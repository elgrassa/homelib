# spec: rewrite — `homelib_rag.rewrite`

**Implemented by:** WP-13. **Consumed by:** `apps/api` `/v1/ask` (WP-14, `AskRequest.rewrite`, default `false` per ADR-001), `evals/retrieval_eval.py` (rewrite on/off arms).

## Purpose

A user's natural-language question is often a worse search string than a
rewritten, retrieval-shaped version of it (expanded acronyms, dropped filler,
explicit key terms). `rewrite_query` asks an LLM to produce that rewritten
string before it reaches `hybrid_search`. This is **net-new code, not a
wrapper around an existing query-rewriting library** — the prompt, the typed
output contract, and the fail-closed parsing here are homelib's own, written
against the LLM client the same way `roadmap.py` (WP-14) is, not pulled from
LangChain or any retrieval framework's built-in rewriter. That is the
best-practice point this module earns.

## Public interface

```python
def rewrite_query(q: str) -> str: ...
```

Always returns a non-empty `str` usable directly as input to `hybrid_search`.

## Data contracts (field-level)

- Internal typed output the LLM is asked to produce (Pydantic model, not
  exposed publicly — `rewrite_query`'s return type is plain `str`):
  ```
  RewriteResult   rewritten_query: str    # non-empty after strip
  ```
- The LLM call requests structured output (JSON mode / tool-call schema,
  matching the same client pattern as `roadmap.py`) so parsing is `RewriteResult
  .model_validate_json(response)`, not regex-scraping free text.
- `rewrite_query`'s contract: on success, `RewriteResult.rewritten_query`
  (stripped) is returned. On **any** failure, the original `q` (unmodified,
  not even stripped) is returned.

## Error/degradation behavior

**Fail-closed by construction: every failure mode returns the original `q`
unchanged, never raises, never returns an empty string, never returns a
partially-parsed guess.** Enumerated failure modes and their handling:

- LLM backend unreachable (connection error, timeout) → catch, return `q`.
- LLM returns non-JSON or JSON that doesn't validate against `RewriteResult`
  (unparseable output) → catch the validation error, return `q`.
- LLM returns valid JSON but `rewritten_query` is empty or whitespace-only
  (empty result) → treated as a failure, return `q`, not the empty string.
- LLM call succeeds but takes longer than a configured timeout → treated the
  same as unreachable, return `q`.
- Any other unexpected exception inside `rewrite_query` is caught at the
  function boundary — this function has no exception it lets propagate to the
  caller. `hybrid_search`/`apps/api` never need a try/except around
  `rewrite_query`.
- No retry-then-raise: unlike `roadmap.py`'s bounded repair retry (which is
  allowed one retry before failing closed), `rewrite_query` degrades to `q`
  immediately on first failure — a slow retrieval-quality miss is preferable
  to added latency on every question for a non-critical rewrite step.

## Named red tests (write before the code)

- `test_rewrite_returns_original_query_on_unparseable_llm_output` — the
  fail-closed test: LLM client mocked to return garbage (`"not json at all"`);
  `rewrite_query(q) == q` exactly.
- `test_rewrite_returns_original_query_when_llm_unreachable` — LLM client
  mocked to raise a connection error; `rewrite_query(q) == q`.
- `test_rewrite_returns_original_query_on_empty_result` — LLM client mocked to
  return valid JSON with `rewritten_query: ""`; `rewrite_query(q) == q`, not
  `""`.
- `test_rewrite_returns_rewritten_query_on_success` — LLM client mocked to
  return a valid, non-empty, different rewrite; `rewrite_query(q)` returns
  that rewrite, not `q`.
- `test_rewrite_never_raises` — property-style test feeding several malformed
  mock responses (missing field, wrong type, `None`, truncated JSON) through
  `rewrite_query` and asserting none of them raise out of the function.
- `test_rewrite_does_not_mutate_input_string` — `q` passed in is unchanged by
  the call (guards against accidental in-place normalization masquerading as
  the fallback path).

## Verify

```
uv run pytest packages/homelib-rag/tests/test_rewrite.py -v
```
