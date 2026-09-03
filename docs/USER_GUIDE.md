# User Guide — Polystore

> **What this app is:** a small library system — books, members, loans — built
> to demonstrate one idea: a single record can live across three different
> databases at once, and still feel like one ordinary Frappe form.
>
> You do not need to know anything about databases to use it. This guide walks
> you through the screens, then shows you how to look at the raw data if you
> want proof.

---

## Getting in

| | |
| --- | --- |
| **Desk (main app)** | http://polystore.localhost:8000/app/polystore |
| **Username** | `Administrator` |
| **Password** | `admin` |
| **Public tour page** | http://polystore.localhost:8000/polystore (no login) |

If the site doesn't respond, it isn't running. In a terminal:

```bash
cd ~/projekts/frappe-bench
bench start
```

Leave that window open — it's the server.

---

## The idea in one picture

Every book and every member is split across three databases:

| Where | What it holds | How you'd describe it |
| --- | --- | --- |
| **MariaDB** (SQL) | Title, author, ISBN, member name, email, phone, dates, status | The regular fields. Every app has these. |
| **MongoDB** (document store) | Free-form attributes and reader profiles | The fields that refuse to fit a form. A hardback has `pages`, an audiobook has `narrator` and `runtime_minutes`, a student member has a `course`. No two records need the same keys. |
| **Neo4j** (graph) | Who borrowed what, which book follows which, who knows whom | The *relationships*. Answering "what should Asha read next" is a walk across links, not a table lookup. |

The app stitches all three together so you never see the seams.

---

## The workspace

Landing at `/app/polystore` gives you the home screen:

* **Store Explorer** — the demo dashboard (next section)
* **Library Book** — the catalogue
* **Library Member** — the readers
* **Book Loan** — who has what

---

## Store Explorer — the tour in one screen

This is the page to open when someone asks "so what does this actually do?"

**1. The status strip (top).** Three cards, one per database, each showing a
green *connected* badge and a live count:

```
MariaDB     8 books · 4 members · 9 loans
MongoDB     9 documents
Neo4j       28 nodes · 21 edges
```

If a badge is red, that service isn't running — see *Troubleshooting*.

**2. "One record, three stores".** Pick a book. You get the same record three
times, side by side:

* the **MariaDB** columns (title, author, status…)
* the **MongoDB** document — raw JSON, and notice the keys change from book to
  book: *A Wizard of Earthsea* has `narrator` and `runtime_minutes`,
  *Neuromancer* has `drm_free` and `file_size_mb`
* the **Neo4j** edges — who borrowed it, what it follows, the series chain

**3. "A member, split three ways".** The same thing for a reader: SQL contact
details, a MongoDB profile, and their Neo4j connections.

**4. "Search a field SQL has never heard of".** Type `narrator` /
`Rob Inglis`, or `series` / `Dune`, and hit Search. These keys have **no
column anywhere** — the query runs inside MongoDB and comes back with real
books. This is the one to demo when someone asks why not just add a column.

**5. "Traversal".** Pick a member and see book recommendations: *people who
borrowed what you borrowed also borrowed these*. Two hops through the graph.

---

## Books

`/app/library-book`

**The top of the form** is ordinary Frappe: Title, Author, ISBN, Media Type,
Status. Those are SQL columns.

**Follows (previous in series)** links a book to the one before it. This is
stored as a `FOLLOWS` edge in Neo4j.

> **Try the cycle guard:** open *Dune* and set its "Follows" to *Children of
> Dune*, which already follows *Dune Messiah*, which follows *Dune*. Save. The
> app refuses and tells you the exact loop:
> *"This would create a loop in the series: Dune → Dune Messiah → Children of
> Dune"*. It names the path rather than saying "invalid".

**Flexible Attributes** is the MongoDB half. The box shows the stored JSON but
is read-only — deliberately, because there is no SQL column behind it. Click
**Edit Attributes**, type any JSON object, and hit **Save to MongoDB**:

```json
{
  "pages": 412,
  "series": "Dune",
  "themes": ["ecology", "empire"],
  "shelf": "3B"
}
```

Any keys you like. Invalid JSON is rejected before anything is written. On a
brand-new book the attributes are held until you save the book itself.

**The Graph menu** (top right, on saved books) has three actions:

* **Readers also borrowed** — books commonly borrowed alongside this one
* **Series chain** — the full chain of predecessors
* **Raw MongoDB document** — the stored document, exactly as MongoDB has it

---

## Members

`/app/library-member`

This is the clearest illustration of the three-way split — one form, three
databases, top to bottom:

**SQL fields** — Member Name, Email, Phone, Membership Type
(Standard/Student/Staff), Joined On, Status. Ordinary columns, filterable and
sortable in the list view like anything else in Frappe.

**Reader Profile (MongoDB)** — click **Edit Profile**. Anything goes:

```json
{
  "favourite_genres": ["science fiction", "ecology"],
  "reading_goal_2026": 40,
  "accessibility": { "large_print": true },
  "pickup_branch": "Bandra"
}
```

