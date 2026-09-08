"""Behavioural tests for `apps/api` — see specs/api.md.

No live Postgres, no live LLM, no model download: every DB/LLM-touching field
of `apps.api.main.Deps` is overridden via `app.dependency_overrides[get_deps]`
with a scripted fake per test. The one exception is
`test_health_never_leaks_key_material`, which deliberately constructs the
REAL `homelib_rag.answer.OpenAIClient` (to exercise real key handling) while
still stubbing out the network-reachability check — see that test's comment.
"""

from __future__ import annotations

import concurrent.futures
import json
import threading
import time
from dataclasses import replace
from typing import Any

import httpx
import psycopg
import pytest
import respx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from homelib_core.models import Block, ExtractionResult, Provenance
from homelib_rag import answer as answer_module
from homelib_rag.answer import LLMResponse, LLMUnreachableError, LLMUsage
from homelib_rag.models import Hit
from homelib_rag.roadmap import RoadmapParseError, RoadmapResponse

import apps.api.main as main
from apps.api.main import Deps, QueryLogRow, app, get_deps
from apps.api.schemas import BookSummary, IngestResponse
from apps.store.sqlite import connect as sqlite_connect
from apps.store.sqlite import migrate as sqlite_migrate

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
        max_tokens: int = 400,
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


def _missing_book_block(book_id: str, ordinal: int) -> Block:
    raise KeyError(f"{book_id}@{ordinal}")


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
        get_book_block=_missing_book_block,
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


@pytest.fixture(autouse=True)
def _reset_tracer() -> Any:
    """Every test gets a fresh tracer provider, built lazily on next
    `get_tracer()` call from whatever env is set at that point — mirrors
    `test_v2_routes.py`'s `_reset_api_deps` for `apps.api.main._deps_singleton`.
    A test that wants to inspect spans overrides this via
    `tracing.reset_tracer_for_tests(some_provider)` after this fixture runs.
    """
    from apps.api import tracing

    tracing.reset_tracer_for_tests(None)
    yield
    tracing.reset_tracer_for_tests(None)


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

    deps = _make_deps(
        retrieve=_retrieve,
        llm_client=_ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])]),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q"})

    assert resp.status_code == 200
    assert captured["arm"] == "hybrid_rerank"


def test_ask_explicit_arm_is_honored() -> None:
    captured: dict[str, Any] = {}

    def _retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str, bool]:
        captured["arm"] = arm
        return ([], arm, False)

    deps = _make_deps(
        retrieve=_retrieve,
        llm_client=_ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])]),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q", "arm": "lexical"})

    assert resp.status_code == 200
    assert captured["arm"] == "lexical"


def test_ask_rewrite_flag_reflected_in_query_log() -> None:
    logged: list[QueryLogRow] = []
    deps = _make_deps(
        rewrite_query=lambda query: "rewritten " + query,
        llm_client=_ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])]),
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

    deps = _make_deps(
        rewrite_query=_rewrite,
        llm_client=_ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])]),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q", "rewrite": False})

    assert resp.status_code == 200
    assert "called" not in captured


def test_ask_rewrite_defaults_to_false_when_omitted() -> None:
    """ADR-001 (docs/adrs/ADR-001-retrieval-arm.md) measured query rewriting
    against hybrid_rerank and rejected it — a request that does not name
    `rewrite` at all must not silently rewrite anyway."""
    captured: dict[str, Any] = {}

    def _rewrite(query: str) -> str:
        captured["called"] = True
        return "should not be used " + query

    deps = _make_deps(
        rewrite_query=_rewrite,
        llm_client=_ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])]),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q"})

    assert resp.status_code == 200
    assert "called" not in captured


def test_ask_validation_rejects_unknown_field() -> None:
    resp = client.post("/v1/ask", json={"query": "q", "bogus_field": 1})
    assert resp.status_code == 422


