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
"""

from collections.abc import Mapping, Sequence

QueryId = str
ChunkId = str

#: query id -> ranked list of result chunk ids, best result first.
RankedResults = Mapping[QueryId, Sequence[ChunkId]]

#: query id -> the chunk id(s) considered relevant to that query.
GroundTruth = Mapping[QueryId, Sequence[ChunkId]]

__all__ = ["ChunkId", "GroundTruth", "QueryId", "RankedResults", "hit_rate_at_k", "mrr_at_k"]


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
