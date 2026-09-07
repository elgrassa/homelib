"""HTTP gate for the shared Cloud demo's per-principal daily LLM cap."""

from __future__ import annotations

import os

from fastapi import HTTPException

from apps.api import sqlite_deps
from apps.runtime_settings import AppMode, read_app_mode
from apps.store.demo_llm_quota import DemoLlmQuotaExceeded, consume_demo_llm_quota
from apps.store.sqlite import create_demo_session

DEFAULT_DEMO_LLM_DAILY_LIMIT = 100


def demo_llm_daily_limit() -> int:
    raw = os.environ.get("HOMELIB_DEMO_LLM_DAILY_LIMIT", str(DEFAULT_DEMO_LLM_DAILY_LIMIT)).strip()
    if not raw:
        return DEFAULT_DEMO_LLM_DAILY_LIMIT
    return int(raw)


def enforce_demo_llm_quota(x_demo_session: str | None) -> None:
    """No-op outside APP_MODE=demo or when SQLite is unset (unit tests).

    Count *before* Groq. Over the cap → 429, no LLM spend.
    """
    if read_app_mode() is not AppMode.DEMO:
        return
    if sqlite_deps.sqlite_path() is None:
        return
    with sqlite_deps.open_store() as conn:
        if x_demo_session:
            row = conn.execute(
                "SELECT principal_id FROM demo_session WHERE id = ?",
                (x_demo_session,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=401, detail="unknown demo session")
            principal_id = str(row[0])
        else:
            principal_id = create_demo_session(conn).principal_id
        try:
            consume_demo_llm_quota(conn, principal_id, limit=demo_llm_daily_limit())
        except DemoLlmQuotaExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