def test_ask_walden_still_uses_passage_citation_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passage content Q must still retrieve + cite; shelf-meta must not short-circuit."""
    retrieve_calls: list[str] = []
    hit = Hit(
        chunk_id="c-walden",
        book_id="b-walden",
        score=1.0,
        rank=1,
        text="by Henry David Thoreau",
        section_path=["Economy"],
        page=1,
        block_ids=["blk-1"],
    )

    def _retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str, bool]:
        retrieve_calls.append(query)
        return ([hit], arm, False)

    monkeypatch.setattr(
        answer_module,
        "_book_metadata",
        lambda book_ids: {bid: ("Walden", ["Henry David Thoreau"]) for bid in book_ids},
    )
    llm = _ScriptedClient(
        [_llm_json("Henry David Thoreau", [{"passage": 1, "quote": "by Henry David Thoreau"}])]
    )
    deps = _make_deps(
        retrieve=_retrieve,
        llm_client=llm,
        list_books=lambda: [
            BookSummary(
                book_id="b-walden",
                title="Walden",
                authors=["Henry David Thoreau"],
                blocks=1,
                chunks=1,
                format="txt",
            )
        ],
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "Who wrote Walden?"})

    assert resp.status_code == 200
    body = resp.json()
    assert retrieve_calls == ["Who wrote Walden?"]
    assert body["answer"] == "Henry David Thoreau"
    assert body["arm_used"] != "shelf_meta"
    assert len(body["citations"]) == 1
    assert body["citations"][0]["quote"] == "by Henry David Thoreau"


def test_ask_what_do_you_have_uses_shelf_metadata_not_passage_abstain() -> None:
    """Inventory Ask must list books via list_books — never empty passage refuse."""
    retrieve_calls: list[str] = []

    def _retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str, bool]:
        retrieve_calls.append(query)
        return ([], arm, False)

    deps = _make_deps(
        retrieve=_retrieve,
        llm_client=_ScriptedClient([]),  # must not be called
        list_books=lambda: [
            BookSummary(
                book_id="b1",
                title="Walden, and On The Duty Of Civil Disobedience",
                authors=["Henry David Thoreau"],
                blocks=10,
                chunks=20,
                format="txt",
            ),
            BookSummary(
                book_id="b2",
                title="Meditations",
                authors=["Marcus Aurelius"],
                blocks=5,
                chunks=8,
                format="txt",
            ),
        ],
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "what do you have"})

    assert resp.status_code == 200
    body = resp.json()
    assert retrieve_calls == []
    assert body["arm_used"] == "shelf_meta"
    assert body["degraded"] is False
    assert body["citations"] == []
    assert "Walden" in body["answer"]
    assert "Meditations" in body["answer"]
    assert body["answer"].strip() != ""


def test_demo_poisoned_hybrid_cache_does_not_block_shelf_meta(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P0 Cloud bug: inventory Q cached as passage refuse under arm=hybrid must
    not win over shelf_meta after the Ask contract lands."""
    from homelib_rag.answer import AskResponse as RagAskResponse
    from homelib_rag.answer import TokenUsage

    from apps.store import answer_cache

    db_path = tmp_path / "poison_cache.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    poisoned = RagAskResponse(
        request_id="poison",
        answer="I don't have an answer.",
        citations=[],
        arm_used="hybrid",
        degraded=False,
        latency_ms=1,
        tokens=TokenUsage(prompt=1987, completion=40),
    )
    key = answer_cache.cache_key("what do you have", arm="hybrid", model="fake-model")
    answer_cache.store(conn, key, poisoned)
    conn.close()

    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("APP_MODE", "demo")
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([], arm, False),
        llm_client=_ScriptedClient([]),
        list_books=lambda: [
            BookSummary(
                book_id="b1",
                title="Walden",
                authors=["Henry David Thoreau"],
                blocks=1,
                chunks=1,
                format="txt",
            ),
        ],
    )
    app.dependency_overrides[get_deps] = lambda: deps
    headers = {"X-Demo-Session": client.post("/v1/demo/session").json()["demo_session_id"]}

    resp = client.post("/v1/ask", json={"query": "what do you have"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["arm_used"] == "shelf_meta"
    assert body["cache_hit"] is False
    assert "Walden" in body["answer"]
    assert "I don't have an answer" not in body["answer"]


def test_ask_romance_from_available_lists_shelf_instead_of_empty_abstain() -> None:
    deps = _make_deps(
        retrieve=lambda query, k, arm: (_ for _ in ()).throw(AssertionError("no retrieve")),
        llm_client=_ScriptedClient([]),
        list_books=lambda: [
            BookSummary(
                book_id="b1",
                title="The Prince",
                authors=["Niccolò Machiavelli"],
                blocks=3,
                chunks=4,
                format="txt",
            )
        ],
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "which available romance book should I read?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["arm_used"] == "shelf_meta"
    assert "romance" in body["answer"].lower()
    assert "The Prince" in body["answer"]
    assert body["citations"] == []


# ── C1: cost in $ (specs/monitoring.md) ─────────────────────────────────


def test_cost_usd_zero_under_local_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither `LLM_PRICE_PER_1K_*` var set (the compose/Ollama default):
    `query_log.cost_usd` is 0 even though real tokens were spent."""
    monkeypatch.delenv("LLM_PRICE_PER_1K_PROMPT", raising=False)
    monkeypatch.delenv("LLM_PRICE_PER_1K_COMPLETION", raising=False)
    logged: list[QueryLogRow] = []
    fake_llm = _ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])])
    deps = _make_deps(
        llm_client=fake_llm,
        log_query=logged.append,
        retrieve=lambda query, k, arm: ([_hit()], arm, False),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q"})

    assert resp.status_code == 200
    assert logged[0].cost_usd == 0.0


def test_cost_usd_computed_from_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    """With both prices set, `cost_usd` is
    `tokens_prompt/1000 * prompt_price + tokens_completion/1000 * completion_price`
    — the `_llm_json` fake above always reports 10 prompt / 5 completion tokens
    (see `_llm_json`), so the expected value is computed the same way here."""
    monkeypatch.setenv("LLM_PRICE_PER_1K_PROMPT", "2.0")
    monkeypatch.setenv("LLM_PRICE_PER_1K_COMPLETION", "4.0")
    logged: list[QueryLogRow] = []
    fake_llm = _ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])])
    deps = _make_deps(
        llm_client=fake_llm,
        log_query=logged.append,
        retrieve=lambda query, k, arm: ([_hit()], arm, False),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q"})

    assert resp.status_code == 200
    body = resp.json()
    expected = (body["tokens"]["prompt"] / 1000) * 2.0 + (body["tokens"]["completion"] / 1000) * 4.0
    assert logged[0].cost_usd == pytest.approx(expected)
    assert logged[0].cost_usd > 0.0


# ── C6: online judge — answer_log opt-in (specs/monitoring.md) ───────────


def test_answer_log_off_by_default(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """`HOMELIB_LOG_ANSWERS` unset (the default): a real /v1/ask call, with a
    real SQLite store configured, writes no `answer_log` row at all — the
    question's plaintext is never persisted unless an operator opts in."""
    db_path = tmp_path / "answers_off.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    monkeypatch.delenv("HOMELIB_LOG_ANSWERS", raising=False)
    deps = _make_deps(
        llm_client=_ScriptedClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "does it jump?"})

    assert resp.status_code == 200
    check = sqlite_connect(db_path)
    count = check.execute("SELECT COUNT(*) FROM answer_log").fetchone()[0]
    check.close()
    assert count == 0


def test_answer_log_written_when_enabled(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """`HOMELIB_LOG_ANSWERS=1` plus a real SQLite store: the question and
    answer ARE persisted, keyed by the same request_id as `query_log`."""
    db_path = tmp_path / "answers_on.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("HOMELIB_LOG_ANSWERS", "1")
    deps = _make_deps(
        llm_client=_ScriptedClient(
            [_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])]
        ),
        retrieve=lambda query, k, arm: ([_hit()], arm, False),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "does it jump?"})

    assert resp.status_code == 200
    request_id = resp.json()["request_id"]
    check = sqlite_connect(db_path)
    row = check.execute(
        "SELECT question, answer FROM answer_log WHERE request_id = ?", (request_id,)
    ).fetchone()
    check.close()
    assert row is not None
    assert row[0] == "does it jump?"
    assert row[1] == "It jumps."


