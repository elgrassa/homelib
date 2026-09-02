"""Red tests for `homelib_rag.rerank` — see specs/rerank.md.

The cross-encoder itself is always stubbed here (`monkeypatch.setattr(
rerank_module, "CrossEncoder", ...)`); nothing in this file downloads a model
or does real inference. A test against the real
`cross-encoder/ms-marco-MiniLM-L-6-v2` model would belong under
`@pytest.mark.slow`, but none is included — the fakes below are deterministic
and exercise the same code paths.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator, Sequence

import pytest
from homelib_rag import rerank as rerank_module
from homelib_rag.models import Hit
from homelib_rag.rerank import rerank


def _hit(chunk_id: str, text: str, *, rank: int, score: float = 0.5) -> Hit:
    return Hit(
        chunk_id=chunk_id,
        book_id="book-1",
        score=score,
        rank=rank,
        text=text,
        section_path=["Chapter 1"],
        page=1,
    )


class _RaisingCrossEncoder:
    """Stand-in whose construction always fails, like a missing-weights load."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated model load failure")


class _FakeCrossEncoder:
    """Deterministic stand-in: scores a pair 1.0 if `text` mentions "bees"."""

    call_count = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        type(self).call_count += 1

    def predict(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        return [1.0 if "bees" in text else 0.0 for _q, text in pairs]


class _ScoringFailsOnceCrossEncoder:
    """Loads fine; the first `predict` call raises, later calls succeed."""

    call_count = 0
    predict_calls = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        type(self).call_count += 1

    def predict(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        type(self).predict_calls += 1
        if type(self).predict_calls == 1:
            raise RuntimeError("simulated scoring failure")
        return [1.0 for _ in pairs]


@pytest.fixture(autouse=True)
def _reset_rerank_state() -> Iterator[None]:
    """Every test starts (and ends) with a clean process-wide singleton."""
    rerank_module._reset_singleton_for_tests()
    _FakeCrossEncoder.call_count = 0
    _ScoringFailsOnceCrossEncoder.call_count = 0
    _ScoringFailsOnceCrossEncoder.predict_calls = 0
    yield
    rerank_module._reset_singleton_for_tests()


# ── named red tests (per the WP-13 task brief) ──────────────────────────────


def test_rerank_returns_none_when_model_load_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _RaisingCrossEncoder)
    hits = [_hit("c1", "irrelevant text", rank=1), _hit("c2", "other text", rank=2)]

    result = rerank("some query", hits)

    assert result is None
    # a caller keeping the original order is demonstrated explicitly:
    used = result if result is not None else hits
    assert used is hits
    assert [h.chunk_id for h in used] == ["c1", "c2"]


def test_rerank_reorders_by_cross_encoder_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _FakeCrossEncoder)
    hits = [
        _hit("irrelevant", "totally unrelated filler sentence", rank=1),
        _hit("relevant", "bees are essential pollinators", rank=2),
    ]

    result = rerank("bees and pollination", hits)

    assert result is not None
    assert [h.chunk_id for h in result] == ["relevant", "irrelevant"]
    assert [h.rank for h in result] == [1, 2]
    assert result[0].score == 1.0
    assert result[1].score == 0.0


def test_rerank_singleton_loads_once_under_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _FakeCrossEncoder)
    hits = [_hit("c1", "bees", rank=1), _hit("c2", "no match", rank=2)]

    n_threads = 8
    barrier = threading.Barrier(n_threads)
    results: list[list[Hit] | None] = [None] * n_threads

    def _call(i: int) -> None:
        barrier.wait()
        results[i] = rerank("bees", hits)

    threads = [threading.Thread(target=_call, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert _FakeCrossEncoder.call_count == 1
    assert all(r is not None for r in results)


# ── remaining named red tests from specs/rerank.md ──────────────────────────


def test_rerank_failure_preserves_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _RaisingCrossEncoder)
    original = [_hit("c1", "first", rank=1), _hit("c2", "second", rank=2)]

    result = rerank("some query", original)
    used = result if result is not None else original

    assert used == original
    assert [h.chunk_id for h in used] == ["c1", "c2"]


def test_rerank_preserves_original_ranking_signal_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _RaisingCrossEncoder)
    original = [_hit("c1", "first", rank=1), _hit("c2", "second", rank=2)]

    result = rerank("some query", original)
    used = result if result is not None else original

    assert used == original
    assert [h.chunk_id for h in used] == ["c1", "c2"]


def test_rerank_reorders_by_relevance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _FakeCrossEncoder)
    hits = [
        _hit("irrelevant", "a sentence about something else entirely", rank=1),
        _hit("relevant", "bees pollinate flowering plants", rank=2),
    ]

    result = rerank("how do bees pollinate flowers", hits)

    assert result is not None
    assert result[0].chunk_id == "relevant"
    assert result[0].rank == 1
    assert result[1].chunk_id == "irrelevant"
    assert result[1].rank == 2


def test_rerank_output_is_permutation_of_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _FakeCrossEncoder)
    hits = [_hit(f"c{i}", f"text {i} bees" if i % 2 else f"text {i}", rank=i) for i in range(1, 6)]

    result = rerank("bees", hits)

    assert result is not None
    assert len(result) == len(hits)
    assert {h.chunk_id for h in result} == {h.chunk_id for h in hits}
    assert [h.rank for h in result] == list(range(1, len(hits) + 1))


def test_rerank_singleton_loads_once_under_concurrent_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _FakeCrossEncoder)
    hits = [_hit("c1", "bees", rank=1)]

    n_threads = 5
    barrier = threading.Barrier(n_threads)

    def _call() -> None:
        barrier.wait()
        rerank("bees", hits)

    threads = [threading.Thread(target=_call) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert _FakeCrossEncoder.call_count == 1


def test_rerank_empty_hits_returns_empty_list_not_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _FakeCrossEncoder)

    result = rerank("anything", [])

    assert result == []
    assert result is not None
    assert _FakeCrossEncoder.call_count == 0  # model never even touched


# ── extra coverage: singleton reuse + non-poisoning on scoring failure ──────


def test_rerank_reuses_loaded_model_on_subsequent_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _FakeCrossEncoder)
    hits = [_hit("c1", "bees", rank=1)]

    rerank("bees", hits)
    rerank("bees", hits)

    assert _FakeCrossEncoder.call_count == 1


def test_rerank_scoring_exception_returns_none_without_poisoning_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rerank_module, "CrossEncoder", _ScoringFailsOnceCrossEncoder)
    hits = [_hit("c1", "text", rank=1)]

    first = rerank("q", hits)
    second = rerank("q", hits)

    assert first is None
    assert second is not None
    assert _ScoringFailsOnceCrossEncoder.call_count == 1  # loaded once, not reloaded
