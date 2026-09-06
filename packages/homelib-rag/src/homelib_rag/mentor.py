"""Mentor intake and path artifacts — see specs/api.md §8, product §5.5.

Intake proposes Areas/Wings/paths and Coffee Table stacks; nothing is
persisted until the user accepts via the POST accept routes. High-stakes
topics get an informational notice; missing evidence yields abstention.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Callable
from typing import Any, Literal

from homelib_core.models import Block, CatalogEntry
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from homelib_rag.agent import TOOL_SCHEMAS as _AGENT_TOOL_SCHEMAS
from homelib_rag.agent import run_agent
from homelib_rag.answer import (
    ChatMessage,
    Citation,
    CitationValidationError,
    LLMUnreachableError,
    OpenAICompatibleClient,
    _validate_citations,
)
from homelib_rag.models import Hit
from homelib_rag.roadmap import CatalogSearch, Level, RoadmapParseError, RoadmapStep

# Mentor's own tool-calling surface (specs/agent-tools.md: "on the Mentor
# request path since 2026-09-06"): the same three retrieval tools `run_agent`
# already knows how to schema/dispatch, minus `build_roadmap` — the mentor
# proposes its own path rather than delegating to the roadmap tool.
_MENTOR_TOOL_NAMES = {"search_shelf", "search_catalog", "get_block"}
_MENTOR_TOOL_SCHEMAS = [
    schema for schema in _AGENT_TOOL_SCHEMAS if schema["function"]["name"] in _MENTOR_TOOL_NAMES
]

__all__ = [
    "CreatePathRequest",
    "MentorIntakeRequest",
    "MentorIntakeResponse",
    "PathResponse",
    "PathStepPreview",
    "ProposedArea",
    "ProposedPath",
    "ProposedWing",
    "build_path",
    "detect_high_stakes_notice",
    "mentor_intake",
]

logger = logging.getLogger(__name__)

_HIGH_STAKES_PATTERN = re.compile(
    r"\b(medical|health|diagnosis|treatment|legal|financial|investment|tax|"
    r"hire|hiring|therapy|prescription|medication)\b",
    re.IGNORECASE,
)

_ABSTENTION_RATIONALE = (
    "I do not have enough indexed sources to propose a grounded path for that "
    "goal yet. Try narrowing the topic or importing relevant books to My Shelf."
)


class MentorIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    interests: list[str] = Field(default_factory=list)
    level: Level | None = None


class ProposedArea(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    area_copy: str | None = Field(default=None, alias="copy")


class ProposedWing(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    area_name: str | None = None
    wing_copy: str | None = Field(default=None, alias="copy")


class PathStepPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int
    title: str
    why: str
    est_effort: Literal["light", "medium", "deep"] | None = None


class ProposedPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    kind: Literal["reading", "learning", "action"]
    steps: list[PathStepPreview]


class MentorIntakeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    proposed_area: ProposedArea | None = None
    proposed_wing: ProposedWing | None = None
    proposed_path: ProposedPath | None = None
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    degraded: bool = False
    high_stakes_notice: str | None = None
    #: Tool names in call order, from the `run_agent` loop this intake now
    #: drives (specs/agent-tools.md). Empty when the LLM never got to call a
    #: tool (abstention on no evidence, or the endpoint was unreachable) —
    #: defaulted so older clients parsing this response still validate.
    tool_calls: list[str] = Field(default_factory=list)
    rounds_used: int = 0


class CreatePathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intake_request_id: str | None = None
    title: str
    kind: Literal["reading", "learning", "action"]
    steps: list[RoadmapStep]


class PathResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_id: str
    title: str
    kind: Literal["reading", "learning", "action"]
    steps: list[RoadmapStep]
    accepted: Literal[True] = True


class _RawPassageCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passage: int = Field(ge=1)
    quote: str


class _LLMIntakeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_area: ProposedArea | None = None
    proposed_wing: ProposedWing | None = None
    proposed_path: ProposedPath | None = None
    rationale: str
    citations: list[_RawPassageCitation] = Field(default_factory=list)


_INTAKE_SYSTEM = (
    "You propose a library learning structure from retrieved shelf passages and "
    "catalog candidates only. Respond with ONLY JSON matching the requested "
    "shape. Every citation must reference a passage number from the context and "
    "quote it verbatim. If evidence is thin, say so in rationale and leave "
    "proposals minimal."
)


def detect_high_stakes_notice(goal: str, interests: list[str]) -> str | None:
    blob = " ".join([goal, *interests])
    if _HIGH_STAKES_PATTERN.search(blob):
        return (
            "HomeLib provides informational, source-cited guidance only — not "
            "medical, legal, financial, or other professional advice."
        )
    return None


def _passage_citations(raw: list[_RawPassageCitation], hits: list[Hit]) -> list[Citation]:
    citations: list[Citation] = []
    for item in raw:
        if item.passage < 1 or item.passage > len(hits):
            raise CitationValidationError(
                f"passage {item.passage} outside context ({len(hits)} passages)"
            )
        hit = hits[item.passage - 1]
        block_id = hit.block_ids[0] if hit.block_ids else hit.chunk_id
        citations.append(
            Citation(
                chunk_id=hit.chunk_id,
                block_id=block_id,
                book_id=hit.book_id,
                book_title=hit.book_id,
                section_path=list(hit.section_path),
                page=hit.page,
                quote=item.quote,
            )
        )
    _validate_citations(citations, hits)
    return citations


def _build_intake_prompt(
    goal: str,
    interests: list[str],
    level: Level | None,
    hits: list[Hit],
    candidates: list[CatalogEntry],
) -> str:
    lines = [
        f"Goal: {goal!r}",
        f"Interests: {interests!r}",
        f"Level: {level or 'unspecified'}",
        "",
        "Shelf passages:",
    ]
    if hits:
        for index, hit in enumerate(hits, start=1):
            lines.append(f"[{index}] {hit.text[:400]}")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("Catalog candidates:")
    if candidates:
        for index, entry in enumerate(candidates[:20], start=1):
            lines.append(f"[{index}] {entry.title!r} by {entry.authors!r} ({entry.ol_key})")
    else:
        lines.append("(none)")
    return "\n".join(lines)


def _mentor_tools(
    catalog: CatalogSearch,
    shelf_search: Callable[[str, int], list[Hit]] | None,
    get_block: Callable[[str], Block] | None,
) -> dict[str, Callable[..., Any]]:
    """Adapt the mentor's own retrieval callables to the keyword-argument
    shape `run_agent` calls tools with (`_MENTOR_TOOL_SCHEMAS`'s parameter
    names) — independent of whatever positional signature the caller's
    `catalog`/`shelf_search`/`get_block` happen to have (e.g. `Deps.get_block`,
    already store-safe: it dispatches on `HOMELIB_SQLITE_PATH` in
    `apps/api/main.py`, or a test fixture's `lambda _goal, _subjects: ...`)."""

    def _search_catalog_tool(query: str, subjects: list[str] | None = None) -> list[CatalogEntry]:
        return catalog(query, subjects)

    tools: dict[str, Callable[..., Any]] = {"search_catalog": _search_catalog_tool}

    if shelf_search is not None:

        def _search_shelf_tool(query: str, k: int = 5) -> list[Hit]:
            return shelf_search(query, k)

        tools["search_shelf"] = _search_shelf_tool

    if get_block is not None:

        def _get_block_tool(block_id: str) -> Block:
            return get_block(block_id)

        tools["get_block"] = _get_block_tool

    return tools


def mentor_intake(
    goal: str,
    interests: list[str],
    level: Level | None,
    *,
    client: OpenAICompatibleClient,
    catalog: CatalogSearch,
    shelf_search: Callable[[str, int], list[Hit]] | None = None,
    get_block: Callable[[str], Block] | None = None,
) -> MentorIntakeResponse:
    """Analyze a goal and return a proposal — never persists Areas/Wings/items.

    Drives the final LLM call through `homelib_rag.agent.run_agent`
    (specs/agent-tools.md: "on the Mentor request path since 2026-09-06"),
    with `search_shelf`/`search_catalog`/`get_block` wired to this call's own
    `shelf_search`/`catalog`/`get_block` — so the loop is store-safe by
    construction, never through `run_agent`'s own Postgres-bound default
    tool table. `MentorIntakeResponse.tool_calls`/`rounds_used` report what
    the loop actually did.
    """
    notice = detect_high_stakes_notice(goal, interests)
    hits = shelf_search(goal, 5) if shelf_search is not None else []
    candidates = catalog(goal, interests or None)

    if not hits and not candidates:
        return MentorIntakeResponse(
            request_id=str(uuid.uuid4()),
            rationale=_ABSTENTION_RATIONALE,
            citations=[],
            degraded=True,
            high_stakes_notice=notice,
        )

    prompt = _build_intake_prompt(goal, interests, level, hits, candidates)
    schema_hint = (
        '{"proposed_area": {"name": "...", "copy": "..."}|null, '
        '"proposed_wing": {"name": "...", "area_name": "...", "copy": "..."}|null, '
        '"proposed_path": {"title": "...", "kind": "reading"|"learning"|"action", '
        '"steps": [{"order": 0, "title": "...", "why": "...", '
        '"est_effort": "light"|"medium"|"deep"|null}]}, '
        '"rationale": "...", "citations": [{"passage": 1, "quote": "..."}]}'
    )
    messages = [
        ChatMessage(role="system", content=_INTAKE_SYSTEM),
        ChatMessage(
            role="user",
            content=f"{prompt}\n\nRespond with ONLY JSON of the form:\n{schema_hint}",
        ),
    ]

    mentor_tools = _mentor_tools(catalog, shelf_search, get_block)
    # Only advertise a tool schema the LLM can actually invoke — `get_block`
    # (and, in principle, `search_shelf`) is optional, so an un-wired one
    # must not appear in `tools=` only to dead-end as "unknown tool".
    mentor_schemas = [s for s in _MENTOR_TOOL_SCHEMAS if s["function"]["name"] in mentor_tools]

    try:
        agent_result = run_agent(
            messages,
            client=client,
            max_tokens=1200,
            tools=mentor_tools,
            tool_schemas=mentor_schemas,
        )
    except LLMUnreachableError:
        return MentorIntakeResponse(
            request_id=str(uuid.uuid4()),
            rationale="The mentor service is temporarily unavailable.",
            citations=[],
            degraded=True,
            high_stakes_notice=notice,
        )

    tool_calls = [record.tool_name for record in agent_result.tool_calls]
    rounds_used = agent_result.rounds_used

    try:
        payload = json.loads(agent_result.final_message or "{}")
        parsed = _LLMIntakeOutput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("mentor intake parse failed: %s", exc)
        return MentorIntakeResponse(
            request_id=str(uuid.uuid4()),
            rationale="Could not parse a grounded mentor proposal.",
            citations=[],
            degraded=True,
            high_stakes_notice=notice,
            tool_calls=tool_calls,
            rounds_used=rounds_used,
        )

    try:
        citations = _passage_citations(parsed.citations, hits) if hits else []
    except CitationValidationError:
        return MentorIntakeResponse(
            request_id=str(uuid.uuid4()),
            proposed_area=parsed.proposed_area,
            proposed_wing=parsed.proposed_wing,
            proposed_path=parsed.proposed_path,
            rationale=parsed.rationale,
            citations=[],
            degraded=True,
            high_stakes_notice=notice,
            tool_calls=tool_calls,
            rounds_used=rounds_used,
        )

    return MentorIntakeResponse(
        request_id=str(uuid.uuid4()),
        proposed_area=parsed.proposed_area,
        proposed_wing=parsed.proposed_wing,
        proposed_path=parsed.proposed_path,
        rationale=parsed.rationale,
        citations=citations,
        degraded=agent_result.degraded,
        high_stakes_notice=notice,
        tool_calls=tool_calls,
        rounds_used=rounds_used,
    )


def build_path(
    title: str,
    kind: Literal["reading", "learning", "action"],
    steps: list[RoadmapStep],
    *,
    catalog: CatalogSearch,
    interests: list[str],
    goal: str,
) -> PathResponse:
    """Create an accepted path artifact after user confirmation."""
    if not steps:
        raise RoadmapParseError("path must contain at least one step")
    candidates = catalog(goal, interests or None)
    valid_ol_keys = {entry.ol_key for entry in candidates}
    for step in steps:
        if step.ol_key is not None and step.ol_key not in valid_ol_keys:
            raise RoadmapParseError(
                f"step references ol_key {step.ol_key!r}, which is not among retrieved candidates"
            )
    return PathResponse(
        path_id=str(uuid.uuid4()),
        title=title,
        kind=kind,
        steps=steps,
    )
