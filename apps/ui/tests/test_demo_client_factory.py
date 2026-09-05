"""Demo-mode HomelibClient factory — APP_MODE=demo selects InProcessClient.

Regression pins for Streamlit Community Cloud (no FastAPI sidecar): the UI
must not construct Http/ApiClient when APP_MODE=demo (and API_URL is unset),
and must fail closed when HOMELIB_SQLITE_PATH is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apps.ui.api_client import HttpClient, InProcessClient
from apps.ui.view_model import (
    DEMO_ENV_KEYS,
    apply_streamlit_secrets_to_environ,
    build_homelib_client,
    wants_inprocess_client,
)


def test_wants_inprocess_when_app_mode_is_demo() -> None:
    assert wants_inprocess_client({"APP_MODE": "demo"}) is True
    assert wants_inprocess_client({"APP_MODE": "selfhosted"}) is False
    assert wants_inprocess_client({}) is False


def test_demo_mode_selects_inprocess_with_sqlite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = tmp_path / "homelib.sqlite"
    db.write_bytes(b"")  # existence check only; bridge is mocked
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.delenv("API_URL", raising=False)
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db))

    sentinel = InProcessClient(
        health=lambda: {"status": "ok"},
        ask=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("unused")),
    )
    monkeypatch.setattr(
        "apps.inprocess_bridge.build_inprocess_client",
        lambda: sentinel,
    )

    client = build_homelib_client()
    assert client is sentinel
    assert isinstance(client, InProcessClient)


def test_demo_mode_without_sqlite_path_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.delenv("API_URL", raising=False)
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)

    with pytest.raises(RuntimeError, match="HOMELIB_SQLITE_PATH"):
        build_homelib_client()


def test_selfhosted_selects_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "selfhosted")
    monkeypatch.setenv("API_URL", "http://api:8000")

    client = build_homelib_client()
    assert isinstance(client, HttpClient)
    assert type(client) is HttpClient


def test_api_url_keeps_compose_on_http_even_if_app_mode_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose injects API_URL — stay HTTP so the UI talks to the api service."""
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("API_URL", "http://api:8000")

    assert wants_inprocess_client() is False
    client = build_homelib_client()
    assert isinstance(client, HttpClient)


def test_apply_streamlit_secrets_copies_demo_keys_into_environ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    secrets = {
        "APP_MODE": "demo",
        "LLM_API_KEY": "gsk_test_not_real",
        "IGNORED": "nope",
    }
    apply_streamlit_secrets_to_environ(secrets)
    assert os.environ["APP_MODE"] == "demo"
    assert os.environ["LLM_API_KEY"] == "gsk_test_not_real"
    assert "IGNORED" not in DEMO_ENV_KEYS
    assert os.environ.get("IGNORED") is None
