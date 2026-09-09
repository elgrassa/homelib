"""Behavioural tests for `homelib_rag.roadmap` — see specs/roadmap.md.

No live Postgres, no live LLM: `catalog` is a plain in-memory callable
fixture and every LLM call goes through a scripted fake `OpenAICompatibleClient`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from homelib_core.models import CatalogEntry
from homelib_rag.answer import LLMResponse, LLMUnreachableError, LLMUsage
from homelib_rag.roadmap import (
    RoadmapParseError,
    RoadmapResponse,
    _parse_and_validate,
    _repair_prompt,
    build_roadmap,
)


class _ScriptedClient:
    model = "fake-model"

    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: Any,
        *,
        tools: Any = None,
        response_format: Any = None,
        max_tokens: int = 400,
    ) -> LLMResponse:
        self.calls.append({"messages": list(messages), "max_tokens": max_tokens})
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _entry(ol_key: str, title: str = "Some Book", authors: list[str] | None = None) -> CatalogEntry:
    return CatalogEntry(
        ol_key=ol_key,
        title=title,
        authors=authors or ["An Author"],
        subjects=["economics"],
        first_publish_year=1920,
        description="Some optional background.",
        provenance_note="test fixture",
    )


def _catalog_returning(entries: list[CatalogEntry]) -> Any:
    def _search(query: str, subjects: list[str] | None = None) -> list[CatalogEntry]:
        return entries

    return _search


def _step(order: int, ol_key: str | None) -> dict[str, Any]:
    return {
        "order": order,
        "ol_key": ol_key,
        "book_id": None,
        "title": "Some Book",
        "authors": ["An Author"],
        "why": "It fits your interests.",
        "prerequisites": [],
        "est_effort": "light",
    }


def _llm_response(steps: list[dict[str, Any]], rationale: str = "A plan.") -> LLMResponse:
    return LLMResponse(
        content=json.dumps({"steps": steps, "rationale": rationale}),
        usage=LLMUsage(prompt_tokens=10, completion_tokens=10),
    )


# ── Named red tests ─────────────────────────────────────────────────────────


def test_roadmap_schema_fail_closed() -> None:
    """Invalid JSON on both the first call and the repair call raises
    `RoadmapParseError`; no `RoadmapResponse` is ever returned."""
    client = _ScriptedClient(
        [
            LLMResponse(content="not json", usage=LLMUsage(prompt_tokens=1, completion_tokens=1)),
            LLMResponse(
                content="still not json", usage=LLMUsage(prompt_tokens=1, completion_tokens=1)
            ),
        ]
    )
    catalog = _catalog_returning([_entry("/works/OL1W")])

    with pytest.raises(RoadmapParseError):
        build_roadmap(["economics"], "beginner", "learn basics", client=client, catalog=catalog)


def test_roadmap_requests_a_larger_completion_cap() -> None:
    """The client's 400-token default is sized for answers; a multi-step
    roadmap's JSON does not fit in it, and a truncated body fails parsing
    every time. Both roadmap calls must pass an explicit larger cap."""
    client = _ScriptedClient(
        [
            LLMResponse(content="not json", usage=LLMUsage(prompt_tokens=1, completion_tokens=1)),
            LLMResponse(
                content="still not json", usage=LLMUsage(prompt_tokens=1, completion_tokens=1)
            ),
        ]
    )
    catalog = _catalog_returning([_entry("/works/OL1W")])

    with pytest.raises(RoadmapParseError):
        build_roadmap(["economics"], "beginner", "learn basics", client=client, catalog=catalog)

    assert [call["max_tokens"] for call in client.calls] == [1600, 1600]


def test_roadmap_schema_repairs_on_second_attempt() -> None:
    """First call malformed, repair call valid: a valid `RoadmapResponse` is
    returned, and the repair prompt sent on the second call contains the
    validation error text from the first."""
    client = _ScriptedClient(
        [
            LLMResponse(
                content="{not valid json", usage=LLMUsage(prompt_tokens=1, completion_tokens=1)
            ),
            _llm_response([_step(0, "/works/OL1W")]),
        ]
    )
    catalog = _catalog_returning([_entry("/works/OL1W")])

    result = build_roadmap(
        ["economics"], "beginner", "learn basics", client=client, catalog=catalog
    )

    assert isinstance(result, RoadmapResponse)
    assert len(result.steps) == 1
    repair_message_content = client.calls[1]["messages"][-1].content
    assert "invalid JSON" in repair_message_content or "JSON" in repair_message_content


def test_roadmap_steps_reference_only_retrieved_candidates() -> None:
    """No returned step's `ol_key` falls outside the retrieved candidates."""
    client = _ScriptedClient([_llm_response([_step(0, "/works/OL1W"), _step(1, None)])])
    catalog = _catalog_returning([_entry("/works/OL1W")])

    result = build_roadmap(
        ["economics"], "beginner", "learn basics", client=client, catalog=catalog
    )

    valid_keys = {"/works/OL1W", None}
    assert all(step.ol_key in valid_keys for step in result.steps)


