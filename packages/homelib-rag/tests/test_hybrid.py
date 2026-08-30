"""Red tests for `homelib_rag.hybrid` — see specs/hybrid.md.

`search_lexical` and `search_vector` are monkeypatched directly on the
`homelib_rag.hybrid` module in every test below (per specs/hybrid.md: "with
both arms monkeypatched to return this fixed ranking"), so nothing here
touches a live Postgres or downloads an embedding model. `hybrid.py` imports
both names into its own namespace (`from homelib_rag.index import
search_lexical, search_vector`), so patching them there — not on
`homelib_rag.index` — is what actually takes effect.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from homelib_rag import hybrid as hybrid_module
from homelib_rag.hybrid import hybrid_search
from homelib_rag.models import Hit

_RRF_K = 60  # the constant pinned by specs/hybrid.md


def _hit(chunk_id: str, *, rank: int, book_id: str = "book-1") -> Hit:
    """A `Hit` as one arm would return it — `score` is that arm's raw score,
    irrelevant to RRF, which only uses `rank`.
    """
    return Hit(
        chunk_id=chunk_id,
        book_id=book_id,
        score=0.5,
        rank=rank,
        text=f"text for {chunk_id}",
        section_path=["Chapter 1"],
        page=1,
    )


def _returning(hits: list[Hit]) -> Callable[[str, int], list[Hit]]:
    def _fn(q: str, k: int) -> list[Hit]:
        return hits

    return _fn


def _raising(exc: Exception) -> Callable[[str, int], list[Hit]]:
    def _fn(q: str, k: int) -> list[Hit]:
        raise exc

    return _fn


# ── named red tests (per the WP-11 task brief / specs/hybrid.md) ────────────


def test_rrf_hand_computed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixed 3-document toy case, arithmetic pinned in the comment below.

    lexical ranking:  A(rank=1), B(rank=2), C(rank=3)
    vector  ranking:  B(rank=1), C(rank=2), A(rank=3)
    K = 60
    rrf(A) = 1/61 + 1/63 = 0.0163934426 + 0.0158730159 = 0.0322664585
    rrf(B) = 1/62 + 1/61 = 0.0161290323 + 0.0163934426 = 0.0325224749
    rrf(C) = 1/63 + 1/62 = 0.0158730159 + 0.0161290323 = 0.0320020482
    expected order: B, A, C   (B wins on strength of its rank-1 vector placement)
    """
    lexical_hits = [_hit("A", rank=1), _hit("B", rank=2), _hit("C", rank=3)]
    vector_hits = [_hit("B", rank=1), _hit("C", rank=2), _hit("A", rank=3)]
    monkeypatch.setattr(hybrid_module, "search_lexical", _returning(lexical_hits))
    monkeypatch.setattr(hybrid_module, "search_vector", _returning(vector_hits))

    hits, mode_used = hybrid_search("q", 3)

    assert mode_used == "hybrid"
    assert [h.chunk_id for h in hits] == ["B", "A", "C"]
    expected_scores = {
        "A": 1 / 61 + 1 / 63,
        "B": 1 / 62 + 1 / 61,
        "C": 1 / 63 + 1 / 62,
    }
    for hit in hits:
        assert hit.score == pytest.approx(expected_scores[hit.chunk_id], abs=1e-9)
    assert [h.rank for h in hits] == [1, 2, 3]


def test_hybrid_dedupes_by_chunk_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A chunk found by both arms appears once, with both contributions summed."""
    lexical_hits = [_hit("shared", rank=1), _hit("lex-only", rank=2)]
    vector_hits = [_hit("vec-only", rank=1), _hit("shared", rank=2)]
    monkeypatch.setattr(hybrid_module, "search_lexical", _returning(lexical_hits))
    monkeypatch.setattr(hybrid_module, "search_vector", _returning(vector_hits))

    hits, mode_used = hybrid_search("q", 10)

    assert mode_used == "hybrid"
    chunk_ids = [h.chunk_id for h in hits]
    assert chunk_ids.count("shared") == 1
    shared_hit = next(h for h in hits if h.chunk_id == "shared")
    expected_shared_score = 1 / (_RRF_K + 1) + 1 / (_RRF_K + 2)
    assert shared_hit.score == pytest.approx(expected_shared_score, abs=1e-9)
    assert set(chunk_ids) == {"shared", "lex-only", "vec-only"}


def test_hybrid_falls_back_to_lexical_when_vector_down(monkeypatch: pytest.MonkeyPatch) -> None:
    lexical_hits = [_hit("A", rank=1), _hit("B", rank=2)]
    monkeypatch.setattr(hybrid_module, "search_lexical", _returning(lexical_hits))
    monkeypatch.setattr(
        hybrid_module, "search_vector", _raising(ConnectionError("vector backend down"))
    )

    hits, mode_used = hybrid_search("q", 5)

    assert mode_used == "lexical"
    assert hits == lexical_hits


def test_hybrid_falls_back_to_vector_when_lexical_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Symmetric case to the lexical-down test above."""
    vector_hits = [_hit("A", rank=1), _hit("B", rank=2)]
    monkeypatch.setattr(
        hybrid_module, "search_lexical", _raising(ConnectionError("lexical backend down"))
    )
    monkeypatch.setattr(hybrid_module, "search_vector", _returning(vector_hits))

    hits, mode_used = hybrid_search("q", 5)

    assert mode_used == "vector"
    assert hits == vector_hits


