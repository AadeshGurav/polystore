"""DocType -> store routing, read from site config rather than hardcoded.

	"polystore_routing": {"Library Book": "mongo"}

A DocType absent from the map uses the ordinary relational path unchanged,
which keeps the blast radius of this app to the DocTypes that opt in.
"""

from __future__ import annotations

import frappe

from polystore.stores.base import DocumentStore
from polystore.stores.mongo import MongoDocumentStore

_ADAPTERS: dict[str, type[DocumentStore]] = {"mongo": MongoDocumentStore}
_instances: dict[str, DocumentStore] = {}


def routing_table() -> dict[str, str]:
	return frappe.conf.get("polystore_routing") or {}


def backend_for(doctype: str) -> str | None:
	"""Return the configured backend key for a DocType, if any."""
	return routing_table().get(doctype)


def store_for(doctype: str) -> DocumentStore | None:
	"""Return the store adapter routed to this DocType, or None for SQL-only."""
	backend = backend_for(doctype)
	if not backend:
		return None

	if backend not in _ADAPTERS:
		frappe.throw(
			f"DocType {doctype} is routed to unknown store backend '{backend}'. "
			f"Known backends: {', '.join(sorted(_ADAPTERS))}."
		)

	if backend not in _instances:
		_instances[backend] = _ADAPTERS[backend]()

	return _instances[backend]


def register_adapter(key: str, adapter: type[DocumentStore]) -> None:
	"""Add a backend at runtime — the extension point for a second store."""
	_ADAPTERS[key] = adapter
