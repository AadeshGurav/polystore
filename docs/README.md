# Documentation

| Document | Read it if you… |
| --- | --- |
| [USER_GUIDE.md](USER_GUIDE.md) | are using or demoing the app — screens, what each panel proves, how to look at the raw databases, and a five-minute demo script |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | have to build on it or rebuild it — how MongoDB and Neo4j sit alongside Frappe's SQL, every hook we use, and the eleven gotchas that cost us time |
| [../README.md](../README.md) | just want to install and run it |

## Design notes

The two feasibility notes this app implements:

- `Database-Flexibility-in-Frappe.docx` — per-DocType routing to a
  non-relational store behind an adapter contract. Implemented in
  `polystore/stores/` and `polystore/overrides/poly_document.py`.
- `Graph-Database-in-Frappe.docx` — relationship logic behind a narrow
  traversal API rather than scattered recursive queries. Implemented in
  `polystore/graph/`.

Where this POC departs from the notes, it is deliberate: the notes recommend
deferring adoption until a workload justifies it, whereas this repository
exists to prove the mechanism works end to end.
