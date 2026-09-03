# Polystore

A working Frappe app that keeps one logical record across three engines, as a
proof of concept for the two feasibility notes it implements:

- **Database Flexibility in Frappe** — per-DocType routing to a non-relational
  store, behind an adapter contract, with no fork of the framework.
- **Graph Database in Frappe** — dependency/relationship logic behind a narrow
  traversal API, so the graph store is one module rather than an audit surface.

The demo domain is a small library.

| Engine | What it holds | Why there |
| --- | --- | --- |
| MariaDB | Book, member and loan rows — identity, links, indexed fields | Existence record; permissions, list views and reports all work unchanged |
| MongoDB | Each book's free-form `attributes` document | Keys differ per media type (`pages`, `narrator`, `file_size_mb`) — a schema per row is exactly what SQL is bad at |
| Neo4j | `BORROWED` and `FOLLOWS` edges | Recommendations and series order are traversals, not joins |

## What it demonstrates

1. **Routing is configuration, not code.** `polystore_routing` in
   `site_config.json` maps DocType to backend. A DocType absent from the map
   takes the ordinary relational path untouched.
2. **The flexible payload never reaches SQL.** `attributes_json` is a virtual
   DocField — the controller loads it from MongoDB on read and writes it back
   on save. There is no column for it. `bench --site … execute
   polystore.api.catalog.search_by_attribute` queries keys SQL has never heard of.
3. **All graph access goes through one module.** `polystore/graph/traversal.py`
   is the only place Cypher is written: direct edges, transitive closure with a
   depth cap, cycle detection, and the two recommendation queries.
4. **Cycles are refused with the path named.** Saving a book whose `follows`
   chain would close a loop fails validation and prints the offending sequence.
5. **Cross-engine writes are not atomic, and the app says so.** The SQL row is
   written first; a failed secondary write raises a specific error rather than
   passing silently, and `polystore.overrides.poly_document.find_orphans`
   reports rows whose payload is missing so they can be repaired.

## Layout

```
polystore/
  stores/        base.py (adapter contract) · mongo.py · registry.py (routing)
  graph/         backend.py (the only Bolt client) · traversal.py (the API)
  overrides/     poly_document.py (mixin adding secondary-store persistence)
  api/           health.py · catalog.py (whitelisted endpoints)
  polystore/doctype/  library_book · library_member · book_loan
  www/           polystore.html (the dashboard at /polystore)
  demo.py        seed data
  tests/         end-to-end tests against both live stores
```

## Setup

Requires a Frappe v15+ bench, MongoDB and Neo4j.

```bash
# services
brew services start mongodb-community
brew services start neo4j
# or: docker compose up -d   (see docker-compose.yml)

# app
bench get-app polystore https://github.com/AadeshGurav/polystore
bench new-site polystore.localhost --install-app polystore

# wiring
bench --site polystore.localhost set-config polystore_mongo_uri "mongodb://localhost:27017"
bench --site polystore.localhost set-config polystore_mongo_db "polystore"
bench --site polystore.localhost set-config -p polystore_routing '{"Library Book": "mongo"}'
bench --site polystore.localhost set-config neo4j_uri "bolt://localhost:7687"
bench --site polystore.localhost set-config neo4j_user "neo4j"
bench --site polystore.localhost set-config neo4j_password "<password>"

# data + run
bench --site polystore.localhost execute polystore.demo.seed
bench start
```

Then open the desk at **http://polystore.localhost:8000/app/polystore**:

- **Polystore workspace** — shortcuts to the three DocTypes and to the explorer.
- **Store Explorer** (`/app/polystore-explorer`) — live status of all three
  engines, the same record shown side by side as MariaDB, MongoDB and Neo4j each
  hold it, a search over MongoDB keys that have no SQL column, and graph
  recommendations.
- **Library Book form** — the MongoDB document is editable inline under *Flexible
  Attributes*; the *Graph* menu runs the traversals against Neo4j.
- **Library Member form** — recommendations, and the shortest path between two
  readers through the books they share.

There is also a public page at **/polystore** for a read-only tour.

If you edit the workspace or page JSON later, `bench migrate` will not overwrite
what is already in the database — re-import it with
`bench --site polystore.localhost execute polystore.demo.resync_desk`.

## Checking it

```bash
bench --site polystore.localhost execute polystore.api.health.status
bench --site polystore.localhost run-tests --app polystore
mongosh polystore --eval 'db.library_book.find().limit(3)'
```

In Neo4j Browser: `MATCH (m:Member)-[r:BORROWED]->(b:Book) RETURN m,r,b`

## Known limits

These are properties of the design, not defects to hide:

- **No atomicity across engines.** A crash between the SQL write and the MongoDB
  write leaves a row without its payload. `find_orphans` is the reconciliation input.
- **User-authored SQL reports cannot read the MongoDB payload.** The right
  behaviour is an explicit limitation, never a silent empty result.
- **Permission filtering and full-text search** for the payload would each need a
  purpose-built implementation; this POC scopes them out deliberately.
- **Traversal depth is capped at six hops** so a malformed graph cannot hang a request.

## Licence

MIT