# ── C5: OpenTelemetry tracing (specs/monitoring.md "Tracing") ────────────


def _in_memory_tracer_provider() -> Any:
    """A `TracerProvider` wired to an `InMemorySpanExporter`, synchronously
    (`SimpleSpanProcessor`) so a test can inspect spans right after the
    request returns — no `force_flush()` needed, unlike the real
    `BatchSpanProcessor` path used in selfhosted mode."""
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_ask_emits_stage_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rewritten /v1/ask call emits every stage span the handler owns: the
    root `homelib.ask`, plus `cache` (always opened; a no-op miss outside
    APP_MODE=demo), `rewrite`, `retrieve`, `llm`, `cite` as children.
    `rerank` is emitted by the production retrieve seam around the real
    cross-encoder call (see `test_default_retrieve_emits_timed_rerank_span`),
    so a scripted `retrieve` fake — as here — never shows one: a trace must
    never claim a stage that did not run."""
    from apps.api import tracing

    provider, exporter = _in_memory_tracer_provider()
    tracing.reset_tracer_for_tests(provider)
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    hit = _hit()
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([hit], "hybrid_rerank", False),
        rewrite_query=lambda query: "rewritten " + query,
        llm_client=_ScriptedClient(
            [_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])]
        ),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "does it jump?", "rewrite": True})

    assert resp.status_code == 200
    span_names = {span.name for span in exporter.get_finished_spans()}
    assert span_names == {"homelib.ask", "cache", "rewrite", "retrieve", "llm", "cite"}


def test_ask_omits_optional_stage_spans_when_not_used() -> None:
    """No rewrite requested and a non-reranking arm: `rewrite`/`rerank` never
    appear — a trace never shows a stage that did not run."""
    from apps.api import tracing

    provider, exporter = _in_memory_tracer_provider()
    tracing.reset_tracer_for_tests(provider)
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([], "lexical", False),
        llm_client=_ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])]),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "q", "arm": "lexical"})

    assert resp.status_code == 200
    span_names = {span.name for span in exporter.get_finished_spans()}
    assert span_names == {"homelib.ask", "cache", "retrieve", "llm", "cite"}


def test_spans_never_carry_raw_question_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api import tracing

    monkeypatch.delenv("HOMELIB_TRACE_QUESTIONS", raising=False)
    provider, exporter = _in_memory_tracer_provider()
    tracing.reset_tracer_for_tests(provider)
    deps = _make_deps(
        llm_client=_ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])])
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "a very unique raw question xyz123"})

    assert resp.status_code == 200
    for span in exporter.get_finished_spans():
        for value in (span.attributes or {}).values():
            assert "xyz123" not in str(value)


def test_spans_carry_question_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api import tracing

    monkeypatch.setenv("HOMELIB_TRACE_QUESTIONS", "1")
    provider, exporter = _in_memory_tracer_provider()
    tracing.reset_tracer_for_tests(provider)
    deps = _make_deps(
        llm_client=_ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])])
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "a very unique raw question xyz123"})

    assert resp.status_code == 200
    root = next(s for s in exporter.get_finished_spans() if s.name == "homelib.ask")
    assert root.attributes is not None
    assert root.attributes["question"] == "a very unique raw question xyz123"


def test_traces_endpoint_returns_tree(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api import tracing

    db_path = tmp_path / "traces.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    # demo -> SimpleSpanProcessor, so the export is synchronous and the trace
    # is already on disk by the time /v1/traces is called below.
    monkeypatch.setenv("APP_MODE", "demo")
    tracing.reset_tracer_for_tests(None)
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    hit = _hit()
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([hit], "hybrid", False),
        llm_client=_ScriptedClient(
            [_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])]
        ),
    )
    app.dependency_overrides[get_deps] = lambda: deps
    headers = {"X-Demo-Session": client.post("/v1/demo/session").json()["demo_session_id"]}

    ask_resp = client.post("/v1/ask", json={"query": "does it jump?"}, headers=headers)
    assert ask_resp.status_code == 200
    trace_id = ask_resp.json()["trace_id"]
    assert trace_id

    trace_resp = client.get(f"/v1/traces/{trace_id}")

    assert trace_resp.status_code == 200
    body = trace_resp.json()
    assert body["trace_id"] == trace_id
    root = next(s for s in body["spans"] if s["name"] == "homelib.ask")
    child_names = {child["name"] for child in root["children"]}
    assert {"retrieve", "llm", "cite"} <= child_names
    assert all("duration_ms" in s for s in [root, *root["children"]])


def test_ask_flushes_batch_spans_so_selfhosted_traces_include_llm(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Selfhosted uses BatchSpanProcessor; without force_flush after /v1/ask,
    /v1/traces can miss llm (and its tokens_prompt/completion attrs)."""
    from apps.api import tracing

    db_path = tmp_path / "batch_traces.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("APP_MODE", "selfhosted")
    tracing.reset_tracer_for_tests(None)
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    hit = _hit()
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([hit], "hybrid", False),
        llm_client=_ScriptedClient(
            [_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])]
        ),
    )
    app.dependency_overrides[get_deps] = lambda: deps

    ask_resp = client.post("/v1/ask", json={"query": "does it jump?"})
    assert ask_resp.status_code == 200
    body = ask_resp.json()
    assert body["tokens"]["prompt"] >= 0
    assert body["tokens"]["completion"] >= 0
    trace_id = body["trace_id"]
    assert trace_id

    trace_resp = client.get(f"/v1/traces/{trace_id}")
    assert trace_resp.status_code == 200
    tree = trace_resp.json()["spans"]

    def _walk(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for node in nodes:
            out.append(node)
            out.extend(_walk(list(node.get("children") or [])))
        return out

    by_name = {node["name"]: node for node in _walk(tree)}
    assert {"homelib.ask", "llm", "cite"} <= set(by_name)
    assert "tokens_prompt" in by_name["llm"]["attributes"]
    assert "tokens_completion" in by_name["llm"]["attributes"]


def test_traces_without_sqlite_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)
    resp = client.get("/v1/traces/does-not-exist")
    assert resp.status_code == 503


