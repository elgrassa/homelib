"""Behavioural tests for `homelib_rag.agent` — see specs/agent-tools.md.

No live Postgres, no live LLM: DB-touching tools (`search_catalog`,
`get_block`) are monkeypatched at their `_connect` seam or invoked through
`run_agent` with the tool functions themselves monkeypatched; every LLM call
goes through a scripted fake `OpenAICompatibleClient`.
"""

from __future__ import annotations

from typing import Any

import homelib_rag.agent as agent_module
import pytest
from homelib_core.models import Block, CatalogEntry, Provenance
from homelib_rag.agent import (
    TOOL_SCHEMAS,
    AgentResult,
    ToolCallRecord,
    build_roadmap,
    get_block,
    get_book_block,
    run_agent,
    search_catalog,
    search_shelf,
)
from homelib_rag.answer import ChatMessage, LLMResponse, LLMUsage
from homelib_rag.models import Hit


class _ScriptedClient:
    model = "fake-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def chat(
        self,
        messages: Any,
        *,
        tools: Any = None,
        response_format: Any = None,
        max_tokens: int = 400,
    ) -> LLMResponse:
        self.calls += 1
        return self._responses.pop(0)


def _tool_call(name: str, arguments: str, call_id: str = "call_1") -> dict[str, Any]:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def _final_message(text: str) -> LLMResponse:
    usage = LLMUsage(prompt_tokens=1, completion_tokens=1)
    return LLMResponse(content=text, tool_calls=None, usage=usage)


def _tool_call_response(*calls: dict[str, Any]) -> LLMResponse:
    usage = LLMUsage(prompt_tokens=1, completion_tokens=1)
    return LLMResponse(content="", tool_calls=list(calls), usage=usage)


# ── Named red tests ─────────────────────────────────────────────────────────


