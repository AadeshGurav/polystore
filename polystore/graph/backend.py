"""Neo4j connection handling — the only module that speaks Bolt.

Everything the application does with the graph goes through
`polystore.graph.traversal`; this file exists so that swapping the store is a
change to one module rather than an audit of the codebase.
"""

from __future__ import annotations

import frappe

DEFAULT_URI = "bolt://localhost:7687"

_driver = None


class GraphUnavailable(Exception):
	"""The graph service could not be reached."""


def get_driver():
	global _driver

	if _driver is None:
		try:
			from neo4j import GraphDatabase
		except ImportError as exc:  # pragma: no cover - install-time failure
			raise GraphUnavailable(
				"the neo4j driver is not installed in this bench environment"
			) from exc

		uri = frappe.conf.get("neo4j_uri") or DEFAULT_URI
		user = frappe.conf.get("neo4j_user") or "neo4j"
		password = frappe.conf.get("neo4j_password") or ""
		_driver = GraphDatabase.driver(uri, auth=(user, password))

	return _driver


def run(cypher: str, params: dict | None = None) -> list[dict]:
	"""Execute one Cypher statement and return plain dicts."""
	try:
		with get_driver().session() as session:
			return [record.data() for record in session.run(cypher, params or {})]
	except GraphUnavailable:
		raise
	except Exception as exc:
		raise GraphUnavailable(f"Neo4j query failed: {exc}") from exc


def ping() -> dict:
	try:
		get_driver().verify_connectivity()
	except Exception as exc:
		raise GraphUnavailable(f"Neo4j unreachable: {exc}") from exc

	rows = run("CALL dbms.components() YIELD name, versions RETURN name, versions")
	version = rows[0]["versions"][0] if rows else "unknown"
	return {"backend": "neo4j", "version": version}
