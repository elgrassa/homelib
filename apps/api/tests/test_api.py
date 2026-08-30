"""Behavioural tests for `apps/api` — see specs/api.md.

No live Postgres, no live LLM, no model download: every DB/LLM-touching field
of `apps.api.main.Deps` is overridden via `app.dependency_overrides[get_deps]`
with a scripted fake per test. The one exception is
`test_health_never_leaks_key_material`, which deliberately constructs the
REAL `homelib_rag.answer.OpenAIClient` (to exercise real key handling) while
still stubbing out the network-reachability check — see that test's comment.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from homelib_core.models import Block, ExtractionResult, Provenance
from homelib_rag import answer as answer_module
from homelib_rag.answer import LLMResponse, LLMUnreachableError, LLMUsage
from homelib_rag.models import Hit
from homelib_rag.roadmap import RoadmapParseError, RoadmapResponse

import apps.api.main as main
from apps.api.main import Deps, QueryLogRow, app, get_deps
from apps.api.schemas import BookSummary, IngestResponse

client = TestClient(app)


class _ScriptedClient:
    """A scripted fake `OpenAICompatibleClient`. No network."""

    model = "fake-model"

    def __init__(self, responses: list[LLMResponse | Exception] | None = None) -> None:
        self._responses = list(responses or [])

    def chat(
        self,
        messages: Any,
        *,
        tools: Any = None,
        response_format: Any = None,
    ) -> LLMResponse:
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _llm_json(answer_text: str, citations: list[dict[str, Any]]) -> LLMResponse:
    return LLMResponse(
        content=json.dumps({"answer": answer_text, "citations": citations}),
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5),
    )


def _missing_block(block_id: str) -> Block:
    raise KeyError(block_id)


def _unimplemented_ingest(req: Any) -> IngestResponse:
    raise NotImplementedError("test did not configure deps.ingest")


def _base_deps() -> Deps:
    return Deps(
        llm_client=_ScriptedClient(),
        llm_provider="ollama",
        llm_reachable=lambda: True,
        db_reachable=lambda: True,
        counts=lambda: (0, 0),
        retrieve=lambda query, k, arm: ([], arm, False),
        rewrite_query=lambda query: query,
        catalog_search=lambda query, subjects=None: [],
        list_books=lambda: [],
        get_block=_missing_block,
        log_query=lambda row: None,
        record_feedback=lambda request_id, feedback, comment: True,
        ingest=_unimplemented_ingest,
    )


def _make_deps(**overrides: Any) -> Deps:
    return replace(_base_deps(), **overrides)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Any:
    yield
    app.dependency_overrides.clear()


def _hit(chunk_id: str = "c1", book_id: str = "b1", text: str = "The fox jumps high.") -> Hit:
    return Hit(
        chunk_id=chunk_id, book_id=book_id, score=1.0, rank=1, text=text, section_path=[], page=None
    )


# ── Named red tests ─────────────────────────────────────────────────────────


def test_health_never_leaks_key_material(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/health` reports booleans only about the LLM — no substring of the
    configured key ever appears in the body. Uses the REAL `OpenAIClient` so
    the key is genuinely loaded into the process, only stubbing the network
    reachability probe (never the key material itself)."""
    secret = "sk-THIS_IS_A_SECRET_TOKEN_1234567890"
    monkeypatch.setenv("LLM_API_KEY", secret)
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b-instruct")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")

    real_client = answer_module.OpenAIClient()
    deps = _make_deps(
        llm_client=real_client,
        llm_provider="ollama",
        llm_reachable=lambda: True,
        db_reachable=lambda: True,
        counts=lambda: (3, 100),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/health")

    assert resp.status_code == 200
    assert secret not in resp.text
    body = resp.json()
    assert body["llm"]["model"] == "qwen2.5:7b-instruct"
    assert body["llm"]["reachable"] is True
    assert "key" not in body["llm"]


def test_feedback_unknown_request_id_returns_404() -> None:
    deps = _make_deps(record_feedback=lambda request_id, feedback, comment: False)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/feedback", json={"request_id": "does-not-exist", "feedback": "up"})

    assert resp.status_code == 404


def test_ask_degrades_to_200_when_vector_backend_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vector search "raises" (simulated at the retrieve seam): response is
    200 with `degraded is True` and `arm_used == "lexical"`."""
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    hit = _hit()

    def _retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str, bool]:
        # hybrid_search already fell back to lexical-only because the vector
        # backend raised — see homelib_rag.hybrid's own degrade contract.
        return ([hit], "lexical", True)

    fake_llm = _ScriptedClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])
    deps = _make_deps(retrieve=_retrieve, llm_client=fake_llm)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "does it jump?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert body["arm_used"] == "lexical"


def test_ask_writes_query_log_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    hit = _hit()
    logged: list[QueryLogRow] = []
    fake_llm = _ScriptedClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([hit], "hybrid", False),
        llm_client=fake_llm,
        log_query=logged.append,
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "does it jump?", "rewrite": False})

    assert resp.status_code == 200
    body = resp.json()
    assert len(logged) == 1
    row = logged[0]
    assert row.request_id == body["request_id"]
    assert row.arm == "hybrid"
    assert row.k == 5
    assert row.rewrite is False
    assert row.degraded is False
    assert row.model == "fake-model"
    assert len(row.query_sha256_prefix) == 16


def test_openapi_snapshot_matches() -> None:
    """Placeholder home for the drift-guard assertion — the real, spec-named
    test lives in `evals/tests/test_openapi_snapshot.py` (specs/api.md's
    Verify section names that exact path). Kept here too so a change to this
    app's route table is caught from within this test module as well."""
    schema = app.openapi()
    paths = set(schema["paths"])
    expected = {
        "/health",
        "/v1/ask",
        "/v1/roadmap",
        "/v1/ingest",
        "/v1/feedback",
        "/v1/books",
        "/v1/blocks/{block_id}",
    }
    assert expected <= paths


# ── /health ──────────────────────────────────────────────────────────────


def test_health_degraded_when_db_down() -> None:
    deps = _make_deps(db_reachable=lambda: False, llm_reachable=lambda: True)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/health")

    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "degraded"
    assert body["db"] is False
    assert body["books"] == 0
    assert body["chunks"] == 0


def test_health_ok_when_everything_reachable() -> None:
    deps = _make_deps(db_reachable=lambda: True, llm_reachable=lambda: True, counts=lambda: (5, 50))
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/health")

    body = resp.json()
    assert body["status"] == "ok"
    assert body["books"] == 5
    assert body["chunks"] == 50


# ── /v1/ask ──────────────────────────────────────────────────────────────


def test_ask_arm_none_uses_default_arm() -> None:
    captured: dict[str, Any] = {}

    def _retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str, bool]:
        captured["arm"] = arm
        return ([], arm, False)

    deps = _make_deps(retrieve=_retrieve, llm_client=_ScriptedClient([_llm_json("ok", [])]))
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q"})

    assert resp.status_code == 200
    assert captured["arm"] == "hybrid_rerank"


