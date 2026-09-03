"""Connectivity endpoints for the two secondary stores."""

from __future__ import annotations

import frappe

from polystore.graph.backend import ping as ping_graph
from polystore.stores.registry import routing_table, store_for


@frappe.whitelist()
def status() -> dict:
	"""Report both stores plus the active DocType routing table."""
	return {
		"routing": routing_table(),
		"document_store": _probe_document_store(),
		"graph_store": _probe(ping_graph),
	}


def _probe_document_store() -> dict:
	routed = routing_table()
	if not routed:
		return {"ok": False, "error": "No DocType is routed to a document store."}

	store = store_for(next(iter(routed)))
	return _probe(store.ping)


def _probe(check) -> dict:
	try:
		return {"ok": True, **check()}
	except Exception as exc:
		return {"ok": False, "error": str(exc)}
