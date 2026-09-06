"""Retrieval-quality metrics — see specs/evals-retrieval.md.

Reimplemented from first principles against the published definitions below,
never derived from (or copied out of) any retrieval/index code under test —
so a bug in a ranking implementation cannot also be the bug in its own eval.
This module was written without reading any prior implementation on this
machine; in particular `CapstoneMealMapSimplified/` and
`MealMaster/ai/week1-rag/` were never consulted.

Both metrics score a batch of queries. For each query there is a ranked list
of result chunk ids (`RankedResults[query]`, best first) and a set of chunk
ids considered relevant to that query (`GroundTruth[query]`, one or more).

- **hit-rate@k** — for one query, 1 if *any* relevant id appears anywhere in
  the first `k` entries of that query's ranked results, else 0. Overall
  hit-rate@k is the mean of that indicator across all queries.
- **MRR@k** (Mean Reciprocal Rank) — for one query, `1 / rank` where `rank`
  (1-based) is the position of the *first* relevant id within the first `k`
  entries of the ranked results, else 0 if no relevant id appears in that
  window. Overall MRR@k is the mean of that value across all queries.

Both metrics agree (and equal 1.0) when every query's first hit is at rank 1;
they diverge whenever a hit exists but is not at rank 1 — hit-rate still
counts it fully, MRR discounts it by `1/rank`.

- **hit-rate-book@k** — the book-level counterpart of hit-rate@k: for one
  query, 1 if the top-`k` results include *any* chunk from the same book as
  a relevant id, else 0, averaged over all queries. It exists because
  hit-rate@k is single-positive and chunk-exact — a neighbouring chunk from
  the correct book, carrying equally relevant prose, scores as a total miss
  (see `docs/adrs/ADR-001-retrieval-arm.md`, "correct book in top-5"). Same
  contract as `hit_rate_at_k` (same `ValueError`s, same missing-query and
  duplicate-id handling) — it is literally the same computation over a
  different id space (book ids instead of chunk ids), so it is implemented
  by calling `hit_rate_at_k` with book ids substituted for chunk ids at the
  caller's boundary, not reimplemented.
"""

from collections.abc import Mapping, Sequence

QueryId = str
ChunkId = str
BookId = str

#: query id -> ranked list of result chunk ids, best result first.
RankedResults = Mapping[QueryId, Sequence[ChunkId]]

#: query id -> the chunk id(s) considered relevant to that query.
GroundTruth = Mapping[QueryId, Sequence[ChunkId]]

#: query id -> ranked list of the *book* id each result chunk belongs to,
#: same order and length as the chunk-id ranking it was derived from.
RankedBooks = Mapping[QueryId, Sequence[BookId]]

#: query id -> the book id(s) considered relevant to that query (normally
#: the single book the ground-truth chunk belongs to).
GroundTruthBooks = Mapping[QueryId, Sequence[BookId]]

__all__ = [
    "BookId",
    "ChunkId",
    "GroundTruth",
    "GroundTruthBooks",
    "QueryId",
    "RankedBooks",
    "RankedResults",
    "hit_rate_at_k",
    "hit_rate_book",
    "mrr_at_k",
]


def _validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError(f"k must be a positive integer, got {k}")


def _validate_relevant(relevant: GroundTruth) -> None:
    if not relevant:
        raise ValueError("relevant mapping is empty — scoring zero queries is a bug, not a 0.0")


def _first_relevant_rank(topk: Sequence[ChunkId], relevant_set: set[ChunkId]) -> int | None:
    """1-based rank of the first id in `topk` that is in `relevant_set`, or None."""
    for position, chunk_id in enumerate(topk, start=1):
        if chunk_id in relevant_set:
            return position
    return None


def hit_rate_at_k(results: RankedResults, relevant: GroundTruth, k: int) -> float:
    """Fraction of queries in `relevant` with a hit in the top `k` of `results`.

    A query missing from `results` (or whose ranked list is `[]`) is treated
    as an empty ranking — a guaranteed miss, not an error. Duplicate ids in a
    ranking do not change hit-rate: it only asks whether a relevant id is
    present anywhere in the window. Raises `ValueError` if `k <= 0` or if
    `relevant` has no queries to score.
    """
    _validate_k(k)
    _validate_relevant(relevant)

    hits = 0
    for query, relevant_ids in relevant.items():
        relevant_set = set(relevant_ids)
        topk = results.get(query, ())[:k]
        if any(chunk_id in relevant_set for chunk_id in topk):
            hits += 1
    return hits / len(relevant)


def mrr_at_k(results: RankedResults, relevant: GroundTruth, k: int) -> float:
    """Mean reciprocal rank, over queries in `relevant`, within the top `k` of `results`.

    A query missing from `results` (or whose ranked list is `[]`) contributes
    0.0, same as a query whose relevant id(s) never appear in the top `k`.
    When a ranking contains duplicate ids, the *first* occurrence determines
    the rank. Raises `ValueError` if `k <= 0` or if `relevant` has no queries
    to score.
    """
    _validate_k(k)
    _validate_relevant(relevant)

    total = 0.0
    for query, relevant_ids in relevant.items():
        relevant_set = set(relevant_ids)
        topk = results.get(query, ())[:k]
        rank = _first_relevant_rank(topk, relevant_set)
        total += 1.0 / rank if rank is not None else 0.0
    return total / len(relevant)


def hit_rate_book(results: RankedBooks, relevant: GroundTruthBooks, k: int) -> float:
    """Book-level hit-rate@k: a hit if any of the top-`k` results' book ids
    matches a relevant book id, regardless of which chunk within that book.

    Signature and semantics deliberately mirror `hit_rate_at_k` exactly —
    `results`/`relevant` are keyed the same way, just carrying book ids
    instead of chunk ids — so this delegates to it rather than duplicating
    the membership/empty/duplicate-id logic. The caller is responsible for
    projecting a chunk-id ranking into the matching book-id ranking (e.g.
    `[hit.book_id for hit in ranked_hits]`); see
    `evals/retrieval_eval.py`'s `QueryOutcome.ranked_book_ids`.
    """
    return hit_rate_at_k(results, relevant, k)
