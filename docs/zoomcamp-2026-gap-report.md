# HomeLib vs LLM Zoomcamp 2026 — coverage gap report

What the 2026 cohort teaches, where HomeLib demonstrates it, and what was
missing on 2026-09-06 when this report was written. Every `path:line` below
was checked against the tree at that date; the "FIXES" list at the end is
resolved item by item in the same PR that lands each fix (`DONE:`) or records
why a technique was deliberately not adopted (`Explanation_Skipped:`).
Companion: [`course-map.md`](course-map.md) (module-by-module status) and the
rubric self-audit in the [README](../README.md#rubric-self-audit).

## Part 1 — What the 2026 cohort teaches and where HomeLib shows it

### Table 1 — Module → techniques taught → homework asks

| Module | Techniques taught | Homework asks |
|---|---|---|
| 01 Agentic RAG | minsearch, sqlitesearch, OpenAI API, `RAGBase` helper, sliding-window chunking (size/step), token-usage comparison (chunked vs whole-doc), function calling, agentic loop (ToyAIKit; PydanticAI/OpenAI SDK/LangChain as alternatives) | Chunk with a size/step pair and measure input tokens; build an agent with a search tool and count tool invocations |
| 02 Vector Search | `Xenova/all-MiniLM-L6-v2` (ONNX, 384-d), cosine as dot product of normalised vectors, numpy scoring by hand, minsearch `VectorSearch`, sqlitesearch, pgvector, text-vs-vector comparison, RRF `1/(k+rank)` with `k=60` | Compute cosine by hand; chunk at 2000/1000 chars and score with numpy dot product; compare top-5 text vs vector results; implement RRF |
| 03 Orchestration | Kestra flows, AI-copilot/context engineering, RAG-vs-no-RAG flow, per-task token-usage logging, agent-vs-workflow trade-off | (flow-building exercises in Kestra; no code homework distinct from the workshop) |
| Workshop: dlt | dlt filesystem + REST sources, incremental loading, DuckDB, marimo dashboards, dltHub platform, LLM-trace analysis | (workshop exercises, not a graded homework) |
| 04 Evaluation | LLM-generated ground truth via structured outputs, hit-rate, MRR, text-vs-vector evaluation, RRF `k` sweep (`k ∈ {1,50,100,200}`) tuned on MRR, LLM-as-a-judge, offline vs online evaluation | (bake-off exercises across arms/`k` values; no single canonical homework artifact) |
| 05 Monitoring | OpenTelemetry spans (tracer, span attributes for tokens + cost, custom `SpanExporter` → SQLite, SQL/pandas over spans), Streamlit chat + dashboard, Postgres, thumbs feedback, built-in LLM judge on live traffic, synthetic traffic, Grafana, compose | Homework Q1–Q6 are all OpenTelemetry-based |
| 06 Best Practices | Elasticsearch hybrid search (kNN + BM25), RRF document reranking, LangChain `ElasticsearchRetriever`; production-reflection discussion | (reflection/discussion, no distinct coding homework) |
| 07 Project example (fitness-assistant) | Flask, compose, Postgres logging, Grafana, hit-rate/MRR with boosting, LLM-judge, multiple chunking strategies per content type | (capstone-shaped project, not a graded homework) |
| `etc/chunking.md` (supplementary) | Fixed-size chunking (words/time/sentences), pause/speaker boundaries, paragraph/section splitting, LLM-driven thematic/contextual/hierarchical/intent-based chunking | — |

### Table 2 — Course topic → module → HomeLib status

| Course topic | Module | HomeLib status | Path:line (verified) | What a reviewer expects |
|---|---|---|---|---|
| Keyword search | 01/02 | **Demonstrated** | Postgres FTS: `packages/homelib-rag/src/homelib_rag/index.py:144` (`ts_rank_cd`/`plainto_tsquery`, dispatched from `:137`). SQLite FTS5: `packages/homelib-rag/src/homelib_rag/sqlite_index.py:192` (`search_lexical`), query at `:211` (`chunks_fts MATCH`) | A working BM25/FTS arm, measurable against vector search |
| Embeddings + cosine | 02 | **Demonstrated** | `index.py:47` (`all-MiniLM-L6-v2` model constant), `:183` (pgvector `<=>` cosine query). SQLite: `sqlite_index.py:25` (model constant), matrix cosine at `:312` (`cache.matrix @ query_vec`) | An embedding model matching the course's own, plus a from-scratch or library cosine path |
| Chunking | 01/02/`etc/chunking.md` | **Partial** | Sentence-packed sliding window: `packages/homelib-core/src/homelib_core/chunk.py:42` (`chunk_book`), defaults `target_chars=1200`/`overlap=200` at `:45-46` | No chunk-size experiment and no token-usage comparison (chunked vs whole-doc) exists anywhere in the repo |
| RRF hybrid | 02/06 | **Demonstrated** | `packages/homelib-rag/src/homelib_rag/hybrid.py:35` (`_RRF_K = 60`), `:113` (`1.0 / (_RRF_K + hit.rank)`) | A working RRF fusion of the lexical and vector arms |
| RRF `k` tuning | 04 | **Missing** | `K` is hard-pinned at `hybrid.py:35`; no sweep of `k` values anywhere in `evals/retrieval_eval.py` (confirmed by grep — no `_RRF_K`/sweep logic there) | A `k` sweep (course uses `{1,50,100,200}`) tuned against MRR, with the chosen value justified in an ADR |
| Cross-encoder rerank | (exceeds course; course teaches RRF, not cross-encoder rerank) | **Demonstrated, exceeds course** | `packages/homelib-rag/src/homelib_rag/rerank.py:25` (model `cross-encoder/ms-marco-MiniLM-L-6-v2`), `:47` (lazy singleton load), `:67` (`rerank()`); measured in `evals/results/retrieval.md` | Not required by the rubric, but a reviewer will note it as a beyond-course addition |
| Query rewriting | 06 (adjacent) | **Demonstrated, measured and rejected** | `packages/homelib-rag/src/homelib_rag/rewrite.py:85` (JSON-mode LLM call), `:96`/`:110` (fail-closed fallback to the original query on any error) — decision recorded in `docs/adrs/ADR-001-retrieval-arm.md` | A documented, evidence-based decision, not silent omission — present here |
| Ground-truth generation, structured output | 04 | **Demonstrated** | `evals/ground_truth.py:183-242` (LLM prompt + `response_format={"type":"json_object"}` call) | LLM-generated Q/A pairs with a validated schema |
| Hit-rate / MRR | 04 | **Demonstrated** | `evals/metrics.py:59` (`hit_rate_at_k`), `:80` (`mrr_at_k`); 4 arms × 235 questions in `evals/results/retrieval.md` | Both metrics computed per-arm over a real ground-truth set |
| LLM-as-a-judge | 04 | **Demonstrated offline** | `evals/judge.py:151` (bias-control disclaimer), `:161` (judge prompt template), `:261` (JSON-mode judge call); 4 prompt arms, null result recorded in `docs/adrs/ADR-003-answer-prompt.md` | Offline judge bake-off is present; online judge on live traffic is not (see below) |
| Answer-vs-answer cosine similarity | 04 (second eval method) | **Missing** | No occurrence of embedding-based answer-similarity scoring anywhere under `evals/` | A second, independent LLM-eval signal alongside the judge |
| Function calling / agent loop | 01 | **Demonstrated, but not on the demo path** | `packages/homelib-rag/src/homelib_rag/agent.py:60` (`TOOL_SCHEMAS`), `:319` (`run_agent`), `:322` (`max_rounds: int = 6`); `specs/agent-tools.md:12` states no LangChain, and the same file documents that `run_agent` is not on any `apps/*` request path, backed by `tests/test_repo_hygiene.py:377` (`test_run_agent_is_not_on_the_demo_request_path`) | A reviewer expects to be able to *trigger* the agent loop from the running demo, not just find it in source |
| Tool-invocation count | 01 (homework ask) | **Partial** | `AgentResult.tool_calls`/`rounds_used` fields exist at `agent.py:297-298`, but nothing in `apps/ui` or `apps/api` logging surfaces them | The homework explicitly asks to count tool invocations; the data model supports it but no UI/log path exposes it |
| dlt ingestion | Workshop / 03 | **Demonstrated** | `apps/ingest/pipeline.py:69` (`import dlt`), `:235-238` (`@dlt.resource(name="books", write_disposition="merge", primary_key="book_id", ...)`) | A working incremental dlt pipeline — present, 37 tests per `docs/course-map.md` |
| Kestra / DuckDB / marimo | 03 / Workshop | **Not used** | Justified in `docs/course-map.md:33-39` ("Why dlt and not Kestra") | A reviewer expects a justification, not silence — present |
| Token tracking | 05 | **Demonstrated** | `packages/homelib-rag/src/homelib_rag/answer.py:275-277` (`LLMUsage(prompt_tokens=..., completion_tokens=...)`), logged at `apps/api/main.py:591-592`; chart at `apps/store/observatory.py:118-124` (`id="token_or_cost_estimate"`) | Prompt/completion token counts captured per request |
| Cost tracking ($) | 05 | **Missing** | The `token_or_cost_estimate` chart (`observatory.py:118-124`) sums tokens only, no dollar conversion anywhere in the codebase; `docs/course-map.md:29` claims tokens are "priced when a cloud key is configured" — no such pricing logic exists in code | A dollar-cost estimate, or the course-map sentence corrected to not overclaim |
| OpenTelemetry tracing | 05 | **Missing** | No occurrence of `opentelemetry`/`otel` anywhere in the repo (confirmed by repo-wide grep) | Module 05's homework (Q1–Q6) is entirely OTel-based; this is the largest single gap against the rubric |
| Feedback thumbs | 05 | **Demonstrated** | `apps/ui/app.py:82-89` (👍/👎 buttons, vote-once guard), `apps/ui/api_client.py:261` (`submit_feedback`) | Thumbs feedback wired end-to-end from UI to storage |
| ≥5-chart dashboard | 05 | **Demonstrated** | 6 Observatory charts, `apps/store/observatory.py:44-131`; Grafana 6 panels, `docker/grafana/provisioning/dashboards/json/homelib-overview.json` (panel titles at lines 18, 50, 84, 116, 148, 182) | At least 5 charts over live query/feedback data — present in both the SQLite (Observatory) and Postgres (Grafana) paths |
| Synthetic traffic | 05 | **Demonstrated** | `scripts/demo_traffic.py` (61 lines) | A script to generate representative demo traffic — present |
| Online LLM judge | 05 | **Missing** | No occurrence of an online/live-traffic judge anywhere under `evals/` or `apps/api` (confirmed by grep) | Module 05 expects a judge running against live traffic, not just an offline bake-off |
| Elasticsearch / LangChain | 06 | **Not used, explicitly** | `specs/agent-tools.md:12` ("No LangChain: course module M1 teaches the loop itself..."), `specs/rewrite.md:14` ("...not pulled from LangChain or any retrieval framework's built-in rewriter") | A documented substitution rationale — present |
| MCP / PydanticAI / Logfire | — | **Not used** | No references found in the repo | Out of rubric scope; no course row demands these |
| Streamlit UI + FastAPI | 01/05/07 | **Demonstrated** | `apps/ui/app.py`, `apps/api/main.py` | A working UI and API surface — present |
| Cloud deployment | 07 | **Pending (owner)** | Not yet shipped per `CLAUDE.md` ("Owner-only: ... Cloud deploy") | Rubric credit for a hosted/public demo |

## FIXES gap LLM Zoomcamp 2026

1. **OpenTelemetry tracing** — Module 05's homework (Q1–Q6) is entirely OTel-based, and its complete absence is the single largest rubric gap in the repo. Add a tracer + span attributes for tokens/cost around the `/v1/ask` call path in `apps/api/main.py`, with a custom `SpanExporter` writing to SQLite alongside the existing `query_log` table. **TODO**
2. **Cost tracking in $** — the `token_or_cost_estimate` Observatory chart (`apps/store/observatory.py:118-124`) sums tokens only, and `docs/course-map.md` claims pricing happens "when a cloud key is configured" with no code backing that sentence — a reviewer who checks will find the claim false. Add a per-model $/token table and multiply it into the existing `tokens_prompt`/`tokens_completion` columns already logged in `apps/api/main.py:591-592`. **TODO**
3. **Second LLM-eval method (answer cosine similarity)** — the offline judge (`evals/judge.py`) is the only eval signal on generated answers; the course expects at least two independent methods so one can sanity-check the other. Embed the generated answer and a reference answer with the existing `all-MiniLM-L6-v2` embedder and score cosine similarity in `evals/`. **TODO**
4. **RRF k sweep** — `_RRF_K` is hard-pinned at `hybrid.py:35` with no sweep recorded anywhere, while Module 04's homework explicitly asks for a `k ∈ {1,50,100,200}` sweep tuned on MRR. Add a `--rrf-k` sweep mode to `evals/retrieval_eval.py` and record the winning `k` in an ADR next to `ADR-001`. **TODO**
5. **Chunking experiment (incl. token comparison chunked vs whole-document)** — `chunk_book` (`packages/homelib-core/src/homelib_core/chunk.py:42`) ships one fixed `target_chars=1200`/`overlap=200` configuration with no experiment behind it, while Module 01's homework specifically asks for a size/step comparison measuring input tokens. Run `chunk_book` at 2-3 `target_chars` settings plus a whole-document (no-chunking) baseline and record input-token counts per arm in `evals/`. **TODO**
6. **Online LLM judge on live traffic** — the judge in `evals/judge.py` only runs offline against the 30-question bake-off (`ADR-003`); Module 05 expects a judge scoring live/production traffic, not just a pre-canned eval set. Wire the existing judge into the `/v1/ask` request path (or a sampling job over `query_log`) behind a feature flag so it scores a fraction of live answers. **TODO**
7. **Agent loop visible on a demo path (Mentor)** — `run_agent` (`agent.py:319`) is fully built and tested but `specs/agent-tools.md` and `tests/test_repo_hygiene.py:377` both confirm it sits on no `apps/*` request path, so a reviewer clicking through the live demo will never see it fire. Expose `run_agent` behind a "Mentor" mode/endpoint in `apps/api`/`apps/ui` so a reviewer can trigger and watch it. **TODO**
8. **Book-level hit-rate column** — `evals/metrics.py` reports hit-rate/MRR only in aggregate across all 235 questions (`evals/results/retrieval.md`), with no per-book breakdown, so a book with unusually poor retrieval is invisible in the current report. Add a `book_id` group-by column to the retrieval-eval report. **TODO**
9. **Demo answer cache (speed on Streamlit Cloud; not a course gap)** — the public demo path calls the LLM fresh on every question, which will be visibly slow on Streamlit Cloud's shared CPU; this is a demo-quality issue, not a rubric gap. Cache answers for the fixed demo question set (or memoize on the exact query string) at the `apps/api` layer. **TODO**
10. **Speed confirmation (top-N rerank, models loaded once per process)** — the cross-encoder (`rerank.py:47`) and embedder (`index.py:47` / `sqlite_index.py:25`) both use lazy singletons, and rerank presumably only runs over the top-N hybrid results rather than the full corpus, but neither claim has a measured number attached anywhere in `evals/results/`. Add a latency assertion/measurement confirming reranking is bounded to top-N and models are loaded once per process, not per-request. **TODO**
11. **Kestra** — dlt is the rubric-equal automated-ingestion tool (Module 03 names both as 2-point options), and Kestra would add a scheduler container with nothing to schedule for a static corpus. **Explanation_Skipped:** justified in `docs/course-map.md:33-39` ("Why dlt and not Kestra") — one pipeline, no cross-system scheduling, dlt's incremental loading does the whole job in-process.
12. **Elasticsearch** — Postgres FTS + pgvector (`index.py`) and SQLite FTS5 + numpy (`sqlite_index.py`) already cover BM25/kNN/RRF with zero extra services to stand up. **Explanation_Skipped:** the dual-store architecture (self-hosted Postgres, SQLite-only for demo/Cloud) already satisfies the keyword+vector+RRF rubric rows without adding a third search engine.
13. **LangChain** — a thin OpenAI-compatible client keeps prompts inspectable and evaluable, which the eval harness (`evals/judge.py`, `evals/ground_truth.py`) depends on. **Explanation_Skipped:** documented at `specs/agent-tools.md:12` and `specs/rewrite.md:14` — every LLM call site is hand-written and directly testable with a scripted fake, not hidden behind a framework abstraction.
14. **minsearch** — it is the course's own teaching index; homelib's production-shaped stores (Postgres FTS/pgvector, SQLite FTS5/numpy) replace it with the real thing. **Explanation_Skipped:** minsearch is explicitly a learning tool in the course material, not something a production-shaped demo should ship instead of a real index.
15. **MCP** — no external tool host is in scope for this project; the agent's four tools (`agent.py:60` `TOOL_SCHEMAS`) are called in-process. **Explanation_Skipped:** MCP solves cross-process/cross-org tool sharing, which this single-service demo does not need.
16. **PydanticAI / Logfire** — the agent loop is ~200 lines of hand-rolled function calling (`agent.py`), and Logfire is a paid SaaS observability product, which conflicts with the studio's local-first-observability default. **Explanation_Skipped:** a framework-free loop stays fully inspectable and testable, and adding a paid telemetry SaaS is out of scope for a self-hosted-first project.
17. **DuckDB / marimo** — SQLite (`apps/store/observatory.py`) plus Streamlit already provide the analytics surface (query log, charts, feedback ratio) that the workshop uses DuckDB/marimo for. **Explanation_Skipped:** a second analytics engine would duplicate `apps/store`'s existing SQLite-backed dashboard with no new capability.

**Legend**

- `DONE: <what changed, path, test, measured number>` — used once an item
  above is actually implemented; replaces the `TODO` tag on that line.
- `Explanation_Skipped: <why it is defensible>` — used for items 11-17, which
  are deliberate, already-justified non-adoptions and need no further work.

Every numbered item must end in `DONE:` or `Explanation_Skipped:`;
`tests/test_gap_report.py::test_gap_report_items_are_all_resolved` fails the
build if a `**TODO**` remains (added in the commit that resolves the last
item).

## Part 3 — Corrections to `docs/course-map.md`

Applied on 2026-09-06 (PR "public-snapshot readiness"): row 05 now lists
OpenTelemetry, the online judge and synthetic traffic and distinguishes the
Grafana (Postgres) and Observatory (SQLite) dashboards; the "priced when a
cloud key is configured" sentence is gone until cost tracking exists in code;
row 02 cites the SQLite/numpy vector arm; row 01 says the agent loop is not
reachable from the Ask door; row 06 calls the cross-encoder "beyond course".