def test_ask_explicit_arm_is_honored() -> None:
    captured: dict[str, Any] = {}

    def _retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str, bool]:
        captured["arm"] = arm
        return ([], arm, False)

    deps = _make_deps(retrieve=_retrieve, llm_client=_ScriptedClient([_llm_json("ok", [])]))
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q", "arm": "lexical"})

    assert resp.status_code == 200
    assert captured["arm"] == "lexical"


def test_ask_rewrite_flag_reflected_in_query_log() -> None:
    logged: list[QueryLogRow] = []
    deps = _make_deps(
        rewrite_query=lambda query: "rewritten " + query,
        llm_client=_ScriptedClient([_llm_json("ok", [])]),
        log_query=logged.append,
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q", "rewrite": True})

    assert resp.status_code == 200
    assert logged[0].rewrite is True


def test_ask_no_rewrite_when_disabled() -> None:
    captured: dict[str, Any] = {}

    def _rewrite(query: str) -> str:
        captured["called"] = True
        return "should not be used " + query

    deps = _make_deps(rewrite_query=_rewrite, llm_client=_ScriptedClient([_llm_json("ok", [])]))
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q", "rewrite": False})

    assert resp.status_code == 200
    assert "called" not in captured


def test_ask_validation_rejects_unknown_field() -> None:
    resp = client.post("/v1/ask", json={"query": "q", "bogus_field": 1})
    assert resp.status_code == 422


# ── /v1/roadmap ──────────────────────────────────────────────────────────


def test_roadmap_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = RoadmapResponse(request_id="r1", steps=[], rationale="ok")
    monkeypatch.setattr(main.roadmap_module, "build_roadmap", lambda *a, **kw: fake_response)
    app.dependency_overrides[get_deps] = lambda: _base_deps()

    resp = client.post(
        "/v1/roadmap", json={"interests": ["stoicism"], "level": "beginner", "goal": "calm"}
    )

    assert resp.status_code == 200
    assert resp.json()["request_id"] == "r1"


def test_roadmap_parse_error_maps_to_502(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: Any, **kwargs: Any) -> RoadmapResponse:
        raise RoadmapParseError("could not parse")

    monkeypatch.setattr(main.roadmap_module, "build_roadmap", _raise)
    app.dependency_overrides[get_deps] = lambda: _base_deps()

    resp = client.post("/v1/roadmap", json={"interests": [], "level": "beginner", "goal": "x"})

    assert resp.status_code == 502
    assert "detail" in resp.json()


def test_roadmap_llm_unreachable_maps_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: Any, **kwargs: Any) -> RoadmapResponse:
        raise LLMUnreachableError("endpoint down")

    monkeypatch.setattr(main.roadmap_module, "build_roadmap", _raise)
    app.dependency_overrides[get_deps] = lambda: _base_deps()

    resp = client.post("/v1/roadmap", json={"interests": [], "level": "beginner", "goal": "x"})

    assert resp.status_code == 503


