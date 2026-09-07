"""APP_MODE=demo daily LLM cap on Ask / Mentor / Roadmap."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from homelib_core.models import Block
from homelib_rag.answer import LLMResponse, LLMUsage
from homelib_rag.mentor import MentorIntakeResponse
from homelib_rag.models import Hit
from homelib_rag.roadmap import RoadmapResponse

import apps.api.main as main
from apps.api.main import Deps, app, get_deps
from apps.store.demo_llm_quota import consume_demo_llm_quota
from apps.store.sqlite import connect, create_demo_session, migrate

client = TestClient(app)


class _ScriptedClient:
    model = "fake-model"

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls = 0

    def chat(self, messages: Any, **kwargs: Any) -> LLMResponse:
        self.calls += 1
        return self._responses.pop(0)


def _llm_json(answer_text: str, citations: list[dict[str, Any]]) -> LLMResponse:
    return LLMResponse(
        content=json.dumps({"answer": answer_text, "citations": citations}),
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5),
    )


def _hit() -> Hit:
    return Hit(
        chunk_id="c1",
        book_id="b1",
        score=1.0,
        rank=1,
        text="The fox jumps high.",
        section_path=[],
        page=None,
    )


def _missing_block(block_id: str) -> Block:
    raise KeyError(block_id)


def _base_deps(**overrides: Any) -> Deps:
    deps = Deps(
        llm_client=_ScriptedClient(),
        llm_provider="fake",
        llm_reachable=lambda: True,
        db_reachable=lambda: True,
        counts=lambda: (0, 0),
        retrieve=lambda query, k, arm: ([_hit()], arm, False),
        rewrite_query=lambda query: query,
        catalog_search=lambda query, subjects=None: [],
        list_books=lambda: [],
        get_block=_missing_block,
        get_book_block=lambda book_id, ordinal: (_ for _ in ()).throw(KeyError(book_id)),
        log_query=lambda row: None,
        record_feedback=lambda request_id, feedback, comment: True,
        ingest=lambda req: (_ for _ in ()).throw(NotImplementedError("unused")),
    )
    return replace(deps, **overrides) if overrides else deps


@pytest.fixture(autouse=True)
def _clear_overrides() -> Any:
    yield
    app.dependency_overrides.clear()
    main._deps_singleton = None


def _demo_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, mode: str, limit: str) -> Path:
    db_path = tmp_path / "quota.sqlite"
    conn = connect(db_path)
    migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("APP_MODE", mode)
    monkeypatch.setenv("HOMELIB_DEMO_LLM_DAILY_LIMIT", limit)
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    return db_path


def _mint(headers_client: TestClient) -> dict[str, str]:
    minted = headers_client.post("/v1/demo/session").json()
    return {"X-Demo-Session": minted["demo_session_id"]}


def test_demo_ask_101st_llm_call_returns_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _demo_db(tmp_path, monkeypatch, mode="demo", limit="2")
    fake_llm = _ScriptedClient(
        [
            _llm_json("one", [{"passage": 1, "quote": "fox jumps"}]),
            _llm_json("two", [{"passage": 1, "quote": "fox jumps"}]),
            _llm_json("should-not-run", [{"passage": 1, "quote": "fox jumps"}]),
        ]
    )
    app.dependency_overrides[get_deps] = lambda: _base_deps(llm_client=fake_llm)
    headers = _mint(client)

    first = client.post("/v1/ask", json={"query": "q1", "arm": "lexical"}, headers=headers)
    second = client.post("/v1/ask", json={"query": "q2", "arm": "lexical"}, headers=headers)
    third = client.post("/v1/ask", json={"query": "q3", "arm": "lexical"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert "Daily demo LLM limit" in third.json()["detail"]
    assert fake_llm.calls == 2


def test_demo_quota_is_per_principal_not_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _demo_db(tmp_path, monkeypatch, mode="demo", limit="1")
    fake_llm = _ScriptedClient(
        [
            _llm_json("alice", [{"passage": 1, "quote": "fox jumps"}]),
            _llm_json("bob", [{"passage": 1, "quote": "fox jumps"}]),
        ]
    )
    app.dependency_overrides[get_deps] = lambda: _base_deps(llm_client=fake_llm)
    alice = _mint(client)
    bob = _mint(client)

    assert (
        client.post("/v1/ask", json={"query": "a", "arm": "lexical"}, headers=alice).status_code
        == 200
    )
    # A different question forces a second LLM attempt (same query would be a
    # demo cache hit and must not consume another quota unit).
    assert (
        client.post("/v1/ask", json={"query": "a2", "arm": "lexical"}, headers=alice).status_code
        == 429
    )
    bob_ok = client.post("/v1/ask", json={"query": "b", "arm": "lexical"}, headers=bob)
    assert bob_ok.status_code == 200
    assert fake_llm.calls == 2


def test_selfhosted_ask_ignores_demo_llm_daily_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _demo_db(tmp_path, monkeypatch, mode="selfhosted", limit="1")
    fake_llm = _ScriptedClient(
        [
            _llm_json("one", [{"passage": 1, "quote": "fox jumps"}]),
            _llm_json("two", [{"passage": 1, "quote": "fox jumps"}]),
        ]
    )
    app.dependency_overrides[get_deps] = lambda: _base_deps(llm_client=fake_llm)

    first = client.post("/v1/ask", json={"query": "q1", "arm": "lexical"})
    second = client.post("/v1/ask", json={"query": "q2", "arm": "lexical"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert fake_llm.calls == 2


def test_demo_cache_hit_does_not_consume_llm_quota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _demo_db(tmp_path, monkeypatch, mode="demo", limit="1")
    fake_llm = _ScriptedClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])
    app.dependency_overrides[get_deps] = lambda: _base_deps(llm_client=fake_llm)
    headers = _mint(client)

    first = client.post(
        "/v1/ask", json={"query": "does it jump?", "arm": "hybrid"}, headers=headers
    )
    cached = client.post(
        "/v1/ask", json={"query": "does it jump?", "arm": "hybrid"}, headers=headers
    )
    other = client.post(
        "/v1/ask", json={"query": "something else", "arm": "hybrid"}, headers=headers
    )

    assert first.status_code == 200
    assert first.json()["cache_hit"] is False
    assert cached.status_code == 200
    assert cached.json()["cache_hit"] is True
    assert other.status_code == 429
    assert fake_llm.calls == 1


def test_demo_roadmap_returns_429_after_daily_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _demo_db(tmp_path, monkeypatch, mode="demo", limit="1")
    fake = RoadmapResponse(request_id="r1", steps=[], rationale="ok")
    monkeypatch.setattr(main.roadmap_module, "build_roadmap", lambda *a, **kw: fake)
    app.dependency_overrides[get_deps] = lambda: _base_deps()
    headers = _mint(client)
    body = {"interests": ["stoicism"], "level": "beginner", "goal": "calm"}

    assert client.post("/v1/roadmap", json=body, headers=headers).status_code == 200
    denied = client.post("/v1/roadmap", json=body, headers=headers)
    assert denied.status_code == 429


def test_demo_mentor_returns_429_when_principal_already_at_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _demo_db(tmp_path, monkeypatch, mode="demo", limit="1")
    conn = connect(db_path)
    session = create_demo_session(conn)
    consume_demo_llm_quota(conn, session.principal_id, limit=1)
    conn.close()

    denied = client.post(
        "/v1/mentor/intake",
        json={"goal": "learn", "interests": ["stoicism"]},
        headers={"X-Demo-Session": session.id},
    )
    assert denied.status_code == 429
    assert "Daily demo LLM limit" in denied.json()["detail"]


def test_demo_mentor_intake_counts_toward_daily_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _demo_db(tmp_path, monkeypatch, mode="demo", limit="1")
    fake = MentorIntakeResponse(request_id="m1", rationale="ok")
    monkeypatch.setattr("apps.api.v2_routes.mentor_intake", lambda *a, **k: fake)
    monkeypatch.setattr("apps.api.main.get_deps", lambda: _base_deps())
    headers = _mint(client)
    body = {"goal": "learn", "interests": ["stoicism"]}

    first = client.post("/v1/mentor/intake", json=body, headers=headers)
    second = client.post("/v1/mentor/intake", json=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 429
