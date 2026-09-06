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
) -> None:
    conn.execute(
        "INSERT INTO query_log ("
        "request_id, ts, latency_ms, arm, k, rerank, rewrite, model, "
        "tokens_prompt, tokens_completion, query_sha256_prefix, degraded, cost_usd"
        ") VALUES (?, datetime('now'), 100, 'hybrid', 5, 0, 0, 'm', ?, ?, ?, 0, ?)",
        (str(uuid.uuid4()), tokens_prompt, tokens_completion, "a" * 16, cost_usd),
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
    (default) 0 — e.g. a local Ollama run with no `LLM_PRICE_PER_1K_*` set."""
    conn = _db(tmp_path)
    _insert_query_log(conn, cost_usd=0.0, tokens_prompt=100, tokens_completion=50)

    response = build_observatory(conn)

    chart = next(c for c in response.charts if c.id == "token_or_cost_estimate")
    assert chart.title == "Token estimate"
    assert chart.points[0].bucket == "total_tokens"
    assert chart.points[0].value == 150.0