# ── /v1/ingest ───────────────────────────────────────────────────────────


def test_ingest_delegates_to_deps() -> None:
    fake_resp = IngestResponse(
        book_id="bk1",
        blocks=3,
        chunks=9,
        extraction=ExtractionResult(
            method="native_text",
            extractor_name="test",
            extractor_version="1.0",
            extraction_sha256="",
            warnings=[],
        ),
    )
    deps = _make_deps(ingest=lambda req: fake_resp)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ingest", json={"source": "snapshot"})

    assert resp.status_code == 200
    assert resp.json()["book_id"] == "bk1"


def test_ingest_rejects_both_path_and_source() -> None:
    resp = client.post("/v1/ingest", json={"path": "x.txt", "source": "snapshot"})
    assert resp.status_code == 422


def test_ingest_rejects_neither_path_nor_source() -> None:
    resp = client.post("/v1/ingest", json={})
    assert resp.status_code == 422


def test_ingest_file_not_found_maps_to_404() -> None:
    def _raise(req: Any) -> IngestResponse:
        raise FileNotFoundError("no such file")

    deps = _make_deps(ingest=_raise)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ingest", json={"path": "missing.txt"})

    assert resp.status_code == 404


def test_ingest_generic_failure_maps_to_502() -> None:
    def _raise(req: Any) -> IngestResponse:
        raise RuntimeError("boom")

    deps = _make_deps(ingest=_raise)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ingest", json={"path": "x.txt"})

    assert resp.status_code == 502


# ── /v1/feedback ─────────────────────────────────────────────────────────


def test_feedback_success() -> None:
    deps = _make_deps(record_feedback=lambda request_id, feedback, comment: True)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post(
        "/v1/feedback", json={"request_id": "r1", "feedback": "down", "comment": "meh"}
    )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ── /v1/books ────────────────────────────────────────────────────────────


