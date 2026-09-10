"""API tests for observatory + Coffee Table routes (WP07/WP10)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.store.sqlite import connect, migrate, seed


@pytest.fixture(autouse=True)
def _reset_api_deps() -> None:
    import apps.api.main as api_main

    api_main._deps_singleton = None
    yield
    api_main._deps_singleton = None


@pytest.fixture()
def sqlite_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "api.sqlite"
    conn = connect(db)
    migrate(conn)
    seed(conn, repo_root=Path(__file__).resolve().parents[3])
    # Seed a few query_log rows for observatory charts
    for i in range(5):
        conn.execute(
            "INSERT INTO query_log ("
            "request_id, ts, latency_ms, arm, k, rerank, rewrite, model, "
            "tokens_prompt, tokens_completion, query_sha256_prefix, degraded, feedback"
            ") VALUES (?, datetime('now'), ?, ?, 5, 0, 0, 'test', 10, 20, ?, ?, ?)",
            (
                f"req-{i}",
                100 + i * 10,
                "hybrid_rerank",
                f"deadbeef{i:04d}",
                0 if i % 2 == 0 else 1,
                "up" if i < 3 else "down",
            ),
        )
    conn.commit()
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db))
    monkeypatch.setenv("APP_MODE", "selfhosted")
    import apps.api.main as api_main

    api_main._deps_singleton = None
    return db


def test_observatory_returns_at_least_five_chart_ids(sqlite_env: Path) -> None:
    with TestClient(app) as client:
        resp = client.get("/v1/observatory")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["charts"]) >= 5
        ids = {c["id"] for c in body["charts"]}
        assert "queries_over_time" in ids
        assert "feedback_ratio" in ids


def test_observatory_never_includes_plaintext_or_keys(sqlite_env: Path) -> None:
    with TestClient(app) as client:
        raw = client.get("/v1/observatory").text.lower()
        assert "api_key" not in raw
        assert "sk-" not in raw
        assert "query_plaintext" not in raw
        assert "password" not in raw


def test_playlist_add_and_accept_roundtrip(sqlite_env: Path) -> None:
    with TestClient(app) as client:
        books = client.get("/v1/resources").json()["items"]
        assert books
        book_id = books[0]["id"]
        added = client.post(
            "/v1/playlists/current/items",
            json={"resource_id": book_id, "origin": "manual_shelf"},
        )
        assert added.status_code == 200
        assert added.json()["items"][0]["status"] == "queued"

        from apps.api import sqlite_deps
        from apps.store import coffee_table as ct

        with sqlite_deps.open_store() as conn:
            ct.propose_items(conn, principal_id="local-user", resource_ids=[books[1]["id"]])
        accepted = client.post("/v1/playlists/current", json={})
        assert accepted.status_code == 200
        assert any(i["status"] == "queued" for i in accepted.json()["items"])


def test_progress_endpoint(sqlite_env: Path) -> None:
    with TestClient(app) as client:
        book_id = client.get("/v1/resources").json()["items"][0]["id"]
        resp = client.post(
            "/v1/progress",
            json={"resource_id": book_id, "kind": "read", "char_offset": 12},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


def test_get_progress_returns_latest_saved_row(sqlite_env: Path) -> None:
    """Audit S03: GET /v1/progress restores the principal's last-read row."""
    with TestClient(app) as client:
        books = client.get("/v1/resources").json()["items"]
        first_id = books[0]["id"]
        second_id = books[1]["id"]
        client.post(
            "/v1/progress",
            json={
                "resource_id": first_id,
                "kind": "read",
                "char_offset": 1,
                "block_id": "blk-a",
            },
        )
        client.post(
            "/v1/progress",
            json={
                "resource_id": second_id,
                "kind": "read",
                "char_offset": 99,
                "block_id": "blk-b",
            },
        )
        latest = client.get("/v1/progress")
        assert latest.status_code == 200
        body = latest.json()
        assert body is not None
        assert body["resource_id"] == second_id
        assert body["char_offset"] == 99
        assert body["block_id"] == "blk-b"
        assert body["kind"] == "read"

        by_resource = client.get("/v1/progress", params={"resource_id": first_id})
        assert by_resource.status_code == 200
        assert by_resource.json()["resource_id"] == first_id
        assert by_resource.json()["char_offset"] == 1