def test_roadmap_rejects_invented_ol_key() -> None:
    """A step referencing an ol_key absent from `candidates` triggers the
    repair-then-hard-error path — never silently accepted."""
    invented_step = _step(0, "/works/OL_INVENTED")
    client = _ScriptedClient(
        [
            _llm_response([invented_step]),
            _llm_response([invented_step]),  # repair attempt also invents it
        ]
    )
    catalog = _catalog_returning([_entry("/works/OL1W")])

    with pytest.raises(RoadmapParseError):
        build_roadmap(["economics"], "beginner", "learn basics", client=client, catalog=catalog)


def test_roadmap_max_steps_bounded() -> None:
    """A fake LLM proposes more steps than `max_steps`; `len(result.steps) <=
    max_steps`, truncated deterministically by `order`."""
    steps = [_step(i, None) for i in range(10)]
    client = _ScriptedClient([_llm_response(steps)])
    catalog = _catalog_returning([])

    result = build_roadmap(
        ["economics"], "beginner", "learn basics", 3, client=client, catalog=catalog
    )

    assert len(result.steps) <= 3
    assert [s.order for s in result.steps] == [0, 1, 2]


# ── Connectivity bypasses the repair loop ───────────────────────────────────


def test_llm_unreachable_propagates_without_consuming_repair_budget() -> None:
    client = _ScriptedClient([LLMUnreachableError("connection refused")])
    catalog = _catalog_returning([_entry("/works/OL1W")])

    with pytest.raises(LLMUnreachableError):
        build_roadmap(["economics"], "beginner", "learn basics", client=client, catalog=catalog)

    assert len(client.calls) == 1  # never made a second (repair) call


def test_llm_unreachable_on_repair_call_also_propagates() -> None:
    client = _ScriptedClient(
        [
            LLMResponse(content="not json", usage=LLMUsage(prompt_tokens=1, completion_tokens=1)),
            LLMUnreachableError("connection dropped mid-repair"),
        ]
    )
    catalog = _catalog_returning([_entry("/works/OL1W")])

    with pytest.raises(LLMUnreachableError):
        build_roadmap(["economics"], "beginner", "learn basics", client=client, catalog=catalog)


# ── _parse_and_validate / _repair_prompt unit tests ─────────────────────────


def test_parse_and_validate_invalid_json_raises() -> None:
    with pytest.raises(RoadmapParseError):
        _parse_and_validate("not json", [])


def test_parse_and_validate_schema_violation_raises() -> None:
    with pytest.raises(RoadmapParseError):
        _parse_and_validate(json.dumps({"steps": "not a list", "rationale": "x"}), [])


def test_parse_and_validate_generates_request_id() -> None:
    raw = json.dumps({"steps": [_step(0, None)], "rationale": "ok"})
    result = _parse_and_validate(raw, [])
    assert result.request_id


def test_repair_prompt_contains_raw_and_error_text() -> None:
    prompt = _repair_prompt("{bad json", "Expecting value: line 1 column 1")
    assert "{bad json" in prompt
    assert "Expecting value" in prompt


def test_parse_and_validate_rewrites_shelf_ol_key_to_book_id() -> None:
    raw = json.dumps(
        {
            "steps": [
                {
                    "order": 0,
                    "ol_key": "shelf:aurelius-meditations",
                    "book_id": None,
                    "title": "Meditations",
                    "authors": ["Marcus Aurelius"],
                    "why": "Core Stoic text on the shelf",
                    "prerequisites": [],
                    "est_effort": "medium",
                }
            ],
            "rationale": "Start on the shelf",
        }
    )
    candidates = [
        CatalogEntry(
            ol_key="shelf:aurelius-meditations",
            title="Meditations",
            authors=["Marcus Aurelius"],
            subjects=["stoicism"],
            provenance_note="Full-text shelf",
        )
    ]
    result = _parse_and_validate(raw, candidates)
    assert result.steps[0].ol_key is None
    assert result.steps[0].book_id == "aurelius-meditations"


def test_catalog_search_called_with_goal_and_interests() -> None:
    captured: dict[str, Any] = {}

    def _search(query: str, subjects: list[str] | None = None) -> list[CatalogEntry]:
        captured["query"] = query
        captured["subjects"] = subjects
        return [_entry("/works/OL1W")]

    client = _ScriptedClient([_llm_response([_step(0, "/works/OL1W")])])
    build_roadmap(
        ["woodworking", "stoicism"],
        "intermediate",
        "become a better carpenter",
        client=client,
        catalog=_search,
    )

    assert captured["query"] == "become a better carpenter"
    assert captured["subjects"] == ["woodworking", "stoicism"]


def test_why_prompt_instructs_against_verbatim_description() -> None:
    """The system prompt explicitly tells the model not to copy
    `description` verbatim into `why` (specs/roadmap.md)."""
    client = _ScriptedClient([_llm_response([_step(0, "/works/OL1W")])])
    catalog = _catalog_returning([_entry("/works/OL1W")])

    build_roadmap(["economics"], "beginner", "learn basics", client=client, catalog=catalog)

    system_message = client.calls[0]["messages"][0].content
    assert "never copy it verbatim" in system_message
