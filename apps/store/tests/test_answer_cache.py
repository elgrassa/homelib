"""Behavioural tests for `apps.store.answer_cache` — C4b (specs/monitoring.md
"Demo answer cache").

`apps/api/tests/test_api.py` covers the demo-only gate end to end
(`test_demo_ask_serves_cached_answer_on_repeat`,
`test_selfhosted_ask_never_reads_answer_cache`,
`test_cache_hit_is_logged_and_flagged`); this module covers the cache
primitives — key derivation and the store/lookup roundtrip — in isolation.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from homelib_rag.answer import AskResponse, TokenUsage

from apps.store.answer_cache import cache_key, lookup, store
from apps.store.sqlite import connect, migrate


def _db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "cache.sqlite")
    migrate(conn)
    return conn


def _response(answer: str = "It jumps.") -> AskResponse:
    return AskResponse(
        request_id="r1",
        answer=answer,
        citations=[],
        arm_used="hybrid",
        degraded=False,
        latency_ms=10,
        tokens=TokenUsage(prompt=10, completion=5),
    )


def test_cache_key_is_stable_for_the_same_inputs() -> None:
    assert cache_key("does it jump?", arm="hybrid", model="m") == cache_key(
        "does it jump?", arm="hybrid", model="m"
    )


def test_cache_key_normalizes_whitespace_and_case() -> None:
    assert cache_key("Does It Jump?", arm="hybrid", model="m") == cache_key(
        "  does   it jump?  ", arm="hybrid", model="m"
    )


def test_cache_key_changes_with_arm() -> None:
    assert cache_key("q", arm="hybrid", model="m") != cache_key("q", arm="lexical", model="m")


def test_cache_key_changes_with_model() -> None:
    assert cache_key("q", arm="hybrid", model="m1") != cache_key("q", arm="hybrid", model="m2")


def test_cache_key_changes_with_k() -> None:
    """Audit S01: different top-k must not share a cached answer."""
    assert cache_key("q", arm="hybrid", model="m", k=3) != cache_key(
        "q", arm="hybrid", model="m", k=10
    )


def test_cache_key_changes_with_rewrite_flag() -> None:
    """Audit S01: rewrite on/off changes retrieval semantics."""
    assert cache_key("q", arm="hybrid", model="m", rewrite=False) != cache_key(
        "q", arm="hybrid", model="m", rewrite=True
    )


def test_cache_key_changes_with_index_revision() -> None:
    """Audit S01: a re-seeded corpus must not reuse prior answers."""
    assert cache_key("q", arm="hybrid", model="m", index_revision="aaa") != cache_key(
        "q", arm="hybrid", model="m", index_revision="bbb"
    )


def test_lookup_miss_returns_none(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    assert lookup(conn, cache_key("nothing cached", arm="hybrid", model="m")) is None


def test_store_then_lookup_roundtrip(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    key = cache_key("does it jump?", arm="hybrid", model="m")
    response = _response("It jumps high.")

    store(conn, key, response)
    found = lookup(conn, key)

    assert found is not None
    assert found.answer == "It jumps high."
    assert found.tokens.prompt == 10


def test_store_overwrites_existing_key(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    key = cache_key("does it jump?", arm="hybrid", model="m")

    store(conn, key, _response("first answer"))
    store(conn, key, _response("second answer"))

    found = lookup(conn, key)
    assert found is not None
    assert found.answer == "second answer"
    count = conn.execute("SELECT COUNT(*) FROM answer_cache WHERE key = ?", (key,)).fetchone()[0]
    assert count == 1