def test_get_progress_null_when_empty(sqlite_env: Path) -> None:
    with TestClient(app) as client:
        resp = client.get("/v1/progress")
        assert resp.status_code == 200
        assert resp.json() is None


def test_audio_capabilities(sqlite_env: Path) -> None:
    with TestClient(app) as client:
        resp = client.get("/v1/audio/capabilities")
        assert resp.status_code == 200
        assert resp.json()["can_generate"] is False


def test_patch_duplicate_ordinals_422(sqlite_env: Path) -> None:
    with TestClient(app) as client:
        books = client.get("/v1/resources").json()["items"]
        a = client.post(
            "/v1/playlists/current/items",
            json={"resource_id": books[0]["id"], "origin": "manual_shelf"},
        ).json()["items"][0]["id"]
        b = client.post(
            "/v1/playlists/current/items",
            json={"resource_id": books[1]["id"], "origin": "manual_shelf"},
        ).json()["items"][-1]["id"]
        resp = client.patch(
            "/v1/playlists/current/items",
            json={"items": [{"id": a, "ordinal": 0}, {"id": b, "ordinal": 0}]},
        )
        assert resp.status_code == 422


def test_scene_search_unknown_resource_404(sqlite_env: Path) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/v1/resources/no-such-book/search",
            json={"query": "compound interest", "mode": "keyword", "k": 3},
        )
        assert resp.status_code == 404


def test_observatory_without_sqlite_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)
    import apps.api.main as api_main

    api_main._deps_singleton = None
    with TestClient(app) as client:
        assert client.get("/v1/observatory").status_code == 503


def test_playlist_current_ok_on_migrate_only_sqlite_without_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compose mounts a pipeline-seeded DB that never ran store.seed().

    After HOMELIB_SQLITE_PATH is set, Coffee Table must not 500 on missing
    local-user — migrate ensures the well-known selfhosted principal.
    """
    db = tmp_path / "pipeline_shaped.sqlite"
    conn = connect(db)
    migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db))
    monkeypatch.setenv("APP_MODE", "selfhosted")
    import apps.api.main as api_main

    api_main._deps_singleton = None
    with TestClient(app) as client:
        resp = client.get("/v1/playlists/current")
        assert resp.status_code == 200
        body = resp.json()
        assert body["principal_id"] == "local-user"
        assert body["items"] == []


def test_feedback_ui_to_db_roundtrip(sqlite_env: Path) -> None:
    """WP10 live feedback path: POST /v1/feedback updates query_log (UI→API→DB)."""
    with TestClient(app) as client:
        resp = client.post(
            "/v1/feedback",
            json={"request_id": "req-0", "feedback": "up"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
    from apps.store.sqlite import connect

    conn = connect(sqlite_env)
    try:
        row = conn.execute("SELECT feedback FROM query_log WHERE request_id = 'req-0'").fetchone()
        assert row is not None
        assert row[0] == "up"
    finally:
        conn.close()


def test_demo_traffic_populates_observatory_charts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP10: demo_traffic.py --n 40 leaves Observatory with ≥5 non-empty chart ids."""
    import scripts.demo_traffic as demo_traffic

    db = tmp_path / "traffic.sqlite"
    monkeypatch.setattr(
        "sys.argv",
        ["demo_traffic.py", "--n", "40", "--db", str(db)],
    )
    demo_traffic.main()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db))
    monkeypatch.setenv("APP_MODE", "selfhosted")
    import apps.api.main as api_main

    api_main._deps_singleton = None
    with TestClient(app) as client:
        body = client.get("/v1/observatory").json()
        assert len(body["charts"]) >= 5
        assert sum(1 for c in body["charts"] if c.get("points")) >= 5


