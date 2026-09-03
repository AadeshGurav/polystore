"""A book: identity and indexed fields in SQL, everything flexible in MongoDB,
series relationships in Neo4j.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from polystore.graph import traversal
from polystore.graph.backend import GraphUnavailable
from polystore.overrides.poly_document import PolyStoreMixin


class LibraryBook(PolyStoreMixin, Document):
	def validate(self):
		self.parsed_payload()
		self.reject_series_cycle()

	def reject_series_cycle(self):
		"""A book may not, directly or transitively, precede itself."""
		if not self.follows:
			return

		if self.follows == self.name:
			frappe.throw(_("A book cannot follow itself."), title=_("Cycle in series"))

		try:
			path = traversal.would_create_cycle(self.name, self.follows)
		except GraphUnavailable as exc:
			frappe.log_error(str(exc), "Polystore graph")
			frappe.throw(
				_("Cannot verify the series order because the graph store is unreachable: {0}").format(exc),
				title=_("Graph store unavailable"),
			)

		if path:
			frappe.throw(
				_("This would create a loop in the series: {0}").format(" -> ".join(path + [self.title])),
				title=_("Cycle in series"),
			)

	def onload(self):
		self.apply_payload()

	def after_insert(self):
		self.sync_stores()

	def on_update(self):
		self.save_payload()
		self.sync_graph()

	def on_trash(self):
		self.drop_payload()
		self.remove_from_graph()

	def sync_stores(self):
		self.save_payload()
		self.sync_graph()

	def sync_graph(self):
		try:
			traversal.sync_book(self.name, self.title)
			traversal.set_sequel_edge(self.name, self.follows)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")
			frappe.msgprint(
				_("Saved, but the series graph was not updated: {0}").format(exc),
				indicator="orange",
				alert=True,
			)

	def remove_from_graph(self):
		try:
			traversal.delete_book(self.name)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")
