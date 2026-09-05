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