def test_demo_mode_same_header_shares_principal_and_missing_header_does_not(
    sqlite_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server-side contract the client fix (H3) relies on: a minted
    `X-Demo-Session` is one stable principal; no header is a fresh anonymous
    principal every time; an unknown header is 401 (so the client remints)."""
    monkeypatch.setenv("APP_MODE", "demo")
    with TestClient(app) as client:
        minted = client.post("/v1/demo/session").json()
        headers = {"X-Demo-Session": minted["demo_session_id"]}
        book_id = client.get("/v1/resources", headers=headers).json()["items"][0]["id"]

        added = client.post(
            "/v1/playlists/current/items",
            json={"resource_id": book_id, "origin": "manual_shelf"},
            headers=headers,
        )
        assert added.status_code == 200, added.text

        with_header = client.get("/v1/playlists/current", headers=headers).json()
        assert len(with_header["items"]) == 1

        without_header = client.get("/v1/playlists/current").json()
        assert without_header["items"] == []

        unknown = client.get("/v1/playlists/current", headers={"X-Demo-Session": "nope"})
        assert unknown.status_code == 401


def test_discover_resources_returns_federated_fixture_hits(
    sqlite_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMELIB_CONNECTOR_MODE", "fixture")
    with TestClient(app) as client:
        empty = client.get("/v1/resources", params={"source": "discover"})
        assert empty.status_code == 200
        assert empty.json()["items"] == []
        assert empty.json()["unique_count"] == 0

        resp = client.get("/v1/resources", params={"source": "discover", "q": "meditations"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["unique_count"] >= 1
        assert body["degraded"] is False
        assert "open_library" in body["approximate_provider_counts"]
        hit = body["items"][0]
        assert hit["source"] == "discover"
        assert hit["title"] == "Meditations"
        assert hit["can_index_text"] is False
        assert hit["provider_url"]
        assert hit["book_id"] is None


def test_discover_resources_degrades_when_one_connector_times_out(
    sqlite_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMELIB_CONNECTOR_MODE", "fixture")
    from pathlib import Path as PathType

    from homelib_rag.connectors import ConnectorName, FixtureConnector, SlowConnector

    fixture_dir = PathType(__file__).resolve().parents[3] / (
        "packages/homelib-rag/tests/fixtures/connectors"
    )

    def _mixed(**_kwargs: object) -> list[object]:
        return [
            SlowConnector(),
            FixtureConnector(ConnectorName.OPEN_LIBRARY, fixture_dir / "open_library.jsonl"),
        ]

    monkeypatch.setattr("homelib_rag.connectors.build_discover_connectors", _mixed)
    with TestClient(app) as client:
        resp = client.get("/v1/resources", params={"source": "discover", "q": "republic"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["degraded"] is True
        assert body["unique_count"] >= 1
        assert body["items"][0]["title"] == "The Republic"


def test_discover_returns_seeded_catalog_not_empty(
    sqlite_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discover default is the committed Open Library snapshot."""
    monkeypatch.setenv("HOMELIB_CONNECTOR_MODE", "snapshot")
    with TestClient(app) as client:
        shelf = client.get("/v1/resources").json()
        discover = client.get("/v1/resources", params={"source": "discover"}).json()
        assert shelf["items"]
        assert discover["items"], "seeded catalog must surface on Discover"
        assert discover["approximate_provider_counts"].get("open_library_snapshot", 0) >= 1
        for item in discover["items"]:
            assert item["source"] == "discover"
            assert item["full_text_available"] is False
            assert item["provider_url"]


def test_discover_empty_query_browses_and_q_filters(
    sqlite_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOMELIB_CONNECTOR_MODE", "snapshot")
    with TestClient(app) as client:
        browsed = client.get("/v1/resources", params={"source": "discover"}).json()
        assert browsed["items"]
        title = browsed["items"][0]["title"]
        needle = title.split()[0]
        filtered = client.get("/v1/resources", params={"source": "discover", "q": needle}).json()
        assert filtered["items"]
        assert all(needle.lower() in item["title"].lower() for item in filtered["items"])
