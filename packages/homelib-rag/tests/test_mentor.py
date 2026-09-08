"""Behavioural tests for mentor intake — specs/api.md, product §5.5."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import homelib_rag.agent as agent_module
import pytest
from homelib_core.models import Block, CatalogEntry, Provenance
from homelib_rag.agent import run_agent
from homelib_rag.answer import ChatMessage, LLMResponse, LLMUnreachableError, LLMUsage
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


class _UnreachableClient:
    """A scripted client whose endpoint is down before any tool call."""

    model = "fake-model"

    def chat(
        self,
        messages: Any,
        *,
        tools: Any = None,
        response_format: Any = None,
        max_tokens: int = 400,
    ) -> LLMResponse:
        _ = (messages, tools, response_format, max_tokens)
        raise LLMUnreachableError("connection refused")


def _get_block_fixture(block_id: str) -> Block:
    return Block(
        block_id=block_id,
        book_id="b1",
        ordinal=0,
        section_path=[],
        text="fetched text",
        char_start=0,
        char_end=12,
        provenance=Provenance(format="txt", source_sha256=""),
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


def _tool_then_intake(*extra: LLMResponse) -> list[LLMResponse]:
    """Scripted agent: one tool round, then final intake JSON.

    Used by tests that specifically verify tool dispatch and reporting.
    """
    tool_call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "get_block", "arguments": '{"block_id": "blk1"}'},
    }
    return [
        LLMResponse(
            content="",
            tool_calls=[tool_call],
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        ),
        *extra,
    ]


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

    client = _ScriptedClient(_tool_then_intake(_intake_json()))
    try:
        mentor_intake(
            "learn stoicism",
            ["philosophy"],
            "beginner",
            client=client,
            catalog=lambda _goal, _subjects: [_catalog_entry()],
            shelf_search=lambda _query, _k: [_hit()],
            get_block=_get_block_fixture,
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
    client = _ScriptedClient(_tool_then_intake(_intake_json()))
    response = mentor_intake(
        "learn stoicism",
        ["philosophy"],
        "beginner",
        client=client,
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
        get_block=_get_block_fixture,
    )
    assert isinstance(response, MentorIntakeResponse)
    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == "c1"
    assert response.citations[0].quote in _hit().text


def test_high_stakes_note() -> None:
    notice = detect_high_stakes_notice("Should I take this medication?", [])
    assert notice is not None
    # Off-topic shelf/catalog for a medical goal → early abstention; notice
    # is still attached. Scripted path is unused.
    client = _ScriptedClient(_tool_then_intake(_intake_json()))
    response = mentor_intake(
        "medical diagnosis for chest pain",
        ["health"],
        None,
        client=client,
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
        get_block=_get_block_fixture,
    )
    assert response.high_stakes_notice is not None
    assert "informational" in response.high_stakes_notice.lower()


def test_mentor_response_reports_tool_calls() -> None:
    """A scripted fake LLM calls `get_block` once before its final proposal
    (`run_agent`'s loop, wired in on the Mentor path since 2026-09-06); the
    response surfaces the tool name and the number of rounds it took."""
    client = _ScriptedClient(_tool_then_intake(_intake_json()))

    response = mentor_intake(
        "learn stoicism",
        ["philosophy"],
        "beginner",
        client=client,
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
        get_block=_get_block_fixture,
    )

    assert response.tool_calls == ["get_block"]
    assert response.rounds_used == 2
    assert response.degraded is False


def test_mentor_accepts_grounded_in_context_path_without_optional_tool_call() -> None:
    """LIVE: retrieved evidence is already in the prompt; a direct final answer is valid."""
    client = _ScriptedClient([_intake_json()])

    response = mentor_intake(
        "learn stoicism",
        ["philosophy"],
        "beginner",
        client=client,
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
        get_block=_get_block_fixture,
    )

    assert response.degraded is False
    assert response.proposed_path is not None
    assert response.proposed_path.title == "Start with Stoicism"
    assert response.tool_calls == []
    assert response.rounds_used == 1


def test_mentor_intake_degrades_when_llm_down() -> None:
    """The LLM endpoint is unreachable before `run_agent` gets to invoke a
    tool: the response is still returned degraded, exactly as it was before
    the intake ran through the agent loop, with no tool activity to report."""
    response = mentor_intake(
        "learn stoicism",
        ["philosophy"],
        "beginner",
        client=_UnreachableClient(),
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
        get_block=_get_block_fixture,
    )

    assert response.degraded is True
    assert response.tool_calls == []
    assert response.rounds_used == 0
    assert response.rationale == "The mentor service is temporarily unavailable."


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


def test_mentor_miss_m1_modern_swe_job_is_out_of_corpus() -> None:
    """Golden #M1 — modern SWE / AI-engineer job loop is not in the 18
    Gutenberg books. Empty shelf+catalog must abstain with no invented path."""
    client = _ScriptedClient([_intake_json()])  # would invent a path if called
    response = mentor_intake(
        "Land AI engineer job",
        ["software interviews", "leetcode"],
        "intermediate",
        client=client,
        catalog=lambda _goal, _subjects: [],
        shelf_search=lambda _query, _k: [],
    )
    assert response.degraded is True
    assert response.proposed_path is None
    assert response.proposed_area is None
    assert response.citations == []
    assert "enough indexed sources" in response.rationale.lower()
    assert client._responses  # LLM never consumed — early abstention


def test_mentor_miss_m1_abstains_on_off_topic_industrial_shelf_hits() -> None:
    """LIVE #M1 honesty failure: off-topic industrial/historical shelf hits
    must not yield an invented modern SWE / labour-market path.

    Provenance: ``ford-my-life-and-work`` chunk text in ``data/homelib.sqlite``
    (Project Gutenberg Ford — farm tractor / ploughing / threshing). The live
    miss returned an agricultural-tractors path with ``tool_calls=[]``,
    ``rounds_used=1``.
    """
    tractor_hit = _hit(
        text=(
            "It occurred to me, as I remember somewhat vaguely, that precisely "
            "the same idea might be applied as a tractor to attend to the "
            "excessively hard labour of ploughing. They were sometimes used as "
            "tractors to pull heavy loads and, if the owner also happened to be "
            "in the threshing-machine business, he hitched his threshing machine "
            "to them."
        ),
        chunk_id="ford-tractor-m1-fixture",
    )
    invented_off_topic = _intake_json(
        proposed_area={"name": "Agricultural Machinery", "copy": "Farm engines"},
        proposed_wing={
            "name": "Threshing shelf",
            "area_name": "Agricultural Machinery",
            "copy": None,
        },
        proposed_path={
            "title": "Path into agricultural tractors",
            "kind": "learning",
            "steps": [
                {
                    "order": 0,
                    "title": "Study farm tractors and ploughing",
                    "why": "Ford describes tractors for threshing-machine work",
                    "est_effort": "medium",
                }
            ],
        },
        rationale="Grounded in Ford tractor passages.",
        citations=[
            {
                "passage": 1,
                "quote": "tractor to attend to the excessively hard labour of ploughing",
            }
        ],
    )
    client = _ScriptedClient([invented_off_topic])
    response = mentor_intake(
        "Land AI engineer job",
        ["software interviews", "leetcode"],
        "intermediate",
        client=client,
        catalog=lambda _goal, _subjects: [],
        shelf_search=lambda _query, _k: [tractor_hit],
    )
    assert response.degraded is True
    assert response.proposed_path is None
    assert response.proposed_area is None
    assert response.proposed_wing is None
    assert response.citations == []
    assert "enough indexed sources" in response.rationale.lower()
    assert client._responses  # early abstention — invented path never accepted


def test_mentor_stops_at_two_rounds_and_abstains_on_empty_json() -> None:
    """Bound: max_rounds=2. Empty/unparseable final JSON must not invent a path."""
    empty = LLMResponse(content="", usage=LLMUsage(prompt_tokens=1, completion_tokens=1))
    client = _ScriptedClient([empty])
    response = mentor_intake(
        "learn stoicism",
        ["philosophy"],
        "beginner",
        client=client,
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
        get_block=_get_block_fixture,
    )
    assert response.degraded is True
    assert response.proposed_path is None
    assert response.rounds_used == 1
    assert "enough indexed sources" in response.rationale.lower()


def test_mentor_unknown_tool_twice_stops_within_two_rounds() -> None:
    """A repeated unknown tool must stop the loop and abstain — no career path."""
    bad = {
        "id": "c1",
        "type": "function",
        "function": {"name": "invent_career", "arguments": "{}"},
    }
    client = _ScriptedClient(
        [
            LLMResponse(
                content="",
                tool_calls=[bad],
                usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
            ),
            LLMResponse(
                content="",
                tool_calls=[bad],
                usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
            ),
            _intake_json(),  # must never be reached if bound holds
        ]
    )
    response = mentor_intake(
        "learn stoicism",
        ["philosophy"],
        "beginner",
        client=client,
        catalog=lambda _goal, _subjects: [_catalog_entry()],
        shelf_search=lambda _query, _k: [_hit()],
        get_block=_get_block_fixture,
    )
    assert response.degraded is True
    assert response.proposed_path is None
    assert response.rounds_used <= 2
    assert "enough indexed sources" in response.rationale.lower()
    assert len(client._responses) == 1  # third scripted reply unused
