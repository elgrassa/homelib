# HomeLib v2 — Developer Wiki

Architecture and operations documentation for the HomeLib capstone project. This wiki is maintained as repo markdown under `docs/wiki/` (the repo copy is canonical; the Forgejo wiki tab, when synced, mirrors it).

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
| [Crossroads and doors](crossroads-and-doors.md) | Door map, how a door opens (rotunda → `?door=` → renderer), rules for adding one |
| [Monitoring and feedback](monitoring-and-feedback.md) | Observatory vs Grafana on the tip path; what the drill asserts |
| [User flows](user-flows.md) | Sequence diagrams for demo, search, Coffee Table state machine, ingest, reset |
| [Retrieval pipeline](retrieval-pipeline.md) | FTS5, vector matrix, RRF, rerank, rewrite, scene search |
| [Local development](local-development.md) | Prerequisites, `just` commands, env vars, compose profiles |
| [Debugging and troubleshooting](debugging-and-troubleshooting.md) | CI lanes, coverage, eval gates, known hazards |
| [Improving the system](improving-the-system.md) | Extension points, test discipline, v1 fallback safety |

---

## Implementation status (v2 branch stack)

Honest snapshot as of evidence through **WP11 + the 2026-09-05 readiness train (#25 PR-A → #26 PR-B → #27 PR-D → #28 PR-C → #29 PR-E, open into `v2` @ `86ba349`, nothing merged)** (see [`docs/evidence.md`](../evidence.md)
and [`docs/reviewer-handoff-v2.md`](../reviewer-handoff-v2.md)):

| Work package | Branch (typical) | Status |
|---|---|---|
| WP00 config skeleton | `v2` | Done |
| WP01 specs | `feat/wp01-specs` | Done (merged) |
| WP02 SQLite schema | `feat/wp02-sqlite` | Done (merged) |
| WP03 SQLite ingest (dlt) | `feat/wp03-ingest` | Done (merged) |
| WP04 FTS5 + vector matrix + eval | `feat/wp04-retrieval` / eval branch | Done (merged + SQLite eval) |
| WP05 catalog connectors + wiki | `feat/wp05-catalog` | Done (merged) |
| WP06 mentor library | `feat/wp06-mentor` | Done (merged; `POST /v1/mentor/intake` + Mentor door) |
| WP07 Coffee Table + progress | `feat/v2-wp08-wp11-surface` | Done (merged) |
| WP08 Crossroads doors (`HomelibClient`, AST boundary) | same | Done — **seven doors** after PR-B (Roadmap wired); rotunda above the grid in PR-D |
| WP09 Projection reader | same | Done (one-page reader + progress; Listen planned, `specs/audio.md`) |
| WP10 Observatory ≥5 charts + feedback | same | Done — six charts; the drill asserts on it since PR-B |
| WP11 docs / drill / publish | #25..#29 → `v2` | `just drill` **PASSED on the train tip `ee0f318`** (2026-09-05; the run on `ae83d51` failed under load — evidence); **owner Mon:** merge the train A→B→D→C→E, `just publish`, Cloud secrets, submit, peers ×3 |
| Readiness train 2026-09-05 | #25 PR-A · #26 PR-B · #27 PR-D · #28 PR-C · #29 PR-E (graphify jobs, draft) | H1/H3/H2 fixed with named tests; M1/M2 fixed; M3/M4 recorded as owner decisions — [handoff](../handoffs/2026-09-05-stakeholder-picky-review-and-wiki-mermaid-handoff.md) |
| v1 fallback | `main` / tag `v1-fallback` | Complete (Postgres + Grafana) |

When a page marks something **implemented** vs **spec-only**, trust [`docs/evidence.md`](../evidence.md) over this table if they diverge.

---

## Quick links

- [README (reviewer quickstart)](../../README.md)
- [CHECKLIST (rubric)](../../CHECKLIST.md)
- [Course map](../course-map.md)
- [OpenAPI snapshot (v1 live API)](../../specs/openapi.snapshot.json)
