# spec: hybrid — `homelib_rag.hybrid`

**Implemented by:** WP-11. **Consumed by:** `homelib_rag.rerank` (WP-13), `apps/api` `/v1/ask` (WP-14), `evals/retrieval_eval.py` (WP-12).

## Purpose

Merge the two independent rankings from `homelib_rag.index` (`search_lexical`,
`search_vector`) into one ranking that beats either arm alone, using Reciprocal
Rank Fusion — and do it in a way that degrades to a working single arm instead
of failing a request when one backend is unreachable. v2 lexical arm is FTS5
instead of Postgres `tsvector`; the RRF contract does not change. `Hit` is defined in
`specs/indexing.md`; this module only reorders and re-scores it.

## Public interface

```python
def hybrid_search(
    q: str,
    k: int,
    *,
    mode: Literal["hybrid", "lexical", "vector"] = "hybrid",
) -> tuple[list[Hit], str]: ...
```

Returns `(hits, mode_used)`. `mode_used` is the arm that **actually** produced
the returned hits after any degradation — not an echo of the requested `mode`.

## Data contracts (field-level)

`hybrid_search` consumes `list[Hit]` from both arms (see `specs/indexing.md`
for the `Hit` shape) and returns `list[Hit]` with two fields reinterpreted:

- `Hit.score` — the fused RRF score (see formula below), not either arm's raw
  score. Callers must not compare a hybrid `score` against a lexical or vector
  `score`; they are different scales.
- `Hit.rank` — 1-based position in the fused ranking, dense, no gaps.

**RRF formula** (reimplemented from the published definition — Cormack, Clarke
& Buttcher, "Reciprocal Rank Fusion outperforms Condorcet and individual Rank
Learning Methods," SIGIR 2009 — never copied from another repo's
implementation):

```
rrf_score(chunk) = sum over each arm A where chunk appears:
                      1 / (K + rank_A(chunk))
K = 60
```

A chunk missing from one arm's top-k contributes 0 for that arm — it is not
penalized further, not excluded. Fused hits are sorted by `rrf_score`
descending, top `k` returned. **Dedup by `chunk_id`**: a chunk appearing in
both arms appears exactly once in the output, with the summed score; its
`text`/`section_path`/`page` are taken from either arm's `Hit` (they describe
the same chunk, so they agree).

## Error/degradation behavior

- `mode="hybrid"` calls both `search_lexical` and `search_vector`. If
  `search_vector` raises (vector backend unreachable), `hybrid_search` catches
  it, falls back to lexical-only results, and returns `mode_used="lexical"` —
  it does **not** raise, and does **not** silently claim `mode_used="hybrid"`.
- Symmetric case: if `search_lexical` raises, falls back to `mode_used="vector"`.
- If **both** arms raise, `hybrid_search` re-raises the vector arm's exception
  (there is no working arm left to degrade to — this is the only case that
  propagates an exception to the caller).
- `mode="lexical"` or `mode="vector"` calls only that arm; a failure there
  raises directly (no fallback to invent — the caller asked for one arm).
- This module never returns `mode_used="hybrid"` unless both arms actually
  contributed at least one hit each to the fusion.

## Named red tests (write before the code)

- `test_rrf_hand_computed_three_doc_toy_example` — fixed toy case with hand-
  computed expected scores, not framework-generated:
  ```
  lexical ranking:  A(rank=1), B(rank=2), C(rank=3)
  vector  ranking:  B(rank=1), C(rank=2), A(rank=3)
  K = 60
  rrf(A) = 1/61 + 1/63 = 0.0163934426 + 0.0158730159 = 0.0322664585
  rrf(B) = 1/62 + 1/61 = 0.0161290323 + 0.0163934426 = 0.0325224749
  rrf(C) = 1/63 + 1/62 = 0.0158730159 + 0.0161290323 = 0.0320020482
  expected order: B, A, C   (B wins on strength of its rank-1 vector placement)
  ```
  Assert `hybrid_search` (with both arms monkeypatched to return this fixed
  ranking) reproduces this exact order and scores within `1e-9`.
- `test_dedup_by_chunk_id_sums_scores` — a chunk present in both arms appears
  once in the output with `score == rrf contribution from both arms`.
- `test_degrades_to_lexical_when_vector_backend_down` — `search_vector`
  monkeypatched to raise; `hybrid_search(mode="hybrid")` returns non-empty
  hits and `mode_used == "lexical"`, no exception propagates.
- `test_degrades_to_vector_when_lexical_backend_down` — symmetric case.
- `test_raises_when_both_backends_down` — both monkeypatched to raise;
  `hybrid_search` raises.
- `test_single_arm_mode_does_not_fall_back` — `mode="vector"` with
  `search_vector` raising propagates the exception rather than trying lexical.

## Verify

```
uv run pytest packages/homelib-rag/tests/test_hybrid.py -v
uv run python -c "from homelib_rag.hybrid import hybrid_search; hits, mode = hybrid_search('compound interest', 5); print(mode, len(hits))"
```
