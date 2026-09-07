"""HTTP gate for the shared Cloud demo's per-principal daily LLM cap."""

from __future__ import annotations

import os

from fastapi import HTTPException

from apps.api import sqlite_deps
from apps.runtime_settings import AppMode, read_app_mode
from apps.store.demo_llm_quota import DemoLlmQuotaExceeded, consume_demo_llm_quota

DEFAULT_DEMO_LLM_DAILY_LIMIT = 100


def demo_llm_daily_limit() -> int:
    raw = os.environ.get("HOMELIB_DEMO_LLM_DAILY_LIMIT", str(DEFAULT_DEMO_LLM_DAILY_LIMIT)).strip()
    if not raw:
        return DEFAULT_DEMO_LLM_DAILY_LIMIT
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_DEMO_LLM_DAILY_LIMIT


def _demo_principal_id(x_demo_session: str | None) -> str | None:
    """Resolve the demo principal, or None when the cap does not apply.

    Missing / blank / unknown ``X-Demo-Session`` is 401 — never mint a
    throwaway principal. A new principal per request would never hit the
    daily cap, so Groq spend on the public demo would be unbounded.
    """
    if read_app_mode() is not AppMode.DEMO:
        return None
    if sqlite_deps.sqlite_path() is None:
        return None
    token = (x_demo_session or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="demo session required")
    with sqlite_deps.open_store() as conn:
        row = conn.execute(
            "SELECT principal_id FROM demo_session WHERE id = ?",
            (token,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="unknown demo session")
        return str(row[0])


def require_demo_session(x_demo_session: str | None) -> None:
    """401 on a demo host when the visitor has no valid session (cache hits too)."""
    _demo_principal_id(x_demo_session)


def enforce_demo_llm_quota(x_demo_session: str | None) -> None:
    """No-op outside APP_MODE=demo or when SQLite is unset (unit tests).

    Count *before* Groq. Over the cap → 429, no LLM spend.
    """
    principal_id = _demo_principal_id(x_demo_session)
    if principal_id is None:
        return
    with sqlite_deps.open_store() as conn:
        try:
            consume_demo_llm_quota(conn, principal_id, limit=demo_llm_daily_limit())
        except DemoLlmQuotaExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
