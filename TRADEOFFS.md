# TRADEOFFS.md

What we tried, what we measured, what shipped. Cite ADRs; do not re-run long evals.

## Chunking — 1200/200 vs 600 vs 2000

Sentence-packed chunks, never split a sentence, never cross a chapter
(`homelib_core.chunk.chunk_book`). Sweep on a 6-book subset
([`evals/results/chunking.md`](evals/results/chunking.md)):

| target/overlap | vector hit@5 (book) | mean tokens (top-5) |
|---|---:|---:|
| 600/100 | 0.973 | ~422 |
| **1200/200** | **0.986** | ~893 |
| 2000/400 | 0.973 | ~1560 |

**Shipped:** 1200/200. Smaller chunks explode count; larger waste context vs
whole-section (~3073 tokens).

## Embedder — open MiniLM vs paid

**Shipped:** `sentence-transformers/all-MiniLM-L6-v2`, 384-d, local, pinned in
`.env.example` / compose. No paid embed API on the tip path — sovereignty +
zero per-query embed cost for DACH / local-first demos.

## Hybrid vs hybrid_rerank

On SQLite (235 Q): hit@5 tied at **0.638**; MRR **0.483 → 0.572** with rerank.
**Shipped:** `hybrid_rerank`. Rerank cannot fix a miss; it reorders fusion’s set.

## Query rewrite — OFF

Implemented, measured on 80 Q: hit flat, MRR down (ADR-001). **Left off.**
That *is* the Zoomcamp rewrite point — a negative result, not a missing feature.

## Ingest — dlt, not Kestra

Rerunnable dlt ELT into SQLite (`just seed-sqlite`) and Postgres v1
(`just seed`). Track E cares that ingest is repeatable; orchestrator logo is
Zoomcamp +2, not the interview.

## Store — SQLite tip vs Postgres

Tip product: **SQLite FTS5 + float32 matrix** (`HOMELIB_SQLITE_PATH`).
Postgres+pgvector remains compose for Grafana / `v1-fallback`. Do not claim
“production vector DB” or Qdrant.

## Agent — hand-rolled loop, not LangGraph

`run_agent` exists for course M1 and runs **only** on Mentor intake with
`max_rounds=2`. Ask is single-shot RAG. **No LangGraph in prod.**

## Dual corpus — shelf full-text vs catalog metadata

**Shipped surface:** Ask passages + inventory/romance use the **18** ingested
full-text shelf books. Mentor/Roadmap/`GET /v1/resources?source=discover`
default to the committed **Open Library catalog snapshot**
(`data/catalog.jsonl` → `catalog` table, ~3061 works, metadata only). Live
connector federation stays opt-in (`HOMELIB_CONNECTOR_MODE=live`, issue #46).
