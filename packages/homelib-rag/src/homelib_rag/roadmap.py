"""Personalized reading roadmap generation — see specs/roadmap.md.

Turns a user's stated interests, level, and goal into a typed, validated,
ordered reading roadmap over the Open Library catalog corpus. Parsing is
fail-closed: the LLM gets exactly one bounded repair retry on a schema/parse
failure (or on an invented `ol_key` — a step referencing a book absent from
the retrieved `candidates`), then `RoadmapParseError` — a half-parsed
roadmap is never returned. Connectivity failures (`LLMUnreachableError`)
bypass the repair budget entirely and propagate immediately, since retrying
the same call cannot fix an unreachable endpoint.

The per-step `why` is free text the LLM generates at answer time; a
`CatalogEntry.description` (Open Library provenance is mixed per-record,
specs/core-models.md/§4.2) is passed into the prompt only as optional
background context, and the system prompt explicitly instructs the model
not to copy it verbatim as `why` — it is never our product copy.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from typing import Literal

from homelib_core.models import CatalogEntry
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from homelib_rag.answer import ChatMessage, OpenAICompatibleClient

__all__ = [
    "CatalogSearch",
    "Level",
    "RoadmapParseError",
    "RoadmapResponse",
    "RoadmapStep",
    "build_roadmap",
]

logger = logging.getLogger(__name__)

Level = Literal["beginner", "intermediate", "advanced"]

# `homelib_rag.index` catalog search, same corpus as `homelib_rag.agent.search_catalog`
# (specs/roadmap.md) — a plain callable so this module never has to import
# `homelib_rag.agent` (that would invert the dependency direction: `agent.py`
# imports `roadmap.py` to implement its own `build_roadmap` tool, not the
# other way around).
CatalogSearch = Callable[[str, "list[str] | None"], "list[CatalogEntry]"]

_MAX_CANDIDATES_IN_PROMPT = 30

_SYSTEM_PROMPT = (
    "You build a personalized, ordered reading roadmap from a list of "
    "candidate books. You may ONLY reference books from the numbered "
    "candidate list below — never invent a book, an ol_key, or an author "
    "not shown there. Order steps so prerequisites come before what depends "
    "on them (0-based indices into your own `steps` array). Each step's "
    "`why` must be YOUR OWN reasoning about why that book fits this "
    "person's interests, level, and goal — a `description` shown for a "
    "candidate is optional background only; never copy it verbatim into "
    "`why`. Respond with ONLY a JSON object of the form "
    '{"steps": [{"order": 0, "ol_key": "/works/OL123W", "book_id": null, '
    '"title": "...", "authors": ["..."], "why": "...", "prerequisites": [], '
    '"est_effort": "light"}], "rationale": "..."} and no other text. Use '
    "null for `ol_key`/`book_id` only if you truly cannot ground a step in "
    "a listed candidate; prefer grounded steps."
)


class RoadmapStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    order: int
    ol_key: str | None
    book_id: str | None
    title: str
    authors: list[str]
    why: str
    prerequisites: list[int]
    est_effort: Literal["light", "medium", "deep"]


class RoadmapResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    steps: list[RoadmapStep]
    rationale: str


class RoadmapParseError(Exception):
    """Raised when the LLM's roadmap output fails to parse/validate on both
    the initial attempt and the single bounded repair attempt."""


class _LLMRoadmapOutput(BaseModel):
    """The shape asked of the LLM — no `request_id`; that is generated
    server-side once parsing succeeds, never asked of the model."""

    model_config = ConfigDict(extra="allow")

    steps: list[RoadmapStep] = Field(default_factory=list)
    rationale: str = ""


def _candidate_line(i: int, entry: CatalogEntry) -> str:
    desc = f" description={entry.description!r}" if entry.description else ""
    return (
        f"[{i}] ol_key={entry.ol_key!r} title={entry.title!r} authors={entry.authors!r} "
        f"subjects={entry.subjects!r}{desc}"
    )


def _build_prompt(
    interests: list[str], level: Level, goal: str, max_steps: int, candidates: list[CatalogEntry]
) -> str:
    lines = [
        f"Interests: {interests!r}",
        f"Level: {level}",
        f"Goal: {goal!r}",
        f"Produce at most {max_steps} steps.",
        "",
        "Candidates (the ONLY books you may cite):",
    ]
    for i, entry in enumerate(candidates[:_MAX_CANDIDATES_IN_PROMPT], start=1):
        lines.append(_candidate_line(i, entry))
    if not candidates:
        lines.append("(none retrieved — every step must use ol_key=null, book_id=null)")
    return "\n".join(lines)


def _repair_prompt(raw: str, validation_error: str) -> str:
    return (
        "Your previous response failed to parse/validate. Here is what you sent:\n\n"
        f"{raw}\n\n"
        f"Validation error:\n{validation_error}\n\n"
        "Respond again with ONLY a corrected JSON object in the exact same "
        "shape as before — no other text, and still only referencing the "
        "candidate list you were given."
    )


def _parse_and_validate(
    raw: str, candidates: list[CatalogEntry], max_steps: int = 8
) -> RoadmapResponse:
    """Parse+validate one LLM roadmap response. Raises `RoadmapParseError`.

    Truncates deterministically to `max_steps` by `order` rather than
    treating an over-long response as a parse failure (specs/roadmap.md).
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RoadmapParseError(f"invalid JSON: {exc}") from exc

    try:
        parsed = _LLMRoadmapOutput.model_validate(data)
    except ValidationError as exc:
        raise RoadmapParseError(f"schema validation failed: {exc}") from exc

    valid_ol_keys = {entry.ol_key for entry in candidates}
    for step in parsed.steps:
        if step.ol_key is not None and step.ol_key not in valid_ol_keys:
            raise RoadmapParseError(
                f"step references ol_key {step.ol_key!r}, which is not among the "
                "retrieved candidates (invented book)"
            )

    steps = sorted(parsed.steps, key=lambda s: s.order)[:max_steps]
    return RoadmapResponse(
        request_id=str(uuid.uuid4()),
        steps=steps,
        rationale=parsed.rationale,
    )


def build_roadmap(
    interests: list[str],
    level: Level,
    goal: str,
    max_steps: int = 8,
    *,
    client: OpenAICompatibleClient,
    catalog: CatalogSearch,
) -> RoadmapResponse:
    """Build a `RoadmapResponse` grounded only in retrieved catalog candidates.

    `LLMUnreachableError` propagates uncaught from either LLM call — the
    repair budget is reserved for parse/validation failures, not connectivity
    (specs/roadmap.md). A `RoadmapParseError` is raised only after the first
    call AND the one repair call both fail to parse/validate.
    """
    candidates = catalog(goal, interests or None)

    prompt = _build_prompt(interests, level, goal, max_steps, candidates)
    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ]

    response = client.chat(messages, response_format={"type": "json_object"})
    raw = response.content or ""
    try:
        return _parse_and_validate(raw, candidates, max_steps)
    except RoadmapParseError as first_error:
        first_error_message = str(first_error)
        logger.warning("build_roadmap: first attempt failed to parse/validate: %s", first_error)

    repair_messages = [
        *messages,
        ChatMessage(role="assistant", content=raw),
        ChatMessage(role="user", content=_repair_prompt(raw, first_error_message)),
    ]
    repair_response = client.chat(repair_messages, response_format={"type": "json_object"})
    repair_raw = repair_response.content or ""
    try:
        return _parse_and_validate(repair_raw, candidates, max_steps)
    except RoadmapParseError as second_error:
        raise RoadmapParseError(
            f"roadmap generation failed after one repair attempt: {second_error}"
        ) from second_error
