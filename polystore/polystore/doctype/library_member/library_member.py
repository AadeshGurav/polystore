"""A member. Relational record of record; a node in the borrowing graph."""

import frappe
from frappe import _
from frappe.model.document import Document

from polystore.graph import traversal
from polystore.graph.backend import GraphUnavailable


class LibraryMember(Document):
	def on_update(self):
		try:
			traversal.sync_member(self.name, self.member_name)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")
			frappe.msgprint(
				_("Saved, but the borrowing graph was not updated: {0}").format(exc),
				indicator="orange",
				alert=True,
			)

	def on_trash(self):
		try:
			traversal.delete_member(self.name)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")
