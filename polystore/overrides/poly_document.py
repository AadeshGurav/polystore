"""Mixin that routes the schemaless half of a DocType to a secondary store.

Ordering is deliberate and matches the design note: the relational row is the
existence record and is written first by the framework; the payload follows.
If the second write fails the user is told immediately and
`polystore.overrides.poly_document.find_orphans` reports the gap for repair —
the failure is never swallowed.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from polystore.stores.base import StoreError
from polystore.stores.registry import store_for

PAYLOAD_FIELD = "attributes_json"


class PolyStoreMixin:
	"""Adds secondary-store persistence to a normal Frappe Document."""

	def load_payload(self) -> dict:
		store = store_for(self.doctype)
		if not store:
			return {}

		try:
			return store.get(self.doctype, self.name)
		except StoreError as exc:
			frappe.log_error(f"{self.doctype} {self.name}: {exc}", "Polystore read")
			return {}

	def save_payload(self) -> None:
		store = store_for(self.doctype)
		if not store:
			return

		try:
			store.put(self.doctype, self.name, self.parsed_payload())
		except StoreError as exc:
			frappe.log_error(f"{self.doctype} {self.name}: {exc}", "Polystore write")
			frappe.throw(
				_("Saved the record, but its flexible attributes could not be written to {0}: {1}").format(
					store.name, exc
				),
				title=_("Secondary store write failed"),
			)

	def drop_payload(self) -> None:
		store = store_for(self.doctype)
		if not store:
			return

		try:
			store.delete(self.doctype, self.name)
		except StoreError as exc:
			frappe.log_error(f"{self.doctype} {self.name}: {exc}", "Polystore delete")

	def parsed_payload(self) -> dict:
		"""The virtual field as a dict. Invalid JSON is a validation error."""
		raw = (self.get(PAYLOAD_FIELD) or "").strip()
		if not raw:
			return {}

		try:
			parsed = json.loads(raw)
		except ValueError as exc:
			frappe.throw(
				_("Attributes must be valid JSON: {0}").format(exc),
				title=_("Invalid attributes"),
			)

		if not isinstance(parsed, dict):
			frappe.throw(_("Attributes must be a JSON object, not a list or value."))

		return parsed

	def onload(self) -> None:
		"""Ship the payload to the client.

		Virtual fields are stripped from `as_dict()`, so the form never sees
		the value unless it travels in `__onload`.
		"""

		self.set_onload("polystore_payload", self.get(PAYLOAD_FIELD) or "")

	def load_from_db(self) -> None:
		"""Populate the virtual field on every read, not just in the form.

		Without this, any `frappe.get_doc(...).save()` would write an empty
		payload back over the document store.
		"""
		super().load_from_db()
		self.apply_payload()

	def apply_payload(self) -> None:
		"""Populate the virtual field for display from the secondary store."""
		payload = self.load_payload()
		self.set(PAYLOAD_FIELD, json.dumps(payload, indent=2) if payload else "")


def find_orphans(doctype: str) -> list[str]:
	"""Relational rows whose secondary payload is missing — reconciliation input."""
	store = store_for(doctype)
	if not store:
		return []

	names = frappe.get_all(doctype, pluck="name")
	return [name for name in names if not store.get(doctype, name)]