def test_traces_unknown_trace_id_404(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "empty_traces.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))

    resp = client.get("/v1/traces/does-not-exist")

    assert resp.status_code == 404


# ── C4b: demo answer cache (specs/monitoring.md "Demo answer cache") ─────


class _CountingClient(_ScriptedClient):
    """Same scripted fake, but counts real `chat()` calls — a cache hit
    must never reach this at all, so the count is the real assertion."""

    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        super().__init__(responses)
        self.calls = 0

    def chat(self, *args: Any, **kwargs: Any) -> LLMResponse:
        self.calls += 1
        return super().chat(*args, **kwargs)


def test_demo_ask_serves_cached_answer_on_repeat(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """APP_MODE=demo: asking the SAME question twice calls the LLM once —
    the second call is served from `answer_cache` (only one scripted
    response is even configured below, so a second real call would itself
    raise `IndexError` and fail this test)."""
    db_path = tmp_path / "cache_demo.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    hit = _hit()
    fake_llm = _CountingClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([hit], "hybrid", False),
        llm_client=fake_llm,
    )
    app.dependency_overrides[get_deps] = lambda: deps
    headers = {"X-Demo-Session": client.post("/v1/demo/session").json()["demo_session_id"]}

    first = client.post(
        "/v1/ask", json={"query": "does it jump?", "arm": "hybrid"}, headers=headers
    )
    second = client.post(
        "/v1/ask", json={"query": "does it jump?", "arm": "hybrid"}, headers=headers
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert fake_llm.calls == 1
    assert first.json()["cache_hit"] is False
    assert second.json()["cache_hit"] is True
    assert second.json()["answer"] == first.json()["answer"]
    # A cache hit still gets its own request_id/trace_id — never a
    # byte-for-byte replay of the first response's envelope.
    assert second.json()["request_id"] != first.json()["request_id"]


def test_selfhosted_ask_never_reads_answer_cache(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-seeded cache entry for the exact key this request would compute
    is ignored in selfhosted mode — the LLM is called and its live answer
    wins, never the stale cached one."""
    from homelib_rag.answer import AskResponse as RagAskResponse
    from homelib_rag.answer import TokenUsage

    from apps.store import answer_cache

    db_path = tmp_path / "cache_selfhosted.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    stale = RagAskResponse(
        request_id="stale-req",
        answer="STALE CACHED ANSWER",
        citations=[],
        arm_used="hybrid",
        degraded=False,
        latency_ms=1,
        tokens=TokenUsage(prompt=1, completion=1),
    )
    key = answer_cache.cache_key("does it jump?", arm="hybrid", model="fake-model")
    answer_cache.store(conn, key, stale)
    conn.close()

    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("APP_MODE", "selfhosted")
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    hit = _hit()
    fake_llm = _CountingClient(
        [_llm_json("Fresh live answer.", [{"passage": 1, "quote": "fox jumps"}])]
    )
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([hit], "hybrid", False),
        llm_client=fake_llm,
    )
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ask", json={"query": "does it jump?", "arm": "hybrid"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Fresh live answer."
    assert body["cache_hit"] is False
    assert fake_llm.calls == 1


def test_cache_hit_is_logged_and_flagged(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The `query_log` row for a cache hit has `cache_hit=True` — captured
    via the same scripted `log_query` fake every other query_log test uses,
    independent of the real sqlite write path."""
    db_path = tmp_path / "cache_logged.sqlite"
    conn = sqlite_connect(db_path)
    sqlite_migrate(conn)
    conn.close()
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata", lambda book_ids: {"b1": ("Title", ["Author"])}
    )
    hit = _hit()
    logged: list[QueryLogRow] = []
    fake_llm = _CountingClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])
    deps = _make_deps(
        retrieve=lambda query, k, arm: ([hit], "hybrid", False),
        llm_client=fake_llm,
        log_query=logged.append,
    )
    app.dependency_overrides[get_deps] = lambda: deps
    headers = {"X-Demo-Session": client.post("/v1/demo/session").json()["demo_session_id"]}

    client.post("/v1/ask", json={"query": "does it jump?", "arm": "hybrid"}, headers=headers)
    client.post("/v1/ask", json={"query": "does it jump?", "arm": "hybrid"}, headers=headers)

    assert len(logged) == 2
    assert logged[0].cache_hit is False
    assert logged[1].cache_hit is True
    # No new LLM spend on a cache hit, regardless of LLM_PRICE_PER_1K_*.
    assert logged[1].cost_usd == 0.0


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


