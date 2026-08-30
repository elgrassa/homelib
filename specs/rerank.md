# spec: rerank — `homelib_rag.rerank`

**Implemented by:** WP-13. **Consumed by:** `apps/api` `/v1/ask` (WP-14, `arm="hybrid_rerank"`), `evals/retrieval_eval.py` (WP-12/13).

## Purpose

Improve ranking quality on top of `hybrid_search`'s output using a cross-encoder
that scores `(query, chunk)` pairs jointly — strictly better relevance signal
than the RRF fusion alone, at the cost of one extra model call. The binding
contract is that this quality improvement is optional: if the cross-encoder
model cannot be loaded, the caller falls back to the ranking it already had,
never to an error.

## Public interface

```python
def rerank(q: str, hits: list[Hit]) -> list[Hit] | None: ...
```

`Hit` is defined in `specs/indexing.md`. `rerank` takes the (already deduped,
already fused) output of `hybrid_search` and returns it reordered — or `None`.

## Data contracts (field-level)

- Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`, loaded via
  `sentence_transformers.CrossEncoder`.
- Loading is a **lazy, thread-safe singleton**: the model loads on first call
  to `rerank`, not at import time; concurrent first calls from multiple request
  threads must not race into two loads or a partially-initialized model
  (guard with a `threading.Lock` around the check-then-load).
- Input: `q: str`, `hits: list[Hit]` (order and content irrelevant to the
  cross-encoder — it scores each `(q, hit.text)` pair independently).
- Output on success: `list[Hit]` — same objects, `score` field replaced with
  the cross-encoder's relevance score, `rank` recomputed 1-based dense from
  the new order, `chunk_id`/`book_id`/`text`/`section_path`/`page` unchanged.
  Length and membership are identical to the input; only order and `score`/
  `rank` change.
- Output on failure: **`None`**, not `[]` and not the original list. `None` is
  the caller's signal to keep whatever ranking it already had — `[]` would be
  indistinguishable from "reranked to zero results," which is a different and
  false claim.

## Error/degradation behavior

- Model load failure (missing weights, OOM, import error on `sentence_transformers`,
  any exception during `CrossEncoder(...)` construction) is caught inside
  `rerank`'s singleton-loading path and converted to `rerank(...) -> None` for
  every call for the lifetime of the process — it does not retry-and-raise on
  every request, and it does not raise at all. **A rerank failure must degrade
  ranking quality, never fail a request.**
- An empty `hits` list returns `[]` (there is nothing to rerank, but this is
  not a failure — the model, if loaded, is not even invoked).
- A scoring-time exception (not a load-time one — e.g. the model raises mid-
  batch on a pathological input) is also caught and converted to `None` for
  that call; a transient scoring failure does not poison the singleton for
  later calls the way a load failure does.
- The caller (`apps/api`) contract: `result = rerank(q, hits); use = result if
  result is not None else hits`. This spec does not implement the caller, but
  the caller's behavior is part of what these red tests must exercise from
  the outside via `rerank`'s return value.

## Named red tests (write before the code)

- `test_rerank_returns_none_when_model_load_fails` — monkeypatch
  `CrossEncoder.__init__` to raise; `rerank(q, hits)` returns `None`, not an
  exception, not `[]`.
- `test_rerank_preserves_original_ranking_signal_on_failure` — the degradation
  test: with load failing, simulate the caller's fallback (`result or hits`)
  and assert the hits are in their original `hybrid_search` order — i.e. the
  test asserts the *caller-visible outcome* of degradation, not just the
  return value in isolation.
- `test_rerank_reorders_by_relevance` — behavioural, not string-match: feed a
  query and two fixture chunks where one is obviously more relevant (shares
  the query's topic) and one is a near-random unrelated sentence; with a real
  (or a scripted deterministic fake) cross-encoder, assert the relevant chunk
  ends up at `rank=1` regardless of its input position.
- `test_rerank_output_is_permutation_of_input` — same `chunk_id` set in and
  out, same length, `rank` values dense 1-based.
- `test_rerank_singleton_loads_once_under_concurrent_calls` — spin up several
  threads calling `rerank` simultaneously on first use; assert the model
  constructor was invoked exactly once (mock/count the `CrossEncoder(...)`
  call).
- `test_rerank_empty_hits_returns_empty_list_not_none` — distinguishes "no
  input" from "load failure."

## Verify

```
uv run pytest packages/homelib-rag/tests/test_rerank.py -v
```
