# Course-module map

Every module of LLM Zoomcamp 2026 and where homelib demonstrates it, with a note
on how we actually run each piece. Status reflects the build honestly: a row
marked *pending* is not yet built, and this file is updated as work lands rather
than written aspirationally at the end.

Module list verified 2026-08-29 against the course repository on
`raw.githubusercontent.com` (read as raw text, not summarized by a fetch tool).

| Module | Tools taught | Where homelib demonstrates it | Status |
|---|---|---|---|
| **01 Agentic RAG** | minsearch, sqlitesearch, OpenAI API, ToyAIKit-style agent loop, **function calling** | `homelib_rag.agent`: an explicit tool-calling loop over `search_shelf` / `search_catalog` / `build_roadmap` / `get_block` | **done** — 7 endpoints, agent loop, roadmap, grounded citations shipped and verified; author-hallucination closed structurally (WP-14) |
| **02 Vector Search** | sentence-transformers, numpy from scratch, minsearch VectorSearch, sqlitesearch, **pgvector**, `all-MiniLM-L6-v2` | pgvector cosine index + the course's own embedding model; lexical-vs-vector arms measured against each other | **done** — pgvector + `all-MiniLM-L6-v2` live against the real corpus; lexical/vector/hybrid arms measured (WP-09/10/12) |
| **03 Orchestration** | Kestra flows, AI copilot, multi-agent YAML | Ingestion is orchestrated with **dlt**. See "Why dlt and not Kestra" below | **done** — dlt pipeline verified: 37 tests, 0 skipped, against a live Postgres (WP-09) |
| **Workshop: dlt** | **dlt**, DuckDB, marimo, Pydantic AI + Logfire | `apps/ingest/pipeline.py` is a real dlt pipeline with idempotent loading | **done** — same pipeline: 37 tests, 0 skipped, against a live Postgres (WP-09) |
| **04 Evaluation** | LLM-as-a-judge, **hit rate, MRR**, LLM-generated ground truth, structured outputs | Ground-truth generator, 4-arm retrieval eval, 3-prompt judge eval | **done** — retrieval: 4 arms × 235 questions, winner recorded in ADR-001 (WP-12). LLM judge: 4-arm bake-off × 30 questions, **null result** — incumbent kept, per ADR-003 (WP-15) |
| **05 Monitoring** | Streamlit chat + dashboard, PostgreSQL, **Grafana**, token/cost tracking, 👍/👎 feedback | `query_log` + in-UI feedback + a provisioned Grafana dashboard | **done** — 6 Grafana panels verified against the live schema; feedback loop verified live end-to-end, ask → 👍 → row in `query_log` (WP-16) |
| **06 Best Practices** | Elasticsearch hybrid, LangChain retriever, **RRF** reranking | RRF hybrid, cross-encoder rerank, and query rewriting — all three | **done** — all three implemented and measured; rewrite **rejected on evidence** on a matched sample (WP-11/13) |
| **07 Project example** | fitness-assistant: Flask, compose, PG logging, Grafana | homelib mirrors its structure at a higher bar: FastAPI, an eval regression gate, an agentic layer | **in progress** — build complete and CI green; the cold-clone drill found and fixed a real citation-resolution bug, and a clean re-run is still pending before submission |

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
every request. Cost is zero under the local default, and priced when a cloud key
is configured. The columns stay either way, because the interesting question is
tokens per answer, not the bill.

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
