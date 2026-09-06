# spec: monitoring — `query_log` + Grafana + `scripts/demo_traffic.py`

**Implemented by:** WP-16 (v1, live on `v1-fallback` / current `main` compose).
**v2 target:** `specs/observatory.md` + ADR-005 — Grafana is **not** the v2
product. This file remains the field-level owner of `query_log` and
`demo_traffic.py`. WP10 reads the same table from SQLite.

**Consumed by:** rubric Monitoring criterion — **both halves required**: in-UI
thumbs feedback (specs/ui.md) AND a dashboard of ≥5 charts. v1 = Grafana;
v2 = Observatory. Neither feedback nor charts alone satisfies the rubric row.

## Purpose

Every `/v1/ask` call leaves an auditable, privacy-respecting trace, and that
trace is visible to a human within seconds via a provisioned dashboard — not
just queryable with SQL after the fact. `POST /v1/feedback` is specified in
`specs/api.md`; this spec does not redefine it, only the table it writes into
and the dashboard reading from that table.

## Public interface

```python
# homelib_rag.monitoring
def log_query(
    *, request_id: str, arm: str, k: int, rerank: bool, rewrite: bool,
    model: str, tokens_prompt: int, tokens_completion: int,
    latency_ms: int, query: str, store_plaintext: bool = False,
) -> None: ...
    # writes one row; query is ALWAYS hashed, plaintext column populated
    # only when store_plaintext=True (opt-in, off by default)

def record_feedback(request_id: str, feedback: Literal["up", "down"]) -> bool: ...
    # False -> unknown request_id (caller turns this into api.md's 404)

def query_sha256_prefix(query: str) -> str: ...   # first 16 hex chars of sha256(query)
```

```python
# scripts/demo_traffic.py
def main(n: int = 40) -> None: ...   # CLI: --n; fires n synthetic /v1/ask + /v1/feedback
    # calls against a running compose stack to populate query_log + Grafana
```

## Data contracts (field-level)

`query_log` (base columns owned by specs/indexing.md's SQL; this spec adds the
plaintext opt-in column):

```
request_id            text PRIMARY KEY
ts                     timestamptz
latency_ms             int
arm                    text                 -- "lexical"|"vector"|"hybrid"|"hybrid_rerank"
k                      int
rerank                 boolean
rewrite                boolean
model                  text
tokens_prompt          int
tokens_completion      int
query_sha256_prefix    text                 -- ALWAYS populated: first 16 hex chars of sha256(query)
degraded               boolean NOT NULL     -- true when the answer came from a fallback path (specs/answer.md)
query_plaintext        text NULL            -- populated ONLY when the caller opts in; NULL by default
feedback               text NULL            -- "up"|"down"|NULL, set by POST /v1/feedback (specs/api.md)
```

Privacy rule: `query_sha256_prefix` is written unconditionally and is what the
Grafana dashboard (v1) / Observatory (v2) and eval tooling read; `query_plaintext` exists purely for a
human operator who explicitly opted in per-request (e.g. a debug flag on
`/v1/ask`) and is never required by any downstream consumer.

**Grafana dashboard (v1 only)** — `docker/grafana/provisioning/dashboards/homelib.json`,
committed, loaded by Grafana's file provisioner (no manual "add panel" step).
Datasource: the same Postgres, via a read-only role provisioned in
`docker/initdb/`. v2 compose may keep this service until Observatory is green
(ADR-005); do not treat Grafana as the scored v2 surface. Minimum 5 panels, all backed by `query_log`:

```
1. Queries/hour        -- count(*) grouped by 1-hour bucket on ts
2. Latency p50/p95      -- percentile_cont(0.5|0.95) within group (order by latency_ms)
3. Arm distribution      -- count(*) grouped by arm
4. Feedback ratio        -- count(feedback='up') / count(feedback IS NOT NULL)
5. Token usage           -- sum(tokens_prompt), sum(tokens_completion) over time
6. Error rate            -- (6th panel) count(*) FILTER (WHERE degraded) / count(*)
```

## Error/degradation behavior

- `log_query` failing to write (DB unreachable) never blocks the `/v1/ask`
  response — the answer is returned to the caller and the log write is
  best-effort with a logged warning; monitoring must not become a new way for
  the API to 500.
- `record_feedback` on an unknown `request_id` returns `False` and does not
  insert a row — `specs/api.md` turns that into a 404, this function never
  silently creates a placeholder log entry.
