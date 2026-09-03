"""Whitelisted endpoints the desk UI and the /polystore page call."""

from __future__ import annotations

import frappe
from frappe import _

from polystore.graph import traversal
from polystore.stores.registry import store_for


@frappe.whitelist()
def book_attributes(book: str) -> dict:
	"""Flexible attributes for one book, straight from the document store."""
	frappe.has_permission("Library Book", doc=book, throw=True)
	store = store_for("Library Book")
	if not store:
		frappe.throw(_("Library Book is not routed to a document store."))

	return store.get("Library Book", book)


@frappe.whitelist()
def search_by_attribute(key: str, value: str, limit: int = 20) -> list[dict]:
	"""Query the document store on a key that has no SQL column at all."""
	frappe.has_permission("Library Book", throw=True)
	store = store_for("Library Book")
	if not store:
		frappe.throw(_("Library Book is not routed to a document store."))

	matches = store.find("Library Book", {key: value}, limit=int(limit))
	names = [match.get("_name") for match in matches if match.get("_name")]
	if not names:
		return []

	return frappe.get_all(
		"Library Book",
		filters={"name": ["in", names]},
		fields=["name", "title", "author", "media_type", "status"],
	)


@frappe.whitelist()
def recommendations(member: str, limit: int = 5) -> list[dict]:
	frappe.has_permission("Library Member", doc=member, throw=True)
	return traversal.recommend_for_member(member, limit)


@frappe.whitelist()
def also_borrowed(book: str, limit: int = 5) -> list[dict]:
	frappe.has_permission("Library Book", doc=book, throw=True)
	return traversal.readers_also_borrowed(book, limit)


@frappe.whitelist()
def series_chain(book: str, depth: int = 6) -> list[dict]:
	frappe.has_permission("Library Book", doc=book, throw=True)
	return traversal.series_chain(book, depth)


@frappe.whitelist()
def connection(member_a: str, member_b: str) -> list[dict]:
	frappe.has_permission("Library Member", throw=True)
	return traversal.shortest_link(member_a, member_b)


@frappe.whitelist()
def record_across_stores(book: str) -> dict:
	"""The same record as each engine sees it — the core of the demo."""
	frappe.has_permission("Library Book", doc=book, throw=True)

	row = frappe.db.get_value(
		"Library Book",
		book,
		["name", "title", "author", "isbn", "media_type", "status", "follows", "modified"],
		as_dict=True,
	)

	store = store_for("Library Book")
	document = store.get("Library Book", book) if store else {}

	graph, error = _graph_view(book)

	return {
		"sql": row,
		"mongo": document,
		"graph": graph,
		"graph_error": error,
		"collection": frappe.conf.get("polystore_mongo_db") or "polystore",
	}


def _graph_view(book: str) -> tuple[dict, str | None]:
	from polystore.graph.backend import GraphUnavailable, run

	try:
		borrowers = run(
			"MATCH (m:Member)-[r:BORROWED]->(:Book {name: $book}) "
			"RETURN m.member_name AS member, r.loan_date AS loan_date ORDER BY member",
			{"book": book},
		)
		neighbours = traversal.direct_edges(book)
		chain = traversal.series_chain(book)
	except GraphUnavailable as exc:
		return {}, str(exc)

	edges = neighbours[0] if neighbours else {}
	view = {
		"borrowers": borrowers,
		"follows": [title for title in (edges.get("follows") or []) if title],
		"followed_by": [title for title in (edges.get("followed_by") or []) if title],
		"chain": chain,
	}
	return view, None


@frappe.whitelist()
def stats() -> dict:
	"""Row counts per engine, so the demo can show all three are populated."""
	store = store_for("Library Book")

	try:
		documents = store.count("Library Book") if store else 0
		document_error = None
	except Exception as exc:
		documents, document_error = 0, str(exc)

	try:
		from polystore.graph.backend import run

		nodes = run("MATCH (n) RETURN count(n) AS count")[0]["count"]
		edges = run("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"]
		graph_error = None
	except Exception as exc:
		nodes, edges, graph_error = 0, 0, str(exc)

	return {
		"sql": {
			"books": frappe.db.count("Library Book"),
			"members": frappe.db.count("Library Member"),
			"loans": frappe.db.count("Book Loan"),
		},
		"mongo": {"documents": documents, "error": document_error},
		"graph": {"nodes": nodes, "edges": edges, "error": graph_error},
	}


@frappe.whitelist()
def save_attributes(book: str, payload: str) -> dict:
	"""Write the flexible attributes straight into the document store.

	The field is virtual, so the desk form renders it read-only — editing goes
	through here, which is honest about where the data actually lives.
	"""
	frappe.has_permission("Library Book", ptype="write", doc=book, throw=True)

	document = frappe.get_doc("Library Book", book)
	document.set("attributes_json", payload)
	parsed = document.parsed_payload()

	store = store_for("Library Book")
	if not store:
		frappe.throw(_("Library Book is not routed to a document store."))

	store.put("Library Book", book, parsed)
	return parsed


@frappe.whitelist()
def save_member_profile(member: str, payload: str) -> dict:
	"""Write a member's free-form profile into the document store."""
	frappe.has_permission("Library Member", ptype="write", doc=member, throw=True)

	document = frappe.get_doc("Library Member", member)
	document.set("attributes_json", payload)
	parsed = document.parsed_payload()

	store = store_for("Library Member")
	if not store:
		frappe.throw(_("Library Member is not routed to a document store."))

	store.put("Library Member", member, parsed)
	return parsed


@frappe.whitelist()
def member_connections(member: str) -> dict:
	"""Direct KNOWS edges plus two-hop suggestions, read from the graph."""
	frappe.has_permission("Library Member", doc=member, throw=True)
	return {
		"connections": traversal.connections(member),
		"suggestions": traversal.friends_of_friends(member),
	}


@frappe.whitelist()
def add_member_connection(member: str, other: str) -> dict:
	"""Create a KNOWS edge. It exists in Neo4j only — there is no SQL row."""
	frappe.has_permission("Library Member", ptype="write", doc=member, throw=True)

	if member == other:
		frappe.throw(_("A member cannot be connected to themselves."))

	if not frappe.db.exists("Library Member", other):
		frappe.throw(_("{0} is not a member.").format(other))

	traversal.connect_members(member, other)
	return member_connections(member)


@frappe.whitelist()
def remove_member_connection(member: str, other: str) -> dict:
	frappe.has_permission("Library Member", ptype="write", doc=member, throw=True)
	traversal.disconnect_members(member, other)
	return member_connections(member)


@frappe.whitelist()
def member_across_stores(member: str) -> dict:
	"""The same member as each engine sees them."""
	frappe.has_permission("Library Member", doc=member, throw=True)

	row = frappe.db.get_value(
		"Library Member",
		member,
		["name", "member_name", "email", "phone", "membership_type", "joined_on", "status"],
		as_dict=True,
	)

	store = store_for("Library Member")
	document = store.get("Library Member", member) if store else {}

	try:
		graph = {
			"knows": traversal.connections(member),
			"suggestions": traversal.friends_of_friends(member, 3),
			"borrowed": frappe.get_all("Book Loan", filters={"member": member}, pluck="book"),
		}
		error = None
	except Exception as exc:
		graph, error = {}, str(exc)

	return {"sql": row, "mongo": document, "graph": graph, "graph_error": error}
