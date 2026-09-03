"""The traversal API — the only sanctioned way to read or write graph edges.

Three primitives the application actually needs (direct edges, transitive
closure with a depth cap, cycle detection) plus the two recommendation
queries built on them. No caller issues its own Cypher.
"""

from __future__ import annotations

from polystore.graph.backend import run

MAX_DEPTH = 6


def sync_member(name: str, member_name: str) -> None:
	run(
		"MERGE (m:Member {name: $name}) SET m.member_name = $member_name",
		{"name": name, "member_name": member_name},
	)


def sync_book(name: str, title: str) -> None:
	run(
		"MERGE (b:Book {name: $name}) SET b.title = $title",
		{"name": name, "title": title},
	)


def record_loan(member: str, book: str, loan_date: str) -> None:
	"""Write the borrow edge. Idempotent: re-saving a loan does not duplicate."""
	run(
		"""
		MATCH (m:Member {name: $member}), (b:Book {name: $book})
		MERGE (m)-[r:BORROWED]->(b)
		SET r.loan_date = $loan_date
		""",
		{"member": member, "book": book, "loan_date": loan_date},
	)


def drop_loan(member: str, book: str) -> None:
	run(
		"MATCH (:Member {name: $member})-[r:BORROWED]->(:Book {name: $book}) DELETE r",
		{"member": member, "book": book},
	)


def set_sequel_edge(book: str, follows: str | None) -> None:
	"""Point a book at its predecessor, replacing any existing edge."""
	run("MATCH (:Book {name: $book})-[r:FOLLOWS]->() DELETE r", {"book": book})

	if follows:
		run(
			"""
			MATCH (b:Book {name: $book}), (p:Book {name: $follows})
			MERGE (b)-[:FOLLOWS]->(p)
			""",
			{"book": book, "follows": follows},
		)


def direct_edges(book: str) -> list[dict]:
	"""Immediate predecessor and successors of a book in its series."""
	return run(
		"""
		MATCH (b:Book {name: $book})
		OPTIONAL MATCH (b)-[:FOLLOWS]->(p:Book)
		OPTIONAL MATCH (n:Book)-[:FOLLOWS]->(b)
		RETURN collect(DISTINCT p.title) AS follows, collect(DISTINCT n.title) AS followed_by
		""",
		{"book": book},
	)


def series_chain(book: str, depth: int = MAX_DEPTH) -> list[dict]:
	"""Transitive closure of FOLLOWS, capped so a query can never run away."""
	depth = max(1, min(int(depth), MAX_DEPTH))
	return run(
		f"""
		MATCH path = (b:Book {{name: $book}})-[:FOLLOWS*1..{depth}]->(ancestor:Book)
		RETURN ancestor.name AS name, ancestor.title AS title, length(path) AS distance
		ORDER BY distance
		""",
		{"book": book},
	)


def would_create_cycle(book: str, follows: str) -> list[str]:
	"""Return the offending path if `book -> follows` would close a loop."""
	if book == follows:
		return [book]

	rows = run(
		f"""
		MATCH path = (start:Book {{name: $follows}})-[:FOLLOWS*1..{MAX_DEPTH}]->(end:Book {{name: $book}})
		RETURN [node IN nodes(path) | node.title] AS titles
		LIMIT 1
		""",
		{"book": book, "follows": follows},
	)
	return rows[0]["titles"] if rows else []


def recommend_for_member(member: str, limit: int = 5) -> list[dict]:
	"""Books borrowed by people who borrowed what this member borrowed."""
	return run(
		"""
		MATCH (me:Member {name: $member})-[:BORROWED]->(:Book)<-[:BORROWED]-(peer:Member)
		MATCH (peer)-[:BORROWED]->(suggestion:Book)
		WHERE NOT (me)-[:BORROWED]->(suggestion)
		RETURN suggestion.name AS name, suggestion.title AS title,
			count(DISTINCT peer) AS shared_readers
		ORDER BY shared_readers DESC, title
		LIMIT $limit
		""",
		{"member": member, "limit": int(limit)},
	)


def readers_also_borrowed(book: str, limit: int = 5) -> list[dict]:
	return run(
		"""
		MATCH (:Book {name: $book})<-[:BORROWED]-(:Member)-[:BORROWED]->(other:Book)
		WHERE other.name <> $book
		RETURN other.name AS name, other.title AS title, count(*) AS times
		ORDER BY times DESC, title
		LIMIT $limit
		""",
		{"book": book, "limit": int(limit)},
	)


def shortest_link(member_a: str, member_b: str) -> list[dict]:
	"""How two readers connect through the books they have shared."""
	return run(
		"""
		MATCH path = shortestPath(
			(a:Member {name: $a})-[:BORROWED*1..6]-(b:Member {name: $b})
		)
		RETURN [node IN nodes(path) | coalesce(node.member_name, node.title)] AS hops,
			length(path) AS distance
		""",
		{"a": member_a, "b": member_b},
	)


def delete_book(name: str) -> None:
	run("MATCH (b:Book {name: $name}) DETACH DELETE b", {"name": name})


def delete_member(name: str) -> None:
	run("MATCH (m:Member {name: $name}) DETACH DELETE m", {"name": name})


def sync_member_profile(name: str, member_name: str, membership_type: str | None) -> None:
	"""Keep the node's own properties in step with the SQL row."""
	run(
		"MERGE (m:Member {name: $name}) SET m.member_name = $member_name, m.membership_type = $membership_type",
		{"name": name, "member_name": member_name, "membership_type": membership_type or "Standard"},
	)


def connect_members(member: str, other: str) -> None:
	"""An undirected acquaintance edge, written once in each direction's view."""
	if member == other:
		return

	run(
		"""
		MATCH (a:Member {name: $member}), (b:Member {name: $other})
		MERGE (a)-[:KNOWS]-(b)
		""",
		{"member": member, "other": other},
	)


def disconnect_members(member: str, other: str) -> None:
	run(
		"MATCH (:Member {name: $member})-[r:KNOWS]-(:Member {name: $other}) DELETE r",
		{"member": member, "other": other},
	)


def connections(member: str) -> list[dict]:
	"""Everyone this member is directly linked to."""
	return run(
		"""
		MATCH (:Member {name: $member})-[:KNOWS]-(other:Member)
		RETURN other.name AS name, other.member_name AS member_name,
			other.membership_type AS membership_type
		ORDER BY member_name
		""",
		{"member": member},
	)


def friends_of_friends(member: str, limit: int = 5) -> list[dict]:
	"""Two hops out: people this member does not know yet, ranked by mutuals."""
	return run(
		"""
		MATCH (me:Member {name: $member})-[:KNOWS]-(mutual:Member)-[:KNOWS]-(candidate:Member)
		WHERE candidate <> me AND NOT (me)-[:KNOWS]-(candidate)
		RETURN candidate.name AS name, candidate.member_name AS member_name,
			count(DISTINCT mutual) AS mutuals,
			collect(DISTINCT mutual.member_name)[0..3] AS through
		ORDER BY mutuals DESC, member_name
		LIMIT $limit
		""",
		{"member": member, "limit": int(limit)},
	)
