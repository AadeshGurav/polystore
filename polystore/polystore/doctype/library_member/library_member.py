"""A member across all three engines.

	MariaDB   name, email, phone, membership type, join date, status
	MongoDB   the reader profile — any shape, no two members alike
	Neo4j     the member node, its BORROWED edges, and KNOWS edges to other readers
"""

import frappe
from frappe import _
from frappe.model.document import Document

from polystore.graph import traversal
from polystore.graph.backend import GraphUnavailable
from polystore.overrides.poly_document import PolyStoreMixin


class LibraryMember(PolyStoreMixin, Document):
	def validate(self):
		self.parsed_payload()

	def onload(self):
		super().onload()
		self.set_onload("polystore_connections", self.graph_connections())
		self.set_onload("polystore_suggestions", self.graph_suggestions())

	def after_insert(self):
		self.save_payload()
		self.sync_graph()

	def on_update(self):
		self.save_payload()
		self.sync_graph()

	def on_trash(self):
		self.drop_payload()
		try:
			traversal.delete_member(self.name)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")

	def sync_graph(self):
		try:
			traversal.sync_member_profile(self.name, self.member_name, self.membership_type)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")
			frappe.msgprint(
				_("Saved, but the borrowing graph was not updated: {0}").format(exc),
				indicator="orange",
				alert=True,
			)

	def graph_connections(self) -> list[dict]:
		if self.is_new():
			return []

		try:
			return traversal.connections(self.name)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")
			return []

	def graph_suggestions(self) -> list[dict]:
		if self.is_new():
			return []

		try:
			return traversal.friends_of_friends(self.name)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")
			return []
