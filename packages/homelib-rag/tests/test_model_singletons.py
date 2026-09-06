"""C9 speed confirmation: the embedder and cross-encoder load once per
process — see specs/rerank.md, specs/indexing.md.

`homelib_rag.index._load_embedder` and `homelib_rag.rerank._load_model` are
each a lazy, lock-guarded singleton (check-then-load, reused after the first
call); `test_index.py`/`test_rerank.py` already cover each singleton's own
behaviour in isolation (identity across calls, thread-safety, non-poisoning
on a scoring failure). This file adds the one behavioural assertion neither
covers directly: the *model constructor itself* is invoked exactly once
across two calls to `search_vector`/`rerank`, for both models in the same
test — the actual claim this repo makes about real-usage latency (cold vs.
warm), not just object identity.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import pytest
from homelib_rag import index as index_module
from homelib_rag import rerank as rerank_module
from homelib_rag.models import Hit
from homelib_rag.rerank import rerank


class _CountingFakeEmbedder:
    call_count = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        type(self).call_count += 1

    def encode(self, _q: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class _CountingFakeCrossEncoder:
    call_count = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        type(self).call_count += 1

    def predict(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        return [0.5 for _ in pairs]


def _hit(chunk_id: str, *, rank: int) -> Hit:
    return Hit(
        chunk_id=chunk_id,
        book_id="book-1",
        score=0.0,
        rank=rank,
        text=f"text for {chunk_id}",
        section_path=["Chapter 1"],
        page=1,
    )


@pytest.fixture(autouse=True)
def _reset_model_singletons() -> Iterator[None]:
    index_module._reset_embedder_for_tests()
    rerank_module._reset_singleton_for_tests()
    _CountingFakeEmbedder.call_count = 0
    _CountingFakeCrossEncoder.call_count = 0
    yield
    index_module._reset_embedder_for_tests()
    rerank_module._reset_singleton_for_tests()


def test_models_load_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two `_embed_query` calls construct the sentence embedder once; two
    `rerank` calls construct the cross-encoder once. Both loads are lazy
    (nothing constructed before first use) and the singleton is reused
    afterwards, matching the cold-load/warm-call cost split C9 measures."""
    monkeypatch.setattr(index_module, "SentenceTransformer", _CountingFakeEmbedder)
    monkeypatch.setattr(rerank_module, "CrossEncoder", _CountingFakeCrossEncoder)

    assert _CountingFakeEmbedder.call_count == 0
    assert _CountingFakeCrossEncoder.call_count == 0

    index_module._embed_query("first query")
    index_module._embed_query("second query")

    hits = [_hit("c1", rank=1), _hit("c2", rank=2)]
    rerank("first rerank call", hits)
    rerank("second rerank call", hits)

    assert _CountingFakeEmbedder.call_count == 1
    assert _CountingFakeCrossEncoder.call_count == 1