- `query_sha256_prefix` is computed even if `store_plaintext=True` fails
  downstream — the hash path and the plaintext path are independent; a
  plaintext-storage failure never means the row loses its hash.
- The Grafana provisioning file failing to load (malformed JSON) fails
  `docker compose up`'s Grafana healthcheck loudly rather than silently
  starting with an empty dashboard list.

## Named red tests (write before the code)

- `test_query_never_stored_plaintext_by_default` — call `log_query` with
  `store_plaintext=False` (the default), assert `query_plaintext IS NULL` and
  `query_sha256_prefix` equals the first 16 hex chars of a manually computed
  `sha256(query)`.
- `test_query_plaintext_opt_in_stores_full_text` — same call with
  `store_plaintext=True`, assert `query_plaintext == query` exactly.
- `test_record_feedback_unknown_request_id_returns_false`.
- `test_record_feedback_updates_existing_row_not_insert` — row count before
  and after `record_feedback` on a known `request_id` is unchanged.
- `test_log_query_failure_does_not_raise` — DB connection mocked to raise;
  `log_query` swallows it and logs a warning instead of propagating.
- `test_dashboard_json_has_at_least_five_panels` — loads
  `docker/grafana/provisioning/dashboards/homelib.json` and asserts
  `len(panels) >= 5` and every panel's `datasource` refers to the Postgres
  source (schema check, not a live Grafana call).

## Verify

```
uv run pytest packages/homelib-rag/tests/test_monitoring.py -v
uv run python scripts/demo_traffic.py --n 40
docker compose -f docker/docker-compose.yml exec postgres psql -U homelib -c "select count(*), count(feedback), count(query_plaintext) from query_log;"
curl -su admin:$GRAFANA_PASSWORD localhost:3001/api/search?query=homelib   # dashboard exists
uv run python scripts/check_dashboard.py    # asserts >=5 panels return data via Grafana API
```

## Cost estimate (C1)

`LLM_PRICE_PER_1K_PROMPT` / `LLM_PRICE_PER_1K_COMPLETION` (`.env.example`,
both default `0`) are read the same way every other `LLM_*` var is — at
call time, no settings object. `post_ask` computes `query_log.cost_usd`
(new SQLite migration 5 / Postgres column) from these prices and the same
token counts already logged. 0/0 (the local/Ollama default) means every
request's `cost_usd` is 0, which Observatory's `token_or_cost_estimate`
chart treats as "unpriced" and falls back to summing tokens, exactly as
before C1 shipped.

## Online judge (C6)

Rubric monitoring wants live traffic judged, not just eval fixtures. Two new
nullable `query_log` columns (migration 6 / Postgres): `relevance` (the
judge's own 1-5 sub-score, stored as text — Observatory's `judged_relevance`
chart buckets on it directly) and `judge_model`. Both are written ONLY by
`scripts/judge_recent.py` (`apps.store.judge_ops.judge_recent_rows`), never
by the API itself — "background judging is never triggered by the API in
demo mode" is not a demo-mode-only rule, `/v1/ask` never calls the judge in
any mode.

**Privacy trade-off, stated plainly:** the judge needs the actual question
and answer text, not the sha256 prefix `query_log` normally carries. The new
`answer_log` table (`request_id` PK, `question`, `answer`, `created_at`) is
the one place in this codebase a question's PLAINTEXT is ever persisted, and
it is written ONLY when the operator sets `HOMELIB_LOG_ANSWERS=1` — default
off, so a deployment that never opts in has nothing for
`scripts/judge_recent.py` to read and `answer_log` stays empty. This is a
deliberate, narrow exception to the query-hashing rule above, not a
relaxation of it: nothing else in this codebase reads `answer_log`, and
turning the flag on is a one-line, reversible operator decision, not a
default anyone inherits silently.

`judge_recent_rows` selects `query_log` rows with `relevance IS NULL` that
also have an `answer_log` entry, scores each with `evals.judge.judge`
(imported, not copied) using an empty citations list — `answer_log` does not
persist citations, so `citation_quality` is not meaningfully judged for live
traffic; `relevance` is the score Observatory actually charts. A row the
judge fails to parse is left unjudged (not marked) so a later run retries
it; a row already judged is never re-selected, so re-running the script is
always safe.
