"""Per-principal UTC-day LLM call counter for the shared Cloud demo."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


class DemoLlmQuotaExceeded(Exception):
    """This principal has already used today's demo LLM budget."""

    def __init__(self, *, limit: int, count: int, day_utc: str) -> None:
        self.limit = limit
        self.count = count
        self.day_utc = day_utc
        super().__init__(f"Daily demo LLM limit reached ({limit} calls). Try again tomorrow (UTC).")


def utc_day(now: datetime | None = None) -> str:
    stamp = now if now is not None else datetime.now(UTC)
    return stamp.astimezone(UTC).date().isoformat()


def consume_demo_llm_quota(
    conn: sqlite3.Connection,
    principal_id: str,
    *,
    limit: int,
    day_utc: str | None = None,
) -> int:
    """Increment today's count. Raise if the principal is already at ``limit``.

    Call this *before* the LLM so a loop cannot spend past the cap.
    Returns the new count (1..limit).
    """
    if limit < 1:
        raise DemoLlmQuotaExceeded(limit=limit, count=0, day_utc=utc_day())
    day = day_utc if day_utc is not None else utc_day()
    with conn:
        row = conn.execute(
            "SELECT count FROM demo_llm_daily WHERE principal_id = ? AND day_utc = ?",
            (principal_id, day),
        ).fetchone()
        current = int(row["count"]) if row is not None else 0
        if current >= limit:
            raise DemoLlmQuotaExceeded(limit=limit, count=current, day_utc=day)
        if row is None:
            conn.execute(
                "INSERT INTO demo_llm_daily (principal_id, day_utc, count) VALUES (?, ?, 1)",
                (principal_id, day),
            )
        else:
            conn.execute(
                "UPDATE demo_llm_daily SET count = count + 1 "
                "WHERE principal_id = ? AND day_utc = ?",
                (principal_id, day),
            )
    return current + 1
