# HomeLib v2 — Developer Wiki

Architecture and operations documentation for the HomeLib capstone project. This wiki is maintained as repo markdown under `docs/wiki/` and can be synced to the [Forgejo wiki](http://localhost:3000/elgrassa/homelib/wiki).

**Ground truth hierarchy**

| Layer | Location | Role |
|---|---|---|
| Product direction | [`specs/product.md`](../../specs/product.md) | What we are building and why |
| Execution plan (frozen) | [`docs/plan-v2.md`](../plan-v2.md) | Week-by-week schedule — do not edit verbatim |
| Field-level contracts | [`specs/*.md`](../../specs/) | One-page specs per component |
| Decisions | [`docs/adrs/`](../adrs/) | Accepted architecture decisions |
| Build log | [`docs/evidence.md`](../evidence.md) | Verified commands and outcomes |

---

## Pages

| Page | What you will learn |
|---|---|
| [Architecture overview](architecture-overview.md) | System diagram, v1→v2 migration, editions, stack |
| [Decision log](decision-log.md) | Fork-in-the-road choices with options, pros/cons, and links to ADRs |
| [Repo structure](repo-structure.md) | Directory tree, where specs/code/tests/data live, branch model |
| [Data model and schemas](data-model-and-schemas.md) | ER diagram, entities, API map, OpenAPI snapshot |
| [User flows](user-flows.md) | Sequence diagrams for demo, search, ingest, reset |
| [Retrieval pipeline](retrieval-pipeline.md) | FTS5, vector matrix, RRF, rerank, rewrite, scene search |
| [Local development](local-development.md) | Prerequisites, `just` commands, env vars, compose profiles |
| [Debugging and troubleshooting](debugging-and-troubleshooting.md) | CI lanes, coverage, eval gates, known hazards |
| [Improving the system](improving-the-system.md) | Extension points, test discipline, v1 fallback safety |

---

## Implementation status (v2 branch stack)

Honest snapshot as of evidence through **WP06** (see [`docs/evidence.md`](../evidence.md)
and [`docs/reviewer-handoff-v2.md`](../reviewer-handoff-v2.md)):

| Work package | Branch (typical) | Status |
|---|---|---|
| WP00 config skeleton | `v2` | Done |
| WP01 specs | `feat/wp01-specs` | Done (merged) |
| WP02 SQLite schema | `feat/wp02-sqlite` | Done (merged) |
| WP03 SQLite ingest (dlt) | `feat/wp03-ingest` | Done (merged) |
| WP04 FTS5 + vector matrix + eval | `feat/wp04-retrieval` / eval branch | Done (merged + SQLite eval) |
| WP05 catalog connectors + wiki | `feat/wp05-catalog` | Done (merged) |
| WP06 mentor library | `feat/wp06-mentor` | Done (merged; API/UI pending) |
| WP07–WP11 API/UI/Observatory/publish | — | Not started |
| v1 fallback | `main` / tag `v1-fallback` | Complete (Postgres + Grafana) |

When a page marks something **implemented** vs **spec-only**, trust [`docs/evidence.md`](../evidence.md) over this table if they diverge.

---

## Quick links

- [README (reviewer quickstart)](../../README.md)
- [CHECKLIST (rubric)](../../CHECKLIST.md)
- [Course map](../course-map.md)
- [OpenAPI snapshot (v1 live API)](../../specs/openapi.snapshot.json)
