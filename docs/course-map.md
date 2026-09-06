# Course-module map

Every module of LLM Zoomcamp 2026 and where homelib demonstrates it, with a note
on how we actually run each piece. Status reflects the build honestly: a row
marked *pending* is not yet built, and this file is updated as work lands rather
than written aspirationally at the end.

Module list verified 2026-08-29 against the course repository on
`raw.githubusercontent.com` (read as raw text, not summarized by a fetch tool).
Technique-level coverage, and the resolution of every gap found on 2026-09-06,
is in [`zoomcamp-2026-gap-report.md`](zoomcamp-2026-gap-report.md).

| Module | Tools taught | Where homelib demonstrates it | Status |
|---|---|---|---|
| **01 Agentic RAG** | minsearch, sqlitesearch, OpenAI API, ToyAIKit-style agent loop, **function calling** | `homelib_rag.agent.run_agent`: an explicit tool-calling loop over `search_shelf` / `search_catalog` / `build_roadmap` / `get_block` | **done** — 7 endpoints, roadmap, grounded citations shipped and verified; author-hallucination closed structurally (WP-14). Since 2026-09-07 the **Mentor** door (`POST /v1/mentor/intake`) drives `run_agent` with store-safe injected tools and reports `tool_calls` / `rounds_used` ("Tools used: …" caption); the Ask door / `POST /v1/ask` stays single-shot through `homelib_rag.answer` by design (`test_run_agent_is_only_on_the_mentor_path`) |
| **02 Vector Search** | sentence-transformers, numpy from scratch, minsearch VectorSearch, sqlitesearch, **pgvector**, `all-MiniLM-L6-v2` | pgvector cosine index (Postgres v1 store) + the course's own embedding model; the SQLite tip-path reimplements the same cosine search from scratch over a normalized float32 matrix — `packages/homelib-rag/src/homelib_rag/sqlite_index.py::search_vector`, no pgvector/faiss; lexical-vs-vector arms measured on both stores | **done** — pgvector + `all-MiniLM-L6-v2` live against the real corpus; lexical/vector/hybrid arms measured (WP-09/10/12) |
| **03 Orchestration** | Kestra flows, AI copilot, multi-agent YAML | Ingestion is orchestrated with **dlt**. See "Why dlt and not Kestra" below | **done** — dlt pipeline verified: 37 tests, 0 skipped, against a live Postgres (WP-09) |
| **Workshop: dlt** | **dlt**, DuckDB, marimo, Pydantic AI + Logfire | `apps/ingest/pipeline.py` is a real dlt pipeline with idempotent loading | **done** — same pipeline: 37 tests, 0 skipped, against a live Postgres (WP-09) |
| **04 Evaluation** | LLM-as-a-judge, **hit rate, MRR**, LLM-generated ground truth, structured outputs | Ground-truth generator, 4-arm retrieval eval, 3-prompt judge eval | **done** — retrieval: 4 arms × 235 questions, winner recorded in ADR-001 (WP-12). LLM judge: 4-arm bake-off × 30 questions, **null result** — incumbent kept, per ADR-003 (WP-15). **Added 2026-09-07:** book-level hit-rate column, RRF `k` sweep (flat on this corpus, k stays 60 — ADR-001), answer-vs-reference cosine similarity as a second LLM-eval method (`evals/answer_similarity.py`), and a chunk-size experiment with prompt-token cost (`evals/results/chunking.md`) — gap-report items 3, 4, 5, 8 |
| **05 Monitoring** | Streamlit chat + dashboard, PostgreSQL, **Grafana**, token/cost tracking, 👍/👎 feedback | `query_log` + in-UI feedback + Grafana (Postgres) and Observatory ≥5 charts (SQLite tip path) | **done** — the Observatory is the scored monitoring surface on the SQLite tip path (6 charts + thumbs feedback); Grafana (Postgres) is the v1 surface and stays empty there (ADR-005) (WP-16 / WP10). **Added 2026-09-07:** OpenTelemetry stage tracing (`apps/api/tracing.py`, `GET /v1/traces/{id}`, time-per-stage chart), USD cost from `LLM_PRICE_PER_1K_*`, an online judge over live traffic (`scripts/judge_recent.py`, judged-relevance chart) and a demo answer cache — nine Observatory charts in total; see [`zoomcamp-2026-gap-report.md`](zoomcamp-2026-gap-report.md) items 1, 2, 6, 9 |
| **06 Best Practices** | Elasticsearch hybrid, LangChain retriever, **RRF** reranking | RRF fusion (`homelib_rag.hybrid.hybrid_search`) and cross-encoder rerank (`homelib_rag.rerank.rerank`) are two distinct stages — fusion merges the lexical/vector rankings, rerank re-scores the fused candidates on top; query rewriting (`homelib_rag.rewrite`) exists and was measured | **done** — all three implemented and measured; rewrite **measured and rejected** in ADR-001 (kept off in production) on a matched sample (WP-11/13) |
| **07 Project example** | fitness-assistant: Flask, compose, PG logging, Grafana | homelib mirrors its structure at a higher bar: FastAPI, an eval regression gate, an agentic layer | **done** — build + CI green; cold-clone drill **PASSED** on `v2` @ `d6f9946` ([`docs/evidence.md`](evidence.md)); cloud/submit remain owner Mon |

## How we run each piece

**Embeddings.** `sentence-transformers/all-MiniLM-L6-v2` — deliberately the model
the course teaches, not a newer one. Reviewers recognize it, its 384 dimensions
keep the pgvector index small, and the weights are baked into the API image so
`docker compose up` needs no model download at runtime.

**The LLM.** Any OpenAI-compatible endpoint. The default is an Ollama container
inside the same compose stack running `qwen2.5:7b-instruct`, verified during
preflight to emit real function calls — so the agentic module rests on a checked
fact rather than an assumption. Pointing `LLM_BASE_URL` and `LLM_API_KEY` at a
cloud provider swaps it with no code change; no account is required to run this
project.

**Token and cost tracking.** `query_log` records prompt and completion tokens on
every request. Dollar cost is **not** computed today — there is no per-provider
pricing table in `apps/api/main.py` — so the columns are tokens in/out, not a
bill; a $ cost column is a follow-up, not part of this submission.

**Why dlt and not Kestra.** The rubric names both as 2-point ingestion tools, so
this is a choice between equals rather than a substitution. homelib's ingestion
is one pipeline — parse, chunk, embed, load — with no cross-system scheduling,
so dlt's incremental loading does the whole job in-process, and the pipeline
runs identically on a laptop and in the compose stack without a scheduler
service to stand up. A Kestra flow would add an orchestration tier that this
DAG does not need, and a reviewer would have to boot it to see anything.

**No LangChain.** Module 01 teaches the agent loop itself. Writing that loop
directly keeps every tool call, retry, and termination condition inspectable —
and testable with a scripted fake LLM instead of a mocked framework.
