"""Seed data for the proof of concept.

	bench --site polystore.localhost execute polystore.demo.seed

Deliberately writes through the ordinary document API so every record takes
the same path a user would: SQL row, then MongoDB payload, then Neo4j edges.
"""

from __future__ import annotations

import json

import frappe

from polystore.graph import traversal

BOOKS = [
	("Dune", "Frank Herbert", "Book", None, {"pages": 412, "series": "Dune", "themes": ["ecology", "empire"]}),
	("Dune Messiah", "Frank Herbert", "Book", "Dune", {"pages": 256, "series": "Dune", "themes": ["empire"]}),
	("Children of Dune", "Frank Herbert", "Book", "Dune Messiah", {"pages": 444, "series": "Dune"}),
	("Neuromancer", "William Gibson", "Ebook", None, {"drm_free": True, "file_size_mb": 1.4, "formats": ["epub", "mobi"]}),
	("Snow Crash", "Neal Stephenson", "Ebook", None, {"drm_free": False, "file_size_mb": 2.1, "formats": ["epub"]}),
	("The Left Hand of Darkness", "Ursula K. Le Guin", "Book", None, {"pages": 304, "awards": ["Hugo", "Nebula"]}),
	("A Wizard of Earthsea", "Ursula K. Le Guin", "Audiobook", None, {"narrator": "Rob Inglis", "runtime_minutes": 421}),
	("Piranesi", "Susanna Clarke", "Audiobook", None, {"narrator": "Chiwetel Ejiofor", "runtime_minutes": 386}),
]

MEMBERS = [
	(
		"Asha Kulkarni",
		"asha@example.com",
		"+91 98200 11111",
		"Staff",
		{"favourite_genres": ["science fiction", "ecology"], "reading_goal_2026": 40, "prefers": "hardback"},
	),
	(
		"Ben Okafor",
		"ben@example.com",
		"+91 98200 22222",
		"Standard",
		{"favourite_genres": ["cyberpunk"], "newsletter": True, "pickup_branch": "Bandra"},
	),
	(
		"Chen Wei",
		"chen@example.com",
		"+91 98200 33333",
		"Student",
		{"course": "Comparative Literature", "reading_goal_2026": 25, "accessibility": {"large_print": True}},
	),
	(
		"Diya Nair",
		"diya@example.com",
		"+91 98200 44444",
		"Standard",
		{"favourite_genres": ["literary fiction"], "audiobook_speed": 1.25},
	),
]

# KNOWS edges — these live in Neo4j only, with no SQL row behind them.
CONNECTIONS = [
	("Asha Kulkarni", "Ben Okafor"),
	("Ben Okafor", "Chen Wei"),
	("Chen Wei", "Diya Nair"),
]

LOANS = [
	("Asha Kulkarni", "Dune"),
	("Asha Kulkarni", "Neuromancer"),
	("Ben Okafor", "Dune"),
	("Ben Okafor", "Snow Crash"),
	("Ben Okafor", "Piranesi"),
	("Chen Wei", "Neuromancer"),
	("Chen Wei", "The Left Hand of Darkness"),
	("Diya Nair", "Piranesi"),
	("Diya Nair", "A Wizard of Earthsea"),
]


def seed():
	"""Create members, books and loans. Safe to run more than once."""
	for member_name, email, phone, membership_type, profile in MEMBERS:
		_upsert(
			"Library Member",
			member_name,
			{
				"member_name": member_name,
				"email": email,
				"phone": phone,
				"membership_type": membership_type,
				"attributes_json": json.dumps(profile, indent=2),
			},
		)

	for left, right in CONNECTIONS:
		traversal.connect_members(left, right)

	for title, author, media_type, follows, attributes in BOOKS:
		_upsert(
			"Library Book",
			title,
			{
				"title": title,
				"author": author,
				"media_type": media_type,
				"attributes_json": json.dumps(attributes, indent=2),
			},
		)

	# Series edges are set in a second pass so the target always exists.
	for title, _author, _media, follows, _attributes in BOOKS:
		if follows:
			book = frappe.get_doc("Library Book", title)
			book.follows = follows
			book.save()

	for member, title in LOANS:
		if frappe.db.exists("Book Loan", {"member": member, "book": title}):
			continue

		frappe.get_doc(
			{
				"doctype": "Book Loan",
				"member": member,
				"book": title,
				"loan_date": frappe.utils.today(),
				"status": "Returned",
			}
		).insert()

	frappe.db.commit()
	print(
		f"Seeded {len(MEMBERS)} members, {len(BOOKS)} books, {len(LOANS)} loans, "
		f"{len(CONNECTIONS)} member connections."
	)


def _upsert(doctype: str, name: str, values: dict):
	if frappe.db.exists(doctype, name):
		document = frappe.get_doc(doctype, name)
		document.update(values)
		document.save()
		return document

	return frappe.get_doc({"doctype": doctype, **values}).insert()


def resync_desk():
	"""Force the workspace and desk page definitions back over the database.

	`bench migrate` leaves an existing Workspace alone, so editing the JSON in
	this app has no effect until it is re-imported:

		bench --site polystore.localhost execute polystore.demo.resync_desk
	"""
	from frappe.modules.import_file import import_file_by_path

	paths = [
		frappe.get_app_path("polystore", "polystore", "workspace", "polystore", "polystore.json"),
		frappe.get_app_path("polystore", "polystore", "page", "polystore_explorer", "polystore_explorer.json"),
	]

	for path in paths:
		import_file_by_path(path, force=True, reset_permissions=True)

	frappe.db.commit()
	frappe.clear_cache()
	print("Re-imported workspace and desk page.")
