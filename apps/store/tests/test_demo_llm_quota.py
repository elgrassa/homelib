"""Demo LLM daily cap — one named test per failure mode."""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.store.demo_llm_quota import DemoLlmQuotaExceeded, consume_demo_llm_quota
from apps.store.sqlite import connect, create_demo_session, migrate


def _conn(tmp_path: Path):
    db = tmp_path / "quota.sqlite"
    conn = connect(db)
    migrate(conn)
    return conn


def test_two_demo_principals_have_independent_daily_counts(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    alice = create_demo_session(conn).principal_id
    bob = create_demo_session(conn).principal_id
    consume_demo_llm_quota(conn, alice, limit=1, day_utc="2026-09-07")
    consume_demo_llm_quota(conn, bob, limit=1, day_utc="2026-09-07")
    with pytest.raises(DemoLlmQuotaExceeded):
        consume_demo_llm_quota(conn, alice, limit=1, day_utc="2026-09-07")
    consume_demo_llm_quota(conn, bob, limit=2, day_utc="2026-09-07")
    conn.close()


def test_limit_allows_nth_call_and_rejects_the_next(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    principal = create_demo_session(conn).principal_id
    assert consume_demo_llm_quota(conn, principal, limit=2, day_utc="2026-09-07") == 1
    assert consume_demo_llm_quota(conn, principal, limit=2, day_utc="2026-09-07") == 2
    with pytest.raises(DemoLlmQuotaExceeded) as exc_info:
        consume_demo_llm_quota(conn, principal, limit=2, day_utc="2026-09-07")
    assert exc_info.value.count == 2
    assert exc_info.value.limit == 2
    conn.close()


def test_a_new_utc_day_resets_the_count(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    principal = create_demo_session(conn).principal_id
    consume_demo_llm_quota(conn, principal, limit=1, day_utc="2026-09-07")
    with pytest.raises(DemoLlmQuotaExceeded):
        consume_demo_llm_quota(conn, principal, limit=1, day_utc="2026-09-07")
    assert consume_demo_llm_quota(conn, principal, limit=1, day_utc="2026-09-08") == 1
    conn.close()
