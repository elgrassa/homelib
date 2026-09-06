"""Reciprocal Rank Fusion over the lexical and vector search arms — see specs/hybrid.md.

Merges the two independent rankings from `homelib_rag.index` (`search_lexical`,
`search_vector`) into one, using Reciprocal Rank Fusion (RRF), and degrades to
a single working arm instead of failing a request when one backend is
unreachable.

RRF formula, reimplemented directly from the published definition — Cormack,
Clarke & Buttcher, "Reciprocal Rank Fusion outperforms Condorcet and
individual Rank Learning Methods," SIGIR 2009 — never copied from another
repo's implementation:

    rrf_score(chunk) = sum over each arm A where chunk appears in that arm's
                        top-k: 1 / (K + rank_A(chunk))
    K = 60

A chunk missing from one arm's top-k simply contributes 0 for that arm — it
is not penalized further, not excluded.

`K` ships as 60 (the value the RRF paper's authors settled on and this
project's production default), but it is a keyword-only `rrf_k` parameter on
`hybrid_search`/`_hybrid`/`_fuse` rather than a hardcoded constant, so
`evals/retrieval_eval.py --rrf-k` can sweep it for `evals/results/retrieval.md`'s
"RRF k sweep" table without touching production call sites (which never pass
`rrf_k` and therefore keep getting 60).
"""

from __future__ import annotations

import logging
from typing import Literal

from homelib_rag.index import search_lexical, search_vector
from homelib_rag.models import Hit

__all__ = ["hybrid_search"]

logger = logging.getLogger(__name__)

# The constant from the RRF paper. Not tunable via config: specs/hybrid.md
# pins it to 60.
_RRF_K = 60


def hybrid_search(
    q: str,
    k: int,
    *,
    mode: Literal["hybrid", "lexical", "vector"] = "hybrid",
    rrf_k: int = _RRF_K,
) -> tuple[list[Hit], str]:
    """Search `q`, returning `(hits, mode_used)`.

    `mode="lexical"` or `mode="vector"` calls only that arm; a failure there
    raises directly — the caller asked for one specific arm, so there is
    nothing to fall back to. `rrf_k` is unused in that case: there is no
    fusion to tune.

    `mode="hybrid"` (the default) calls both arms and fuses them with RRF,
    using `rrf_k` as the fusion constant `K` (default 60, matching
    production and the RRF paper). If one arm raises, `hybrid_search` catches
    it and degrades to the other arm alone, returning its raw hits and
    `mode_used` set to that arm's name — it never raises for a single-arm
    failure. If *both* arms raise, there is no working arm to degrade to, so
    `hybrid_search` re-raises the vector arm's exception.

    `mode_used` is always the arm that actually produced the returned hits,
    never an echo of the requested `mode`.
    """
    if mode == "lexical":
        return search_lexical(q, k), "lexical"
    if mode == "vector":
        return search_vector(q, k), "vector"
    return _hybrid(q, k, rrf_k)


def _hybrid(q: str, k: int, rrf_k: int = _RRF_K) -> tuple[list[Hit], str]:
    lexical_hits: list[Hit] = []
    vector_hits: list[Hit] = []
    lexical_ok = False
    vector_ok = False
    vector_exc: Exception | None = None

    try:
        lexical_hits = search_lexical(q, k)
        lexical_ok = True
    except Exception as exc:  # degrade to the other arm, don't crash the request
        logger.warning("lexical arm failed in hybrid_search: %s", exc)

    try:
        vector_hits = search_vector(q, k)
        vector_ok = True
    except Exception as exc:  # degrade to the other arm, don't crash the request
        logger.warning("vector arm failed in hybrid_search: %s", exc)
        vector_exc = exc

    if not lexical_ok and not vector_ok:
        # No working arm left to degrade to. The vector exception is the one
        # that propagates, per specs/hybrid.md.
        assert vector_exc is not None
        raise vector_exc
    if not vector_ok:
        return lexical_hits, "lexical"
    if not lexical_ok:
        return vector_hits, "vector"
    return _fuse(lexical_hits, vector_hits, k, rrf_k), "hybrid"


def _fuse(
    lexical_hits: list[Hit], vector_hits: list[Hit], k: int, rrf_k: int = _RRF_K
) -> list[Hit]:
    """Reciprocal-Rank-Fuse two arms' hits, dedup by `chunk_id`, top `k`.

    Each arm's own `Hit.rank` (its 1-based position in that arm's ranking) is
    the `rank_A(chunk)` the RRF formula uses — not a position recomputed here.
    A chunk present in both arms is deduped: its contributions are summed and
    it appears once in the output, with `text`/`section_path`/`page` taken
    from whichever arm's `Hit` was seen first (they describe the same chunk,
    so both arms agree on those fields). `rrf_k` defaults to the production
    constant so every existing call site (e.g. `homelib_rag.scene_search`,
    which calls this positionally without `rrf_k`) keeps behaving identically.
    """
    scores: dict[str, float] = {}
    hit_by_id: dict[str, Hit] = {}
    for arm_hits in (lexical_hits, vector_hits):
        for hit in arm_hits:
            contribution = 1.0 / (rrf_k + hit.rank)
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + contribution
            hit_by_id.setdefault(hit.chunk_id, hit)

    ordered_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [
        hit_by_id[chunk_id].model_copy(update={"score": scores[chunk_id], "rank": rank})
        for rank, chunk_id in enumerate(ordered_ids[:k], start=1)
    ]