def test_get_books() -> None:
    summary = BookSummary(
        book_id="bk1", title="T", authors=["A"], blocks=3, chunks=10, format="txt"
    )
    deps = _make_deps(list_books=lambda: [summary])
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/v1/books")

    assert resp.status_code == 200
    assert resp.json() == [
        {
            "book_id": "bk1",
            "title": "T",
            "authors": ["A"],
            "blocks": 3,
            "chunks": 10,
            "format": "txt",
        }
    ]


# ── /v1/blocks/{block_id} ────────────────────────────────────────────────


def test_get_block_endpoint_not_found() -> None:
    deps = _make_deps(get_block=_missing_block)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/v1/blocks/missing")

    assert resp.status_code == 404


def test_get_block_endpoint_found() -> None:
    block = Block(
        block_id="b1",
        book_id="bk1",
        ordinal=0,
        section_path=["Ch1"],
        text="hi",
        char_start=0,
        char_end=2,
        provenance=Provenance(format="txt", source_sha256=""),
    )
    deps = _make_deps(get_block=lambda block_id: block)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/v1/blocks/b1")

    assert resp.status_code == 200
    assert resp.json()["block_id"] == "b1"
    assert resp.json()["book_id"] == "bk1"


# ── Deps production wiring sanity ───────────────────────────────────────────


def test_infer_provider_variants() -> None:
    assert main._infer_provider("http://localhost:11434/v1") == "ollama"
    assert main._infer_provider("https://api.openai.com/v1") == "openai"
    assert main._infer_provider("https://api.anthropic.com/v1") == "anthropic"
    assert main._infer_provider("http://ollama:11434/v1") == "ollama"


def test_query_sha256_prefix_is_16_hex_chars() -> None:
    prefix = main._query_sha256_prefix("hello world")
    assert len(prefix) == 16
    assert all(c in "0123456789abcdef" for c in prefix)


def test_resolve_arm_defaults_to_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOMELIB_DEFAULT_ARM", raising=False)
    assert main._resolve_arm(None) == "hybrid_rerank"
    assert main._resolve_arm("lexical") == "lexical"


def test_resolve_arm_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMELIB_DEFAULT_ARM", "vector")
    assert main._resolve_arm(None) == "vector"


def test_default_retrieve_unknown_arm_raises() -> None:
    with pytest.raises(ValueError, match="unknown arm"):
        main._default_retrieve("q", 5, "not-a-real-arm")


def test_default_retrieve_degrades_when_both_arms_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(q: str, k: int, *, mode: str) -> tuple[list[Hit], str]:
        raise ConnectionError("db down")

    monkeypatch.setattr(main, "hybrid_search", _raise)

    hits, arm_used, degraded = main._default_retrieve("q", 5, "hybrid")

    assert hits == []
    assert degraded is True
    assert arm_used == "hybrid"


def test_default_retrieve_applies_rerank_for_hybrid_rerank(monkeypatch: pytest.MonkeyPatch) -> None:
    hit = _hit()
    monkeypatch.setattr(main, "hybrid_search", lambda q, k, *, mode: ([hit], "hybrid"))
    monkeypatch.setattr(main, "rerank", lambda q, hits: list(reversed(hits)))

    _hits, arm_used, degraded = main._default_retrieve("q", 5, "hybrid_rerank")

    assert arm_used == "hybrid_rerank"
    assert degraded is False


def test_default_retrieve_keeps_hybrid_order_when_rerank_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hit = _hit()
    monkeypatch.setattr(main, "hybrid_search", lambda q, k, *, mode: ([hit], "hybrid"))
    monkeypatch.setattr(main, "rerank", lambda q, hits: None)

    _hits, arm_used, degraded = main._default_retrieve("q", 5, "hybrid_rerank")

    assert arm_used == "hybrid"
    assert degraded is False  # rerank unavailability is never a degradation
