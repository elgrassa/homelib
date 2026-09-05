"""Unit tests for apps.inprocess_bridge (demo ASGI wiring)."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

from apps.inprocess_bridge import build_inprocess_client, require_sqlite_path
from apps.ui.api_client import InProcessClient


def test_require_sqlite_path_fails_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)
    with pytest.raises(RuntimeError, match="HOMELIB_SQLITE_PATH"):
        require_sqlite_path()


def test_require_sqlite_path_fails_when_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "nope.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(missing))
    with pytest.raises(RuntimeError, match="not a file"):
        require_sqlite_path()


def test_build_inprocess_client_wraps_asgi_delegate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = tmp_path / "homelib.sqlite"
    db.write_bytes(b"")
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db))

    fake_main = ModuleType("apps.api.main")
    fake_main.app = object()  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "apps.api.main", fake_main)

    client = build_inprocess_client()
    assert isinstance(client, InProcessClient)
    assert client._delegate is not None


def test_inprocess_client_serves_real_requests_over_asgi(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The bridge must drive the FastAPI app from Streamlit's sync script
    thread. The tip wrapped ``httpx.ASGITransport`` (async-only) in a sync
    ``httpx.Client``, so the first call raised ``AttributeError`` and the demo
    edition never answered — health and the demo-session mint are the two
    calls every page run makes, so both go through the real app here."""
    from apps.store.sqlite import connect, migrate

    db = tmp_path / "homelib.sqlite"
    conn = connect(db)
    migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db))
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")

    client = build_inprocess_client()

    health = client.health()
    assert health["db"] is True
    assert health["books"] == 0
    session_id = client.create_demo_session()
    assert session_id
    assert client.get_playlist()["items"] == []


def test_sync_asgi_transport_maps_a_stalled_app_to_a_read_timeout() -> None:
    """The in-process edition must degrade like the HTTP one: a stalled route
    becomes ``httpx.ReadTimeout`` (→ ``ApiUnavailableError``), never a hang."""
    import asyncio

    import httpx

    from apps.inprocess_bridge import SyncASGITransport

    async def stalled(scope: dict[str, object], receive: object, send: object) -> None:
        await asyncio.sleep(5)

    client = httpx.Client(transport=SyncASGITransport(stalled), base_url="http://x")
    with pytest.raises(httpx.ReadTimeout):
        client.get("/slow", timeout=0.2)
