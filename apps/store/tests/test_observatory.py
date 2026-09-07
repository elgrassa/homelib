"""Behavioural tests for `apps.store.observatory` — specs/observatory.md.

New charts land here as they are added (C1 cost, C6 judged relevance, C5
time-per-stage) so this module stays the one place Observatory's chart
contract is pinned, alongside the WP10 base charts already covered by
`apps/api/tests/test_v2_routes.py`.
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest

from apps.store.observatory import build_observatory
from apps.store.sqlite import connect, migrate


def _db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "obs.sqlite")
    migrate(conn)
    return conn


def _insert_query_log(
    conn: sqlite3.Connection,
    *,
    cost_usd: float = 0.0,
    tokens_prompt: int = 100,
    tokens_completion: int = 50,
    relevance: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO query_log ("
        "request_id, ts, latency_ms, arm, k, rerank, rewrite, model, "
        "tokens_prompt, tokens_completion, query_sha256_prefix, degraded, cost_usd, relevance"
        ") VALUES (?, datetime('now'), 100, 'hybrid', 5, 0, 0, 'm', ?, ?, ?, 0, ?, ?)",
        (str(uuid.uuid4()), tokens_prompt, tokens_completion, "a" * 16, cost_usd, relevance),
    )
    conn.commit()


def test_observatory_cost_chart_uses_cost_when_priced(tmp_path: Path) -> None:
    """C1: once any row carries a real `cost_usd`, chart 6 reports total USD
    (title "Cost estimate (USD)", bucket `total_cost_usd`) instead of the
    token sum it falls back to when nothing has been priced."""
    conn = _db(tmp_path)
    _insert_query_log(conn, cost_usd=0.0123, tokens_prompt=100, tokens_completion=50)
    _insert_query_log(conn, cost_usd=0.0456, tokens_prompt=200, tokens_completion=80)

    response = build_observatory(conn)

    chart = next(c for c in response.charts if c.id == "token_or_cost_estimate")
    assert chart.title == "Cost estimate (USD)"
    assert len(chart.points) == 1
    assert chart.points[0].bucket == "total_cost_usd"
    assert chart.points[0].value == 0.0123 + 0.0456


def test_observatory_token_chart_when_nothing_priced(tmp_path: Path) -> None:
    """The pre-C1 behaviour is preserved when every row's cost_usd is the
    (default) 0 — e.g. a local Ollama run with no `LLM_PRICE_PER_1K_*` set.

    Chart 6 breaks the sum into prompt / completion / total so reviewers can
    see token usage counts without reading query_log.
    """
    conn = _db(tmp_path)
    _insert_query_log(conn, cost_usd=0.0, tokens_prompt=100, tokens_completion=50)

    response = build_observatory(conn)

    chart = next(c for c in response.charts if c.id == "token_or_cost_estimate")
    assert chart.title == "Token estimate"
    points = {p.bucket: p.value for p in chart.points}
    assert points == {
        "prompt_tokens": 100.0,
        "completion_tokens": 50.0,
        "total_tokens": 150.0,
    }


def test_observatory_relevance_chart(tmp_path: Path) -> None:
    """C6: `judged_relevance` counts query_log rows per relevance label, and
    ignores rows the online judge has not scored yet (relevance IS NULL)."""
    conn = _db(tmp_path)
    _insert_query_log(conn, relevance="4")
    _insert_query_log(conn, relevance="4")
    _insert_query_log(conn, relevance="2")
    _insert_query_log(conn, relevance=None)  # not yet judged — excluded

    response = build_observatory(conn)

    chart = next(c for c in response.charts if c.id == "judged_relevance")
    assert chart.title == "Judged relevance"
    points = {p.bucket: p.value for p in chart.points}
    assert points == {"2": 1.0, "4": 2.0}


def test_observatory_relevance_chart_empty_when_nothing_judged(tmp_path: Path) -> None:
    """Rubric requirement (specs/observatory.md): an unpopulated chart still
    exists with empty points, never a 500."""
    conn = _db(tmp_path)
    _insert_query_log(conn, relevance=None)

    response = build_observatory(conn)

    chart = next(c for c in response.charts if c.id == "judged_relevance")
    assert chart.points == []


def _insert_span(
    conn: sqlite3.Connection,
    *,
    trace_id: str,
    span_id: str,
    name: str,
    start_ns: int,
    end_ns: int,
    parent_span_id: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO spans (trace_id, span_id, parent_span_id, name, start_ns, end_ns, attributes) "
        "VALUES (?, ?, ?, ?, ?, ?, '{}')",
        (trace_id, span_id, parent_span_id, name, start_ns, end_ns),
    )
    conn.commit()


def test_observatory_time_per_stage_chart(tmp_path: Path) -> None:
    """C5: `time_per_stage` reports the mean duration (ms) per span name
    across recent traces — two `retrieve` spans of 10ms and 30ms average to
    20ms."""
    conn = _db(tmp_path)
    _insert_span(conn, trace_id="t1", span_id="s1", name="retrieve", start_ns=0, end_ns=10_000_000)
    _insert_span(conn, trace_id="t2", span_id="s2", name="retrieve", start_ns=0, end_ns=30_000_000)

    response = build_observatory(conn)

    chart = next(c for c in response.charts if c.id == "time_per_stage")
    assert chart.title == "Time per stage (mean, ms)"
    point = next(p for p in chart.points if p.bucket == "retrieve")
    assert point.value == pytest.approx(20.0)


def test_observatory_time_per_stage_chart_empty_when_no_spans(tmp_path: Path) -> None:
    conn = _db(tmp_path)

    response = build_observatory(conn)

    chart = next(c for c in response.charts if c.id == "time_per_stage")
    assert chart.points == []


def _insert_query_log_with_cache_hit(conn: sqlite3.Connection, *, cache_hit: bool) -> None:
    conn.execute(
        "INSERT INTO query_log ("
        "request_id, ts, latency_ms, arm, k, rerank, rewrite, model, "
        "tokens_prompt, tokens_completion, query_sha256_prefix, degraded, cache_hit"
        ") VALUES (?, datetime('now'), 100, 'hybrid', 5, 0, 0, 'm', 10, 5, ?, 0, ?)",
        (str(uuid.uuid4()), "a" * 16, 1 if cache_hit else 0),
    )
    conn.commit()


def test_observatory_cache_hits_vs_live_chart(tmp_path: Path) -> None:
    """C4b: `cache_hits_vs_live` counts query_log rows by cache_hit,
    labelled "cache_hit"/"live" rather than raw 0/1."""
    conn = _db(tmp_path)
    _insert_query_log_with_cache_hit(conn, cache_hit=False)
    _insert_query_log_with_cache_hit(conn, cache_hit=False)
    _insert_query_log_with_cache_hit(conn, cache_hit=True)

    response = build_observatory(conn)

    chart = next(c for c in response.charts if c.id == "cache_hits_vs_live")
    assert chart.title == "Cache hits vs live"
    points = {p.bucket: p.value for p in chart.points}
    assert points == {"live": 2.0, "cache_hit": 1.0}