def test_books_block_by_ordinal_returns_page() -> None:
    block = Block(
        block_id="b1",
        book_id="walden",
        ordinal=2,
        section_path=["Ch"],
        text="page two",
        char_start=10,
        char_end=18,
        provenance=Provenance(format="txt", source_sha256=""),
    )
    deps = _make_deps(get_book_block=lambda book_id, ordinal: block)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/v1/books/walden/blocks", params={"ordinal": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert body["book_id"] == "walden"
    assert body["ordinal"] == 2
    assert body["text"] == "page two"


def test_books_block_by_ordinal_not_found() -> None:
    deps = _make_deps(get_book_block=_missing_book_block)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/v1/books/missing/blocks", params={"ordinal": 0})

    assert resp.status_code == 404


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


def test_default_retrieve_emits_timed_rerank_span(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `rerank` span wraps the real cross-encoder call inside the
    production retrieve seam, so `time_per_stage` reports what reranking
    costs (candidates in, whether it applied) instead of a zero-length
    marker opened after the fact."""
    from apps.api import tracing

    provider, exporter = _in_memory_tracer_provider()
    tracing.reset_tracer_for_tests(provider)
    hit = _hit()
    monkeypatch.setattr(main, "hybrid_search", lambda q, k, *, mode: ([hit, hit], "hybrid"))
    monkeypatch.setattr(main, "rerank", lambda q, hits: list(reversed(hits)))

    _hits, arm_used, _degraded = main._default_retrieve("q", 5, "hybrid_rerank")

    assert arm_used == "hybrid_rerank"
    spans = [s for s in exporter.get_finished_spans() if s.name == "rerank"]
    assert len(spans) == 1
    assert dict(spans[0].attributes or {}) == {"candidates": 2, "applied": True}
    assert spans[0].end_time is not None and spans[0].start_time is not None
    assert spans[0].end_time >= spans[0].start_time


def test_default_retrieve_keeps_hybrid_order_when_rerank_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hit = _hit()
    monkeypatch.setattr(main, "hybrid_search", lambda q, k, *, mode: ([hit], "hybrid"))
    monkeypatch.setattr(main, "rerank", lambda q, hits: None)

    _hits, arm_used, degraded = main._default_retrieve("q", 5, "hybrid_rerank")

    assert arm_used == "hybrid"
    assert degraded is False  # rerank unavailability is never a degradation


class _FakeCursor:
    """Scripted cursor for exercising `main._connect()` production helpers."""

    def __init__(
        self,
        *,
        fetchone_results: list[Any] | None = None,
        fetchall_results: list[Any] | None = None,
        fail_execute: bool = False,
    ) -> None:
        self._fetchone_results = list(fetchone_results or [])
        self._fetchall_results = list(fetchall_results or [])
        self.fail_execute = fail_execute
        self.queries: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> None:
        if self.fail_execute:
            raise psycopg.OperationalError("simulated write failure")
        self.queries.append((query, params))

    def fetchone(self) -> Any:
        return self._fetchone_results.pop(0) if self._fetchone_results else None

    def fetchall(self) -> list[Any]:
        result = self._fetchall_results.pop(0) if self._fetchall_results else []
        return result if isinstance(result, list) else [result]

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _patch_connect(monkeypatch: pytest.MonkeyPatch, cursor: _FakeCursor) -> _FakeCursor:
    monkeypatch.setattr(main, "_connect", lambda: _FakeConnection(cursor))
    return cursor


def test_infer_provider_returns_hostname_for_unknown_provider() -> None:
    assert main._infer_provider("https://api.example.com/v1") == "api.example.com"


@pytest.mark.parametrize(
    ("arm", "expected_mode"),
    [("lexical", "lexical"), ("vector", "vector")],
)
def test_default_retrieve_single_arms(
    monkeypatch: pytest.MonkeyPatch, arm: str, expected_mode: str
) -> None:
    hit = _hit()
    monkeypatch.setattr(main, "hybrid_search", lambda q, k, *, mode: ([hit], expected_mode))

    hits, arm_used, degraded = main._default_retrieve("q", 5, arm)

    assert hits == [hit]
    assert arm_used == expected_mode
    assert degraded is False


def test_default_retrieve_marks_degraded_when_search_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hit = _hit()
    monkeypatch.setattr(main, "hybrid_search", lambda q, k, *, mode: ([hit], "lexical"))

    _hits, arm_used, degraded = main._default_retrieve("q", 5, "hybrid")

    assert arm_used == "lexical"
    assert degraded is True


@respx.mock
def test_default_llm_reachable_true_when_models_endpoint_responds() -> None:
    main._reset_llm_reachable_cache_for_tests()
    respx.get("http://localhost:11434/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    assert main._default_llm_reachable("http://localhost:11434/v1") is True


def test_default_llm_reachable_false_on_connection_error() -> None:
    main._reset_llm_reachable_cache_for_tests()
    assert main._default_llm_reachable("http://127.0.0.1:1") is False


@respx.mock
def test_default_llm_reachable_caches_probe_so_health_stays_cheap() -> None:
    """Regression: uncached Groq `/models` probes made solo `/health` 1.2-1.9s
    and timed out during Ask; a short TTL cache keeps liveness under 2s."""
    main._reset_llm_reachable_cache_for_tests()
    route = respx.get("http://llm.test/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    assert main._default_llm_reachable("http://llm.test/v1") is True
    assert main._default_llm_reachable("http://llm.test/v1") is True
    assert route.call_count == 1


def test_health_returns_while_ask_llm_is_still_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/health` must not wait for an in-flight Ask's LLM call — that was the
    compose hang (UI spinner + curling /health both timing out)."""
    from homelib_rag.answer import AskResponse, TokenUsage

    from apps.inprocess_bridge import SyncASGITransport

    release = threading.Event()
    entered = threading.Event()

    def _blocking_answer(
        query: str,
        hits: Any,
        *,
        client: Any = None,
        arm_used: str = "hybrid",
    ) -> AskResponse:
        del query, hits, client
        entered.set()
        release.wait(timeout=5.0)
        return AskResponse(
            request_id="blocked-ask",
            answer="ok",
            citations=[],
            arm_used=arm_used,
            degraded=False,
            latency_ms=0,
            tokens=TokenUsage(prompt=1, completion=1),
        )

    monkeypatch.setattr(answer_module, "answer", _blocking_answer)
    monkeypatch.setattr(main.shelf_meta_module, "is_shelf_meta_intent", lambda query: False)
    deps = _make_deps(
        retrieve=lambda q, k, arm: ([_hit()], arm, False),
        llm_reachable=lambda: True,
    )
    app.dependency_overrides[get_deps] = lambda: deps
    transport = SyncASGITransport(app)
    ask_http = httpx.Client(transport=transport, base_url="http://test")
    health_http = httpx.Client(transport=transport, base_url="http://test")
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            ask_future = pool.submit(
                lambda: ask_http.post("/v1/ask", json={"query": "Who wrote Walden?"})
            )
            assert entered.wait(timeout=2.0)
            t0 = time.monotonic()
            health = health_http.get("/health", timeout=2.0)
            health_s = time.monotonic() - t0
            release.set()
            ask = ask_future.result(timeout=5)
    finally:
        ask_http.close()
        health_http.close()
        app.dependency_overrides.pop(get_deps, None)

    assert health.status_code == 200
    assert health_s < 2.0
    assert ask.status_code == 200


def test_default_db_reachable_true_when_select_one_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_connect(monkeypatch, _FakeCursor(fetchone_results=[(1,)]))

    assert main._default_db_reachable() is True


def test_default_db_reachable_false_when_connect_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail() -> _FakeConnection:
        raise psycopg.OperationalError("db down")

    monkeypatch.setattr(main, "_connect", _fail)

    assert main._default_db_reachable() is False


def test_default_counts_returns_table_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connect(monkeypatch, _FakeCursor(fetchone_results=[(3,), (42,)]))

    assert main._default_counts() == (3, 42)


def test_default_counts_returns_zero_when_db_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail() -> _FakeConnection:
        raise psycopg.OperationalError("db down")

    monkeypatch.setattr(main, "_connect", _fail)

    assert main._default_counts() == (0, 0)


def test_default_list_books_maps_rows_to_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        ("bk1", "Title One", ["Author A"], 2, 5, "txt"),
        ("bk2", "Title Two", ["Author B"], 0, 0, ""),
    ]
    _patch_connect(monkeypatch, _FakeCursor(fetchall_results=[rows]))

    summaries = main._default_list_books()

    assert summaries == [
        BookSummary(
            book_id="bk1", title="Title One", authors=["Author A"], blocks=2, chunks=5, format="txt"
        ),
        BookSummary(
            book_id="bk2", title="Title Two", authors=["Author B"], blocks=0, chunks=0, format=""
        ),
    ]


