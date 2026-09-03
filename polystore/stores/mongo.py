"""MongoDB adapter — the reference non-relational backend for this POC.

One collection per routed DocType, one document per record, keyed by the
Frappe document name so the relational row and the payload always agree on
identity.
"""

from __future__ import annotations

import frappe

from polystore.stores.base import DocumentStore, StoreUnavailable

DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_DB = "polystore"

_client = None


def _collection_name(doctype: str) -> str:
	return doctype.lower().replace(" ", "_")


def get_client():
	"""Return a process-wide MongoClient built from site config."""
	global _client

	if _client is None:
		try:
			from pymongo import MongoClient
		except ImportError as exc:  # pragma: no cover - install-time failure
			raise StoreUnavailable(
				"pymongo is not installed in this bench environment"
			) from exc

		uri = frappe.conf.get("polystore_mongo_uri") or DEFAULT_URI
		_client = MongoClient(uri, serverSelectionTimeoutMS=3000)

	return _client


def _db():
	name = frappe.conf.get("polystore_mongo_db") or DEFAULT_DB
	return get_client()[name]


class MongoDocumentStore(DocumentStore):
	name = "mongo"

	def put(self, doctype: str, docname: str, payload: dict) -> None:
		document = dict(payload or {})
		document["_id"] = docname
		document["doctype"] = doctype
		self._collection(doctype).replace_one({"_id": docname}, document, upsert=True)

	def get(self, doctype: str, docname: str) -> dict:
		document = self._collection(doctype).find_one({"_id": docname})
		return self._strip(document)

	def delete(self, doctype: str, docname: str) -> None:
		self._collection(doctype).delete_one({"_id": docname})

	def find(self, doctype: str, criteria: dict, limit: int = 20) -> list[dict]:
		cursor = self._collection(doctype).find(criteria or {}).limit(limit)
		return [
			{"_name": document["_id"], **self._strip(document)} for document in cursor
		]

	def count(self, doctype: str, criteria: dict | None = None) -> int:
		return self._collection(doctype).count_documents(criteria or {})

	def ping(self) -> dict:
		try:
			info = get_client().server_info()
		except Exception as exc:
			raise StoreUnavailable(f"MongoDB unreachable: {exc}") from exc

		return {"backend": "mongo", "version": info.get("version")}

	def _collection(self, doctype: str):
		try:
			return _db()[_collection_name(doctype)]
		except Exception as exc:
			raise StoreUnavailable(f"MongoDB unreachable: {exc}") from exc

	@staticmethod
	def _strip(document: dict | None) -> dict:
		if not document:
			return {}

		return {key: value for key, value in document.items() if key not in ("_id", "doctype")}