Chen Wei has a `course` and an `accessibility` block; Diya Nair has an
`audiobook_speed`. Neither has the other's fields, and nothing had to be
migrated to make that true.

**Connections (Neo4j)** — click **Manage Connections**. Add another member and
a `KNOWS` edge is written straight into the graph. There is **no child table
and no join table** behind this — if you look in MariaDB you will not find it
anywhere. The form shows two read-only summaries:

* **Knows** — direct connections
* **Friends of friends** — people two hops away that this member doesn't know
  yet, with the mutual connection named

**The Graph menu** adds:

* **Book recommendations** — what to read next, from borrowing patterns
* **Path to another member** — the shortest chain of shared books between two
  readers ("Asha → Dune → Ben")

---

## Loans

`/app/book-loan`

Pick a member and a book, set the date. On save:

* the book's status flips to **On Loan** (and back to **Available** when you
  set the loan to Returned) — SQL;
* a `BORROWED` edge is written into Neo4j.

That edge **stays after the book is returned**. Borrowing history is what makes
recommendations work — deleting it would be like forgetting every book anyone
ever read.

A book already on loan can't be loaned again; the app says so and stops you.

---

## Looking at the raw databases

Useful for proving the data really is where the app claims it is.

### Neo4j — the visual one

Open **http://localhost:7474** and connect with `neo4j` / `neo4jadmin123`.

```cypher
// everything, drawn as a picture
MATCH (n)-[r]->(m) RETURN n, r, m

// who borrowed what
MATCH (m:Member)-[r:BORROWED]->(b:Book) RETURN m, r, b

// the Dune series chain
MATCH p = (:Book)-[:FOLLOWS*]->(:Book) RETURN p

// the social graph
MATCH (a:Member)-[r:KNOWS]-(b:Member) RETURN a, r, b
```

The graph view is genuinely the best-looking part of any demo — lead with it.

### MongoDB

**MongoDB Compass** (GUI): connect to `mongodb://localhost:27017`, open the
**polystore** database, then the **library_book** or **library_member**
collection.

Or the shell:

```bash
mongosh polystore
db.library_book.find().pretty()
db.library_member.findOne({_id: "Chen Wei"})
db.library_book.find({series: "Dune"})       # a query with no SQL equivalent here
```

Notice `_id` is the book or member's name — that's the link back to the SQL row.

### MariaDB

```bash
cd ~/projekts/frappe-bench
bench --site polystore.localhost mariadb
```

```sql
DESCRIBE `tabLibrary Member`;   -- note: no attributes_json, no connections
SELECT name, membership_type, status FROM `tabLibrary Member`;
```

That `DESCRIBE` is worth showing: the flexible profile and the connections are
genuinely *not there*.

---

## A five-minute demo script

1. **Store Explorer** — three green badges. "One app, three live databases."
2. Scroll to **One record, three stores**, pick *A Wizard of Earthsea*.
   "Same book. SQL has the title. MongoDB has the narrator and runtime.
   Neo4j knows who borrowed it."
3. Switch the picker to *Neuromancer*. "Different keys — `drm_free`,
   `file_size_mb`. No migration, no schema change."
4. **Search a field SQL has never heard of**: `series` / `Dune` → three books.
   "There is no series column. That query ran inside MongoDB."
5. **A member, split three ways** — pick Chen Wei. "Contact details in SQL, a
   student profile in MongoDB, connections in the graph."
6. Open **Library Member → Chen Wei → Manage Connections**. Add someone.
   "That link exists only in Neo4j. There's no table for it."
7. Open **Neo4j Browser**, run `MATCH (n)-[r]->(m) RETURN n, r, m`. "And here
   it is."
8. Finish on the cycle guard: try to make *Dune* follow *Children of Dune*.
   "It refuses, and it names the loop."

---

## Troubleshooting

**A badge is red on the Store Explorer.** That service isn't running:

```bash
brew services start mongodb-community
brew services start neo4j
brew services list          # check what's up
```

**The site won't load at all.** `bench start` isn't running, or MariaDB is
down:

```bash
brew services start mariadb@11.8
cd ~/projekts/frappe-bench && bench start
```

**A form action does nothing.** The browser is holding an old copy of the
scripts:

```bash
bench build --app polystore
bench --site polystore.localhost clear-cache
```

then hard-refresh the page (**⌘⇧R**).

**Data looks wrong or you want a clean slate:**

```bash
bench --site polystore.localhost execute polystore.demo.seed
```

Safe to run repeatedly — it updates the demo records in place rather than
duplicating them.

**Check everything at once:**

```bash
bench --site polystore.localhost execute polystore.api.health.status
```

You'll get back the routing table plus the live status of both secondary
stores, with the error text if either is unhappy.

---

## Where to go next

* **`DEVELOPER_GUIDE.md`** (same folder) — how the three-database split is
  actually built, for whoever extends it.
* **`../README.md`** — install and setup from scratch.
