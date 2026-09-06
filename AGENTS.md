# AGENTS.md — HomeLib

Repo-level instructions, auto-loaded every session. Read the maintained docs
below instead of crawling source. Global git/security rules:
`~/.Codex/AGENTS.md` (binding here).

## What this is

LLM Zoomcamp capstone: a private academic shelf you can ask, with citations
that open the page. Dual store (Postgres+pgvector self-hosted; SQLite-only for
demo/Cloud). Stack: Python 3.13 · FastAPI · Streamlit · dlt ingest · Ollama
local / Groq for the public demo behind the existing `OpenAIClient`.
**Forgejo-primary** (`forgejo` remote); never push GitHub.

## Read-first order (token discipline)

1. This file.
1bis. **Named-symbol questions: `graphify explain "<Symbol>"` before grepping**
   — ~200 tokens for `file:line` + typed neighbours. Prefer **function/class
   names as written in code** (`build_rotunda_html`, `ApiClient`,
   `book_metadata`); module-level constants may resolve to a mentioning test
   instead of the binding. Conceptual names do not resolve. The graph cannot
   answer "which files do I touch to do X" (use the module table + `docs/adrs/`
   + latest handoff). A negative result is not proof of absence (DI / untyped
   call graphs are blind). **Never `Read graphify-out/graph.json` or dump
   `GRAPH_REPORT.md` into context** (~14k / ~900k tokens measured 2026-09-05 —
   query only). Never install upstream `graphify-mcp` / the `[mcp]` extra —
   CLI indexer only. Branches never touch `graphify-out/` (graph-guard
   hard-fails); `graph-refresh` regenerates it on `main` after merge (`main`
   is the single long-lived branch — `v2` was collapsed into it 2026-09-06).
   `just graph` is local inspection only — never commit its output. Until the
   first refresh lands, fall back to step 2.
2. Latest handoff in `docs/handoffs/` (`YYYY-MM-DD-*-handoff.md`) — local,
   git-ignored working notes; absent in the public snapshot (skip if missing).
3. `CHECKLIST.md` + `docs/evidence.md` (last ~8 rows) for readiness claims.
4. Relevant `specs/` + `docs/adrs/` for the area you are changing.
5. Full-file source exploration last, scoped to the task.

## Module map

| Module | Type | Purpose |
|---|---|---|
| `apps/api` | service | FastAPI `/v1/*`, health, Observatory |
| `apps/ui` | UI | Streamlit Crossroads doors + rotunda |
| `apps/ingest` | pipeline | dlt corpus + SQLite seed CLI |
| `apps/store` | library | SQLite Coffee Table / Observatory |
| `packages/homelib-rag` | library | retrieval, answer, agent tools, index |
| `packages/homelib-core` | library | shared models / settings |

## Standing rules

- Stacked PRs into `main` (oldest-first, rebase-merge); agents do not merge.
- One `just ci` per push; targeted pytest per fix; no OpenAPI regen unless asked.
- Demo LLM stays behind existing `OpenAIClient`/`LLM_*` — no ProviderChain,
  no `LLM_PROVIDERS`, no new SDK.
- Owner-only: `just publish`, Cloud deploy, peers, LICENSE.

## Skill routing

| Event | Skill |
|---|---|
| Before push / PR | `pr-first-git` |
| Bug fix / review finding | `one-test-per-finding` |
| Feature declared done | `live-gate-debugging` |
| CI / runner symptoms | `forgejo-ci-runner-ops` |
