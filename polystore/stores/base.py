"""Contract every non-relational document store adapter must satisfy.

Modelled on the narrow slice of `frappe.database.Database` that a DocType
actually needs: write, read, delete. An adapter that cannot honour an
operation raises `StoreOperationUnsupported` rather than failing quietly.
"""

from __future__ import annotations

import abc


class StoreError(Exception):
	"""Base class for every failure originating in a store adapter."""


class StoreUnavailable(StoreError):
	"""The backing service could not be reached."""


class StoreOperationUnsupported(StoreError):
	"""The adapter deliberately does not implement this operation."""


class DocumentStore(abc.ABC):
	"""A per-DocType secondary store holding the flexible part of a record.

	The relational row remains the existence record (see the design note in
	README: writes across two engines are not atomic). This adapter owns only
	the schemaless payload hanging off that row.
	"""

	name: str = "base"

	@abc.abstractmethod
	def put(self, doctype: str, docname: str, payload: dict) -> None:
		"""Create or replace the payload for one document."""

	@abc.abstractmethod
	def get(self, doctype: str, docname: str) -> dict:
		"""Return the payload for one document, or an empty dict."""

	@abc.abstractmethod
	def delete(self, doctype: str, docname: str) -> None:
		"""Remove the payload for one document. Missing is not an error."""

	@abc.abstractmethod
	def find(self, doctype: str, criteria: dict, limit: int = 20) -> list[dict]:
		"""Return payloads matching a backend-native filter expression."""

	@abc.abstractmethod
	def count(self, doctype: str, criteria: dict | None = None) -> int:
		"""Return how many payloads match."""

	@abc.abstractmethod
	def ping(self) -> dict:
		"""Raise `StoreUnavailable` if the backend is not reachable."""
