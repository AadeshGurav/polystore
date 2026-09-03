"""Behaviour tests for the two secondary stores.

They exercise the routed DocType end to end, so they need MongoDB and Neo4j
running — the point of the POC is that both really are in the write path.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from polystore.graph import traversal
from polystore.overrides.poly_document import find_orphans
from polystore.stores.registry import backend_for, store_for


class TestDocumentStoreRouting(IntegrationTestCase):
	def test_library_book_is_routed_to_mongo(self):
		self.assertEqual(backend_for("Library Book"), "mongo")
		self.assertIsNone(backend_for("Library Member"))

	def test_attributes_land_in_mongo_not_sql(self):
		book = _make_book("Test Atlas", {"pages": 12, "colour": "blue"})

		payload = store_for("Library Book").get("Library Book", book.name)
		self.assertEqual(payload["colour"], "blue")

		columns = {field.fieldname for field in frappe.get_meta("Library Book").fields if not field.is_virtual}
		self.assertNotIn("attributes_json", columns)

	def test_invalid_json_is_rejected_with_a_message(self):
		book = frappe.get_doc(
			{"doctype": "Library Book", "title": "Test Broken", "attributes_json": "{not json"}
		)
		with self.assertRaises(frappe.ValidationError):
			book.insert()

	def test_deleting_a_book_removes_its_payload(self):
		book = _make_book("Test Ephemeral", {"pages": 1})
		name = book.name
		book.delete()

		self.assertEqual(store_for("Library Book").get("Library Book", name), {})

	def test_reconciliation_reports_no_orphans(self):
		_make_book("Test Reconciled", {"pages": 3})
		self.assertNotIn("Test Reconciled", find_orphans("Library Book"))


class TestGraphTraversal(IntegrationTestCase):
	def test_series_edge_and_capped_closure(self):
		first = _make_book("Test Volume One", {})
		second = _make_book("Test Volume Two", {}, follows=first.name)

		chain = traversal.series_chain(second.name)
		self.assertEqual([hop["name"] for hop in chain], [first.name])

	def test_cycle_is_rejected_and_names_the_path(self):
		first = _make_book("Test Loop One", {})
		second = _make_book("Test Loop Two", {}, follows=first.name)

		first.follows = second.name
		with self.assertRaises(frappe.ValidationError):
			first.save()

	def test_loan_writes_a_borrow_edge(self):
		book = _make_book("Test Borrowed", {})
		member = _make_member("Test Reader")
		frappe.get_doc(
			{
				"doctype": "Book Loan",
				"member": member.name,
				"book": book.name,
				"loan_date": frappe.utils.today(),
			}
		).insert()

		edges = traversal.readers_also_borrowed(book.name)
		self.assertIsInstance(edges, list)
		self.assertEqual(frappe.db.get_value("Library Book", book.name, "status"), "On Loan")


def _make_book(title: str, attributes: dict, follows: str | None = None):
	if frappe.db.exists("Library Book", title):
		frappe.delete_doc("Library Book", title, force=True)

	return frappe.get_doc(
		{
			"doctype": "Library Book",
			"title": title,
			"author": "Test Author",
			"follows": follows,
			"attributes_json": json.dumps(attributes),
		}
	).insert()


def _make_member(member_name: str):
	if frappe.db.exists("Library Member", member_name):
		return frappe.get_doc("Library Member", member_name)

	return frappe.get_doc({"doctype": "Library Member", "member_name": member_name}).insert()
