"""Context for the /polystore proof-of-concept dashboard."""

from __future__ import annotations

import frappe

from polystore.api.health import status
from polystore.graph import traversal
from polystore.graph.backend import GraphUnavailable
from polystore.stores.registry import store_for

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.health = status()
	context.books = _books_with_attributes()
	context.members = _members_with_recommendations()
	context.series = _series_chains()
	return context


def _books_with_attributes() -> list[dict]:
	store = store_for("Library Book")
	books = frappe.get_all(
		"Library Book",
		fields=["name", "title", "author", "media_type", "status"],
		order_by="title",
	)

	for book in books:
		book["attributes"] = store.get("Library Book", book["name"]) if store else {}

	return books


def _members_with_recommendations() -> list[dict]:
	members = frappe.get_all("Library Member", fields=["name", "member_name"], order_by="member_name")

	for member in members:
		member["borrowed"] = frappe.get_all(
			"Book Loan", filters={"member": member["name"]}, pluck="book"
		)
		member["recommended"], member["error"] = _safe(
			lambda: traversal.recommend_for_member(member["name"], 3)
		)

	return members


def _series_chains() -> list[dict]:
	chains = []
	for name in frappe.get_all("Library Book", filters={"follows": ["is", "set"]}, pluck="name"):
		hops, error = _safe(lambda: traversal.series_chain(name))
		chains.append({"book": name, "hops": hops or [], "error": error})

	return chains


def _safe(call):
	"""Run a graph call, surfacing failure as text rather than a blank page."""
	try:
		return call(), None
	except GraphUnavailable as exc:
		return None, str(exc)