def test_agent_dispatches_tools_with_scripted_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scripted fake LLM issues search_shelf then search_catalog then a
    final answer; each real Python tool function is invoked with the parsed
    arguments and its result fed back as a tool-role message."""
    calls_made: list[tuple[str, dict[str, Any]]] = []

    def _fake_search_shelf(query: str, k: int = 5) -> list[Hit]:
        calls_made.append(("search_shelf", {"query": query, "k": k}))
        hit = Hit(
            chunk_id="c1", book_id="b1", score=1.0, rank=1, text="t", section_path=[], page=None
        )
        return [hit]

    def _fake_search_catalog(query: str, subjects: list[str] | None = None) -> list[CatalogEntry]:
        calls_made.append(("search_catalog", {"query": query, "subjects": subjects}))
        return [
            CatalogEntry(
                ol_key="/works/OL1W",
                title="T",
                authors=["A"],
                subjects=[],
                first_publish_year=None,
                description=None,
                provenance_note="",
            )
        ]

    monkeypatch.setitem(agent_module._TOOL_FUNCTIONS, "search_shelf", _fake_search_shelf)
    monkeypatch.setitem(agent_module._TOOL_FUNCTIONS, "search_catalog", _fake_search_catalog)

    client = _ScriptedClient(
        [
            _tool_call_response(_tool_call("search_shelf", '{"query": "stoicism", "k": 3}')),
            _tool_call_response(_tool_call("search_catalog", '{"query": "stoicism"}')),
            _final_message("Here is what I found."),
        ]
    )

    result = run_agent([ChatMessage(role="user", content="tell me about stoicism")], client=client)

    assert isinstance(result, AgentResult)
    assert result.degraded is False
    assert result.final_message == "Here is what I found."
    assert calls_made[0] == ("search_shelf", {"query": "stoicism", "k": 3})
    assert calls_made[1] == ("search_catalog", {"query": "stoicism", "subjects": None})
    assert [tc.tool_name for tc in result.tool_calls] == ["search_shelf", "search_catalog"]
    assert all(tc.error is None for tc in result.tool_calls)


def test_max_rounds_terminates_degraded() -> None:
    """A fake LLM that always requests another tool call stops at exactly
    `max_rounds`, `degraded is True`, and no unbounded loop occurs."""
    responses = [
        _tool_call_response(_tool_call("get_block", '{"block_id": "x"}', call_id=f"call_{i}"))
        for i in range(10)
    ]
    client = _ScriptedClient(responses)

    result = run_agent(
        [ChatMessage(role="user", content="loop forever")], max_rounds=3, client=client
    )

    assert result.rounds_used == 3
    assert result.degraded is True
    assert client.calls == 3


def test_max_rounds_preserves_assistant_json_content() -> None:
    """When the loop exhausts rounds, keep the last assistant text for salvage."""
    proposal = (
        '{"proposed_path": {"title": "Stoic start", "kind": "reading",'
        ' "steps": []}, "rationale": "ok", "citations": []}'
    )
    responses = [
        LLMResponse(
            content=proposal if i == 1 else "",
            tool_calls=[_tool_call("get_block", '{"block_id": "x"}', call_id=f"c{i}")],
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )
        for i in range(2)
    ]
    client = _ScriptedClient(responses)
    result = run_agent(
        [ChatMessage(role="user", content="loop")],
        max_rounds=2,
        client=client,
        tools={"get_block": lambda block_id: None},
        tool_schemas=[s for s in TOOL_SCHEMAS if s["function"]["name"] == "get_block"],
    )
    assert result.degraded is True
    assert result.final_message == proposal


def test_unknown_tool_name_repaired_then_terminated() -> None:
    """A fake LLM requests a tool name absent from TOOL_SCHEMAS twice
    consecutively; the first attempt yields a corrective tool-role message
    and the second ends the loop with degraded=True without raising."""
    client = _ScriptedClient(
        [
            _tool_call_response(_tool_call("frobnicate", "{}", call_id="c1")),
            _tool_call_response(_tool_call("frobnicate", "{}", call_id="c2")),
        ]
    )

    result = run_agent([ChatMessage(role="user", content="do something")], client=client)

    assert result.degraded is True
    assert result.rounds_used == 2
    assert len(result.tool_calls) == 1  # only the first unknown attempt is recorded
    assert result.tool_calls[0].error == "unknown tool: frobnicate"


def test_tool_exception_is_caught_and_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """One tool is monkeypatched to raise; ToolCallRecord.error is set, the
    loop continues, and no exception propagates out of run_agent."""

    def _raise(**_kwargs: Any) -> Any:
        raise RuntimeError("boom")

    tool_functions = agent_module._TOOL_FUNCTIONS
    monkeypatch.setitem(tool_functions, "get_block", _raise)

    client = _ScriptedClient(
        [
            _tool_call_response(_tool_call("get_block", '{"block_id": "x"}')),
            _final_message("recovered"),
        ]
    )

    result = run_agent([ChatMessage(role="user", content="fetch a block")], client=client)

    assert result.degraded is False
    assert result.final_message == "recovered"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].error == "boom"


# ── Loop termination on a clean final message ───────────────────────────────


def test_run_agent_returns_immediately_on_no_tool_calls() -> None:
    client = _ScriptedClient([_final_message("hello")])

    result = run_agent([ChatMessage(role="user", content="hi")], client=client)

    assert result.final_message == "hello"
    assert result.rounds_used == 1
    assert result.tool_calls == []
    assert result.degraded is False


def test_malformed_tool_arguments_default_to_empty_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_get_block(**kwargs: Any) -> Block:
        captured.update(kwargs)
        return Block(
            block_id="b",
            book_id="bk",
            ordinal=0,
            section_path=[],
            text="t",
            char_start=0,
            char_end=1,
            provenance=Provenance(format="txt", source_sha256=""),
        )

    tool_functions = agent_module._TOOL_FUNCTIONS
    monkeypatch.setitem(tool_functions, "get_block", _fake_get_block)

    client = _ScriptedClient(
        [
            _tool_call_response(_tool_call("get_block", "not valid json")),
            _final_message("ok"),
        ]
    )

    result = run_agent([ChatMessage(role="user", content="x")], client=client)

    assert captured == {}
    assert result.tool_calls[0].arguments == {}
    assert result.tool_calls[0].error is None
    assert result.final_message == "ok"


# ── Tool implementations ────────────────────────────────────────────────────


def test_search_shelf_delegates_to_hybrid_search(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_hybrid_search(q: str, k: int, *, mode: str = "hybrid") -> tuple[list[Hit], str]:
        captured["q"] = q
        captured["k"] = k
        captured["mode"] = mode
        hit = Hit(
            chunk_id="c1", book_id="b1", score=1.0, rank=1, text="t", section_path=[], page=None
        )
        return ([hit], "hybrid")

    monkeypatch.setattr("homelib_rag.agent.hybrid_search", _fake_hybrid_search)

    hits = search_shelf("stoicism", k=7)

    assert captured == {"q": "stoicism", "k": 7, "mode": "hybrid"}
    assert hits[0].chunk_id == "c1"


def test_search_catalog_empty_query_raises() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        search_catalog("   ")


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows
        self.executed: list[tuple[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


def test_search_catalog_by_subjects(monkeypatch: pytest.MonkeyPatch) -> None:
    row = ("/works/OL1W", "Meditations", ["Marcus Aurelius"], ["philosophy"], 180, "desc", "note")
    cursor = _FakeCursor([row])
    monkeypatch.setattr("homelib_rag.agent._connect", lambda: _FakeConnection(cursor))

    results = search_catalog("stoicism", subjects=["philosophy"])

    assert len(results) == 1
    assert results[0].ol_key == "/works/OL1W"
    assert results[0].authors == ["Marcus Aurelius"]
    assert "subjects && %s::text[]" in cursor.executed[0][0]


def test_search_catalog_by_title_like(monkeypatch: pytest.MonkeyPatch) -> None:
    row = ("/works/OL2W", "Meditations", ["Marcus Aurelius"], [], None, None, "")
    cursor = _FakeCursor([row])
    monkeypatch.setattr("homelib_rag.agent._connect", lambda: _FakeConnection(cursor))

    results = search_catalog("meditations")

    assert len(results) == 1
    assert results[0].description is None
    assert results[0].provenance_note == ""


def test_get_block_found(monkeypatch: pytest.MonkeyPatch) -> None:
    row = ("blk1", "book1", 0, ["Ch1"], "Some text.", 0, 10, "txt", None, None, None)
    cursor = _FakeCursor([row])
    monkeypatch.setattr("homelib_rag.agent._connect", lambda: _FakeConnection(cursor))

    block = get_block("blk1")

    assert block.block_id == "blk1"
    assert block.book_id == "book1"
    assert block.provenance.format == "txt"
    assert block.provenance.source_sha256 == ""


def test_get_block_not_found_raises_keyerror(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = _FakeCursor([])
    monkeypatch.setattr("homelib_rag.agent._connect", lambda: _FakeConnection(cursor))

    with pytest.raises(KeyError):
        get_block("missing")


def test_get_book_block_maps_pg_row_and_passes_params(monkeypatch: pytest.MonkeyPatch) -> None:
    row = ("blk2", "book1", 1, ["Ch2"], "Page two text.", 10, 20, "epub", 5, 2, "anchor1")
    cursor = _FakeCursor([row])
    monkeypatch.setattr("homelib_rag.agent._connect", lambda: _FakeConnection(cursor))

    block = get_book_block("book1", 1)

    assert block.block_id == "blk2"
    assert block.book_id == "book1"
    assert block.ordinal == 1
    assert block.section_path == ["Ch2"]
    assert block.text == "Page two text."
    assert block.char_start == 10
    assert block.char_end == 20
    assert block.provenance.format == "epub"
    assert block.provenance.page == 5
    assert block.provenance.spine_index == 2
    assert block.provenance.anchor == "anchor1"
    assert block.provenance.source_sha256 == ""
    assert cursor.executed[0][1] == ("book1", 1)


def test_get_book_block_raises_keyerror_when_no_row(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = _FakeCursor([])
    monkeypatch.setattr("homelib_rag.agent._connect", lambda: _FakeConnection(cursor))

    with pytest.raises(KeyError):
        get_book_block("book1", 99)


def test_build_roadmap_tool_wraps_roadmap_module(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_roadmap_build_roadmap(
        interests: list[str], level: str, goal: str, *, client: Any, catalog: Any
    ) -> Any:
        captured["interests"] = interests
        captured["level"] = level
        captured["goal"] = goal
        return "fake-roadmap-response"

    monkeypatch.setattr("homelib_rag.agent._roadmap_build_roadmap", _fake_roadmap_build_roadmap)

    result = build_roadmap(["stoicism"], "beginner", "learn calm")

    assert result == "fake-roadmap-response"
    assert captured["interests"] == ["stoicism"]
    assert captured["level"] == "beginner"
    assert captured["goal"] == "learn calm"


def test_tool_schemas_shape() -> None:
    names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
    assert names == {"search_shelf", "search_catalog", "build_roadmap", "get_block"}
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


def test_run_agent_uses_injected_get_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """`run_agent(..., tools=...)` dispatches to the caller's own tool table
    instead of this module's Postgres-bound `_TOOL_FUNCTIONS` default — the
    store-safety seam `homelib_rag.mentor.mentor_intake` uses to wire
    `Deps.get_block` in on the Mentor path (specs/agent-tools.md)."""

    def _real_get_block_must_not_run(**_kwargs: Any) -> Block:
        raise AssertionError("the module-default get_block must not be called")

    monkeypatch.setitem(agent_module._TOOL_FUNCTIONS, "get_block", _real_get_block_must_not_run)

    injected_calls: list[str] = []

    def _injected_get_block(block_id: str) -> Block:
        injected_calls.append(block_id)
        return Block(
            block_id=block_id,
            book_id="bk",
            ordinal=0,
            section_path=[],
            text="t",
            char_start=0,
            char_end=1,
            provenance=Provenance(format="txt", source_sha256=""),
        )

    client = _ScriptedClient(
        [
            _tool_call_response(_tool_call("get_block", '{"block_id": "blk-1"}')),
            _final_message("fetched"),
        ]
    )

    result = run_agent(
        [ChatMessage(role="user", content="fetch a block")],
        client=client,
        tools={"get_block": _injected_get_block},
    )

    assert injected_calls == ["blk-1"]
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "get_block"
    assert result.tool_calls[0].arguments == {"block_id": "blk-1"}
    assert result.tool_calls[0].error is None
    assert result.final_message == "fetched"
    assert result.degraded is False


def test_tool_call_record_and_agent_result_roundtrip() -> None:
    record = ToolCallRecord(round=0, tool_name="x", arguments={}, result_summary="ok", error=None)
    result = AgentResult(final_message="done", tool_calls=[record], rounds_used=1, degraded=False)
    assert result.tool_calls[0].tool_name == "x"
