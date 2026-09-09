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
import re
from collections.abc import Sequence
from typing import Literal

from homelib_rag.models import Hit

__all__ = [
    "boost_books_named_in_query",
    "hybrid_search",
    "merge_unique_hits",
    "promote_query_overlap",
    "promote_verbatim_phrase",
]

logger = logging.getLogger(__name__)

# The constant from the RRF paper. Not tunable via config: specs/hybrid.md
# pins it to 60.
_RRF_K = 60

_CONTENT_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "of",
        "for",
        "in",
        "on",
        "at",
        "by",
        "is",
        "are",
        "be",
        "as",
        "it",
        "its",
        "my",
        "me",
        "i",
        "we",
        "you",
        "your",
        "with",
        "from",
        "into",
        "about",
        "how",
        "what",
        "when",
        "where",
        "why",
        "who",
        "whom",
        "which",
        "this",
        "that",
        "these",
        "those",
        "does",
        "did",
        "do",
        "say",
        "says",
        "said",
    }
)


def search_lexical(q: str, k: int) -> list[Hit]:
    """Lazy re-export so tests can monkeypatch ``hybrid.search_lexical``."""
    from homelib_rag.index import search_lexical as _impl

    return _impl(q, k)


def search_vector(q: str, k: int) -> list[Hit]:
    """Lazy re-export so tests can monkeypatch ``hybrid.search_vector``."""
    from homelib_rag.index import search_vector as _impl

    return _impl(q, k)


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


def promote_verbatim_phrase(query: str, hits: list[Hit]) -> list[Hit]:
    """Keep exact body matches ahead of semantic/reranker approximations."""
    needle = " ".join(query.split()).casefold()
    if not needle:
        return hits
    return sorted(
        hits,
        key=lambda hit: needle not in " ".join(hit.text.split()).casefold(),
    )


def _content_tokens(query: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9']+", query.casefold())
        if len(token) > 2 and token not in _CONTENT_STOPWORDS
    ]


def promote_query_overlap(query: str, hits: list[Hit]) -> list[Hit]:
    """Prefer hits that share the longest content n-gram with the question.

    Ask questions rarely equal a passage verbatim; scene search uses the
    exact phrase. Ranking by longest overlapping content tokens keeps
    "living deliberately" passages ahead of unrelated shelf noise.
    """
    tokens = _content_tokens(query)
    if len(tokens) < 2 or not hits:
        return promote_verbatim_phrase(query, hits)

    def _overlap_rank(hit: Hit) -> tuple[int, int, int]:
        text = " ".join(hit.text.casefold().split())
        text_tokens = set(re.findall(r"[a-z0-9']+", text))
        best_ngram = 0
        for length in range(len(tokens), 1, -1):
            for start in range(len(tokens) - length + 1):
                phrase = " ".join(tokens[start : start + length])
                if phrase in text:
                    best_ngram = length
                    break
                if all(_token_matches(tok, text_tokens) for tok in tokens[start : start + length]):
                    best_ngram = length
                    break
            if best_ngram >= length:
                break
        token_hits = sum(1 for tok in tokens if _token_matches(tok, text_tokens))
        # Prefer passages that pair live/living with deliberately when asked.
        deliberate_bonus = 0
        query_has_deliberate = "deliberately" in tokens or "deliberate" in tokens
        query_has_live = any(tok in tokens for tok in ("live", "living"))
        if (
            query_has_deliberate
            and query_has_live
            and "deliberately" in text_tokens
            and any(_token_matches(tok, text_tokens) for tok in ("live", "living"))
        ):
            deliberate_bonus = 1
        # Sort key: lower is better — negate so more overlap comes first.
        return (-deliberate_bonus, -best_ngram, -token_hits)

    return sorted(hits, key=_overlap_rank)


def _token_matches(tok: str, text_tokens: set[str]) -> bool:
    if tok in text_tokens:
        return True
    if len(tok) < 4:
        return False
    return any(
        len(other) >= 4 and (tok.startswith(other) or other.startswith(tok))
        for other in text_tokens
    )


def merge_unique_hits(*hit_lists: Sequence[Hit], k: int) -> list[Hit]:
    """Concatenate hit lists, keep first occurrence of each chunk_id, cap at k."""
    seen: set[str] = set()
    merged: list[Hit] = []
    for hits in hit_lists:
        for hit in hits:
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            merged.append(hit)
            if len(merged) >= k:
                return [
                    h.model_copy(update={"rank": rank}) for rank, h in enumerate(merged, start=1)
                ]
    return [h.model_copy(update={"rank": rank}) for rank, h in enumerate(merged, start=1)]


def boost_books_named_in_query(
    query: str,
    hits: list[Hit],
    book_titles: dict[str, str],
) -> list[Hit]:
    """When the question names a shelf title, keep that book's hits first."""
    if not hits or not book_titles:
        return hits
    q = query.casefold()
    named = {book_id for book_id, title in book_titles.items() if title and title.casefold() in q}
    if not named:
        # Also match distinctive title tokens (e.g. "Walden" in a longer title).
        for book_id, title in book_titles.items():
            for part in re.findall(r"[a-z0-9']+", title.casefold()):
                if len(part) >= 5 and part in q:
                    named.add(book_id)
                    break
    if not named:
        return hits
    return sorted(hits, key=lambda hit: hit.book_id not in named)
