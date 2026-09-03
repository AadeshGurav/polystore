"""A loan. The SQL row is the record of the transaction; the graph edge it
writes is what makes recommendation traversals possible.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from polystore.graph import traversal
from polystore.graph.backend import GraphUnavailable


class BookLoan(Document):
	def validate(self):
		if self.status == "Returned" and not self.return_date:
			self.return_date = frappe.utils.today()

		if self.is_new() and frappe.db.get_value("Library Book", self.book, "status") == "On Loan":
			frappe.throw(
				_("{0} is already on loan.").format(self.book), title=_("Book unavailable")
			)

	def on_update(self):
		frappe.db.set_value(
			"Library Book",
			self.book,
			"status",
			"Available" if self.status == "Returned" else "On Loan",
		)
		self.write_edge()

	def on_trash(self):
		frappe.db.set_value("Library Book", self.book, "status", "Available")
		try:
			traversal.drop_loan(self.member, self.book)
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")

	def write_edge(self):
		"""The borrow edge survives the return: history is what recommendations read."""
		try:
			traversal.record_loan(self.member, self.book, str(self.loan_date))
		except GraphUnavailable as exc:
			frappe.log_error(f"{self.name}: {exc}", "Polystore graph")
			frappe.msgprint(
				_("Loan saved, but the borrowing graph was not updated: {0}").format(exc),
				indicator="orange",
				alert=True,
			)
