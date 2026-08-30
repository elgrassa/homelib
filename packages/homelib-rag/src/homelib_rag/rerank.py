"""Cross-encoder reranker — see specs/rerank.md.

Improves ranking quality on top of `hybrid_search`'s output by scoring each
`(query, chunk)` pair jointly with a cross-encoder. The binding contract is
that this quality improvement is strictly optional: if the model cannot be
loaded, or scoring blows up mid-batch, `rerank` degrades to `None` and the
caller keeps whatever ranking it already had. A rerank failure must never
fail a request.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from sentence_transformers import CrossEncoder

from homelib_rag.models import Hit

__all__ = ["rerank"]

logger = logging.getLogger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Lazy, thread-safe singleton state. The model loads on first call to
# `rerank`, not at import time; a `threading.Lock` guards the check-then-load
# so concurrent first callers never race into two loads or a partially
# initialized model. A load failure is permanent for the process's lifetime —
# later calls short-circuit on `_load_failed` without retrying.
_lock = threading.Lock()
_model: CrossEncoder | None = None
_load_failed = False


def _load_model() -> CrossEncoder | None:
    """Return the process-wide `CrossEncoder` singleton, loading it if needed.

    Returns `None` (without raising) if construction fails for any reason —
    missing weights, OOM, an import error, anything `CrossEncoder(...)` can
    throw.
    """
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    with _lock:
        if _model is not None or _load_failed:
            return _model
        try:
            _model = CrossEncoder(_MODEL_NAME)
        except Exception:
            logger.exception("cross-encoder model failed to load: %s", _MODEL_NAME)
            _load_failed = True
            return None
        return _model


def _reset_singleton_for_tests() -> None:
    """Reset the lazy singleton. Test-only — not part of the public API."""
    global _model, _load_failed
    with _lock:
        _model = None
        _load_failed = False


def rerank(q: str, hits: list[Hit]) -> list[Hit] | None:
    """Reorder `hits` by cross-encoder relevance to `q`.

    Returns the reordered hits on success: same `chunk_id` set and length as
    the input, `score` replaced with the cross-encoder's relevance score, and
    `rank` recomputed 1-based dense from the new order. Every other field is
    unchanged.

    Returns `None` — never `[]`, never raises — when the model can't be
    loaded or a scoring-time exception occurs, signalling the caller to keep
    its existing ranking (`result = rerank(q, hits); use = result if result
    is not None else hits`). A scoring-time failure does not poison the
    singleton: a later call may still succeed.

    An empty `hits` list returns `[]` directly, without touching the model —
    that is "nothing to rerank," not a failure.
    """
    if not hits:
        return []

    model = _load_model()
    if model is None:
        return None

    try:
        pairs: list[tuple[str, str]] = [(q, hit.text) for hit in hits]
        raw_scores: Any = model.predict(pairs)
        scored = sorted(
            zip(hits, raw_scores, strict=True),
            key=lambda pair: float(pair[1]),
            reverse=True,
        )
        return [
            hit.model_copy(update={"score": float(score), "rank": rank})
            for rank, (hit, score) in enumerate(scored, start=1)
        ]
    except Exception:
        logger.exception("cross-encoder scoring failed for query %r", q)
        return None