def test_default_log_query_inserts_monitoring_row(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = _patch_connect(monkeypatch, _FakeCursor())
    row = QueryLogRow(
        request_id="req-1",
        latency_ms=12,
        arm="hybrid",
        k=5,
        rerank=True,
        rewrite=False,
        model="fake-model",
        tokens_prompt=10,
        tokens_completion=5,
        query_sha256_prefix="abc123",
        degraded=False,
    )

    main._default_log_query(row)

    assert len(cursor.queries) == 1
    query, params = cursor.queries[0]
    assert "INSERT INTO query_log" in query
    assert params[0] == "req-1"


def test_default_log_query_swallows_db_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connect(monkeypatch, _FakeCursor(fail_execute=True))
    row = QueryLogRow(
        request_id="req-2",
        latency_ms=1,
        arm="lexical",
        k=3,
        rerank=False,
        rewrite=False,
        model="fake-model",
        tokens_prompt=0,
        tokens_completion=0,
        query_sha256_prefix="deadbeef",
        degraded=True,
    )

    main._default_log_query(row)


def test_default_record_feedback_returns_true_when_row_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_connect(monkeypatch, _FakeCursor(fetchone_results=[("req-1",)]))

    assert main._default_record_feedback("req-1", "up", "nice") is True


def test_default_record_feedback_returns_false_for_unknown_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_connect(monkeypatch, _FakeCursor(fetchone_results=[None]))

    assert main._default_record_feedback("missing", "down", None) is False


def test_get_deps_returns_same_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    main._deps_singleton = None
    built = _base_deps()
    monkeypatch.setattr(main, "_build_default_deps", lambda: built)
    try:
        assert main.get_deps() is main.get_deps()
    finally:
        main._deps_singleton = None


def test_post_ingest_reraises_http_exception_unchanged() -> None:
    def _raise(req: Any) -> IngestResponse:
        raise HTTPException(status_code=418, detail="teapot")

    deps = _make_deps(ingest=_raise)
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.post("/v1/ingest", json={"path": "x.txt"})

    assert resp.status_code == 418
    assert resp.json()["detail"] == "teapot"


def test_health_is_degraded_when_store_has_zero_books() -> None:
    """SQLite creates the file on first connect, so a never-seeded clone has a
    reachable, migrated, empty store. That must read as degraded (still HTTP
    200 — the compose healthcheck is liveness, seeded-ness is this field)."""
    deps = _make_deps(db_reachable=lambda: True, llm_reachable=lambda: True, counts=lambda: (0, 0))
    app.dependency_overrides[get_deps] = lambda: deps

    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"] is True
    assert body["books"] == 0
