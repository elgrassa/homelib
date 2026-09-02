"""Behavioural tests for mentor intake — specs/api.md, product §5.5."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import homelib_rag.agent as agent_module
import pytest
from homelib_core.models import CatalogEntry
from homelib_rag.agent import run_agent
from homelib_rag.answer import ChatMessage, LLMResponse, LLMUsage
from homelib_rag.mentor import (
    MentorIntakeResponse,
    build_path,
    detect_high_stakes_notice,
    mentor_intake,
)
from homelib_rag.models import Hit
from homelib_rag.roadmap import RoadmapParseError, RoadmapStep


class _ScriptedClient:
    model = "fake-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)

    def chat(
        self,
        messages: Any,
        *,
        tools: Any = None,
        response_format: Any = None,
        max_tokens: int = 400,
    ) -> LLMResponse:
        _ = (messages, tools, response_format, max_tokens)
        return self._responses.pop(0)


def _hit(text: str = "Virtue is the only good.", chunk_id: str = "c1") -> Hit:
    return Hit(
        chunk_id=chunk_id,
        book_id="b1",
        score=1.0,
        rank=1,
        text=text,
        section_path=["Book I"],
        page=3,
        block_ids=["blk1"],
    )


def _catalog_entry(ol_key: str = "/works/OL1W") -> CatalogEntry:
    return CatalogEntry(
        ol_key=ol_key,
        title="Meditations",
        authors=["Marcus Aurelius"],
        subjects=["philosophy"],
        first_publish_year=1800,
        description=None,
        provenance_note="fixture",
    )


def _intake_json(**overrides: Any) -> LLMResponse:
    payload = {
        "proposed_area": {"name": "Stoicism", "copy": "Calm practice"},
        "proposed_wing": {"name": "Ethics shelf", "area_name": "Stoicism", "copy": None},
        "proposed_path": {
            "title": "Start with Stoicism",
            "kind": "reading",
            "steps": [
                {
                    "order": 0,
                    "title": "Meditations",
                    "why": "Foundation",
                    "est_effort": "light",
                }
            ],
        },
        "rationale": "Grounded in shelf evidence.",
        "citations": [{"passage": 1, "quote": "Virtue is the only good."}],
    }
    payload.update(overrides)
    return LLMResponse(
        content=json.dumps(payload),
        usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
    )


def test_tool_dispatch_scripted_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Port v1: scripted fake LLM dispatches real tool functions in order."""
    calls: list[str] = []

    def _fake_search_shelf(query: str, k: int = 5) -> list[Hit]:
        calls.append(f"shelf:{query}:{k}")
        return [_hit()]

    def _fake_search_catalog(query: str, subjects: list[str] | None = None) -> list[CatalogEntry]:
        calls.append(f"catalog:{query}")
        return [_catalog_entry()]

    monkeypatch.setitem(agent_module._TOOL_FUNCTIONS, "search_shelf", _fake_search_shelf)
    monkeypatch.setitem(agent_module._TOOL_FUNCTIONS, "search_catalog", _fake_search_catalog)

    tool_call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "search_shelf", "arguments": '{"query": "stoicism", "k": 2}'},
    }
    client = _ScriptedClient(
        [
            LLMResponse(
                content="",
                tool_calls=[tool_call],
                usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
            ),
            LLMResponse(content="done", usage=LLMUsage(prompt_tokens=1, completion_tokens=1)),
        ]
    )
    result = run_agent([ChatMessage(role="user", content="help")], client=client)
    assert calls == ["shelf:stoicism:2"]
    assert result.final_message == "done"


def test_intake_never_creates_active_state(tmp_path: Path) -> None:
    from apps.store.sqlite import connect, migrate, row_counts, seed
    from apps.store.tests.test_sqlite import REPO_ROOT, _fresh

    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    before = {key: row_counts(conn)[key] for key in ("areas", "wings", "playlist", "playlist_item")}

    client = _ScriptedClient([_intake_json()])
    try:
        mentor_intake(
            "learn stoicism",
            ["philosophy"],
            "beginner",
            client=client,
            catalog=lambda _goal, _subjects: [_catalog_entry()],
            shelf_search=lambda _query, _k: [_hit()],
        )
        after = {
            key: row_counts(conn)[key] for key in ("areas", "wings", "playlist", "playlist_item")
        }
        assert after == before
    finally:
        conn.close()


def test_path_schema_fail_closed() -> None:
    with pytest.raises(RoadmapParseError, match="not among retrieved candidates"):
        build_path(
            "Bad path",
            "reading",
            [
                RoadmapStep(
                    order=0,
                    ol_key="/works/INVENTED",
                    book_id=None,
                    title="Ghost book",
                    authors=["Nobody"],
                    why="n/a",
                    prerequisites=[],
                    est_effort="light",
                )
            ],
            catalog=lambda _goal, _subjects: [_catalog_entry("/works/OL1W")],
            interests=["philosophy"],
            goal="learn",
        )


def test_citations_resolve() -> None:
    client = _ScriptedClient([_intake_json()])
    response = mentor_intake(
        "learn stoicism",
        ["philosophy"],
        "beginner",
        client=client,
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
    )
    assert isinstance(response, MentorIntakeResponse)
    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == "c1"
    assert response.citations[0].quote in _hit().text


def test_high_stakes_note() -> None:
    notice = detect_high_stakes_notice("Should I take this medication?", [])
    assert notice is not None
    client = _ScriptedClient([_intake_json()])
    response = mentor_intake(
        "medical diagnosis for chest pain",
        ["health"],
        None,
        client=client,
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
    )
    assert response.high_stakes_notice is not None
    assert "informational" in response.high_stakes_notice.lower()


def test_abstention_on_no_evidence() -> None:
    client = _ScriptedClient([])
    response = mentor_intake(
        "obscure niche topic",
        [],
        None,
        client=client,
        catalog=lambda _goal, _subjects: [],
        shelf_search=lambda _query, _k: [],
    )
    assert response.degraded is True
    assert response.citations == []
    assert response.proposed_path is None
    assert "enough indexed sources" in response.rationale.lower()