def test_both_backends_down_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    lexical_exc = RuntimeError("lexical backend down")
    vector_exc = RuntimeError("vector backend down")
    monkeypatch.setattr(hybrid_module, "search_lexical", _raising(lexical_exc))
    monkeypatch.setattr(hybrid_module, "search_vector", _raising(vector_exc))

    with pytest.raises(RuntimeError) as exc_info:
        hybrid_search("q", 5)

    # The vector arm's exception is the one that propagates, per specs/hybrid.md.
    assert exc_info.value is vector_exc


def test_hits_are_rank_ordered_and_capped_at_k_lexical_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lexical-only mode: at most k, best-first, rank 1-based and dense."""
    lexical_hits = [_hit(f"c{i}", rank=i) for i in range(1, 4)]
    monkeypatch.setattr(hybrid_module, "search_lexical", _returning(lexical_hits))

    hits, mode_used = hybrid_search("q", 3, mode="lexical")

    assert mode_used == "lexical"
    assert len(hits) <= 3
    assert [h.rank for h in hits] == list(range(1, len(hits) + 1))
    assert [h.chunk_id for h in hits] == ["c1", "c2", "c3"]


def test_hits_are_rank_ordered_and_capped_at_k_vector_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vector-only mode: at most k, best-first, rank 1-based and dense."""
    vector_hits = [_hit(f"c{i}", rank=i) for i in range(1, 4)]
    monkeypatch.setattr(hybrid_module, "search_vector", _returning(vector_hits))

    hits, mode_used = hybrid_search("q", 3, mode="vector")

    assert mode_used == "vector"
    assert len(hits) <= 3
    assert [h.rank for h in hits] == list(range(1, len(hits) + 1))
    assert [h.chunk_id for h in hits] == ["c1", "c2", "c3"]


def test_hits_are_rank_ordered_and_capped_at_k_hybrid_fusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fused hybrid output: capped at k, best-first, rank 1-based and dense."""
    lexical_hits = [_hit(f"lex{i}", rank=i) for i in range(1, 6)]
    vector_hits = [_hit(f"vec{i}", rank=i) for i in range(1, 6)]
    monkeypatch.setattr(hybrid_module, "search_lexical", _returning(lexical_hits))
    monkeypatch.setattr(hybrid_module, "search_vector", _returning(vector_hits))

    hits, mode_used = hybrid_search("q", 4)

    assert mode_used == "hybrid"
    assert len(hits) == 4  # capped, even though 10 distinct chunk_ids exist
    assert [h.rank for h in hits] == [1, 2, 3, 4]
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)  # best-first


# ── remaining named red tests from specs/hybrid.md ───────────────────────────


def test_single_arm_mode_does_not_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """`mode="vector"` with `search_vector` raising propagates, no fallback."""
    exc = ConnectionError("vector backend down")
    monkeypatch.setattr(hybrid_module, "search_vector", _raising(exc))
    # If a fallback happened, this would be called — it must not be.
    monkeypatch.setattr(
        hybrid_module,
        "search_lexical",
        _raising(AssertionError("search_lexical must not be called in mode='vector'")),
    )

    with pytest.raises(ConnectionError):
        hybrid_search("q", 5, mode="vector")


def test_single_lexical_mode_does_not_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Symmetric case: `mode="lexical"` with `search_lexical` raising propagates."""
    exc = ConnectionError("lexical backend down")
    monkeypatch.setattr(hybrid_module, "search_lexical", _raising(exc))
    monkeypatch.setattr(
        hybrid_module,
        "search_vector",
        _raising(AssertionError("search_vector must not be called in mode='lexical'")),
    )

    with pytest.raises(ConnectionError):
        hybrid_search("q", 5, mode="lexical")


def test_missing_from_one_arm_contributes_zero_not_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A chunk in only one arm's top-k is still included, scored on that arm alone."""
    lexical_hits = [_hit("only-in-lexical", rank=1)]
    vector_hits = [_hit("only-in-vector", rank=1)]
    monkeypatch.setattr(hybrid_module, "search_lexical", _returning(lexical_hits))
    monkeypatch.setattr(hybrid_module, "search_vector", _returning(vector_hits))

    hits, mode_used = hybrid_search("q", 10)

    assert mode_used == "hybrid"
    by_id = {h.chunk_id: h for h in hits}
    assert by_id["only-in-lexical"].score == pytest.approx(1 / (_RRF_K + 1), abs=1e-9)
    assert by_id["only-in-vector"].score == pytest.approx(1 / (_RRF_K + 1), abs=1e-9)
