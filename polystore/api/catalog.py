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
