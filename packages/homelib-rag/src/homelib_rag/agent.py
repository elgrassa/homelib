"""Explicit function-calling agent loop — see specs/agent-tools.md.

A hand-rolled request -> tool -> result loop over an OpenAI-compatible
chat-completions endpoint (Ollama `/v1` by default). No LangChain: the loop
itself is the point (course module M1), and a hand-rolled loop keeps every
tool call inspectable via `AgentResult.tool_calls`.

Four typed tools the model may call: `search_shelf` (retrieval over the
ingested shelf), `search_catalog` (Open Library catalog), `build_roadmap`
(wraps `homelib_rag.roadmap.build_roadmap` with default client/catalog
wiring), and `get_block` (fetch one block by id — also reused directly by
`apps/api`'s `GET /v1/blocks/{block_id}`, so the two never disagree about
what a block looks like).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import psycopg
from homelib_core.models import Block, CatalogEntry, Provenance
from pydantic import BaseModel, ConfigDict

from homelib_rag.answer import (
    ChatMessage,
    OpenAICompatibleClient,
    default_llm_client,
)
from homelib_rag.hybrid import hybrid_search
from homelib_rag.models import Hit
from homelib_rag.roadmap import Level, RoadmapResponse
from homelib_rag.roadmap import build_roadmap as _roadmap_build_roadmap

__all__ = [
    "TOOL_SCHEMAS",
    "AgentResult",
    "ToolCallRecord",
    "build_roadmap",
    "get_block",
    "run_agent",
    "search_catalog",
    "search_shelf",
]

logger = logging.getLogger(__name__)

_DEFAULT_DATABASE_URL = "postgresql://homelib:homelib_local_dev@localhost:5432/homelib"

# A tool result summary this long is not "a bounded success summary"
# anymore (specs/agent-tools.md: "result_summary: str  # truncated repr").
_MAX_SUMMARY_CHARS = 800
_MAX_CATALOG_RESULTS = 20


# ── Tool schemas (the `tools=` payload sent to the chat endpoint) ──────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_shelf",
            "description": "Full-text search over the ingested book shelf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search the Open Library catalog for books by topic or subject.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "subjects": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_roadmap",
            "description": (
                "Build a personalized, ordered reading roadmap from interests, level, and a goal."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "interests": {"type": "array", "items": {"type": "string"}},
                    "level": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "advanced"],
                    },
                    "goal": {"type": "string"},
                },
                "required": ["interests", "level", "goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_block",
            "description": "Fetch one block of a book's text by its block_id.",
            "parameters": {
                "type": "object",
                "properties": {"block_id": {"type": "string"}},
                "required": ["block_id"],
            },
        },
    },
]


# ── Tool implementations ───────────────────────────────────────────────────


def search_shelf(query: str, k: int = 5) -> list[Hit]:
    """Full-text search over the ingested book shelf (RRF hybrid search)."""
    hits, _mode_used = hybrid_search(query, k, mode="hybrid")
    return hits


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)


def _connect() -> psycopg.Connection[tuple[Any, ...]]:
    """Open a new Postgres connection. Test seam: monkeypatch this directly."""
    return psycopg.connect(_dsn())


def search_catalog(query: str, subjects: list[str] | None = None) -> list[CatalogEntry]:
    """Search the `catalog` table (Open Library corpus) by subject overlap or
    a title/subject substring match. Raises `ValueError` for an empty
    (post-strip) `query`, matching `homelib_rag.index`'s own convention."""
    if not query.strip():
        raise ValueError("query must not be empty")
    if os.environ.get("HOMELIB_SQLITE_PATH", "").strip():
        # Same predicate as homelib_rag.index (ADR-004). Dispatching HERE, not
        # in the API deps, covers every binding at once: `Deps.catalog_search`,
        # the `build_roadmap` wrapper below, and `_TOOL_FUNCTIONS`.
        from homelib_rag.sqlite_index import search_catalog as _sqlite_search_catalog

        return _sqlite_search_catalog(query, subjects)
    with _connect() as conn, conn.cursor() as cur:
        if subjects:
            cur.execute(
                """
                SELECT ol_key, title, authors, subjects, first_publish_year,
                       description, provenance_note
                FROM catalog
                WHERE subjects && %s::text[]
                LIMIT %s
                """,
                (list(subjects), _MAX_CATALOG_RESULTS),
            )
        else:
            like = f"%{query}%"
            cur.execute(
                """
                SELECT ol_key, title, authors, subjects, first_publish_year,
                       description, provenance_note
                FROM catalog
                WHERE title ILIKE %s
                   OR EXISTS (SELECT 1 FROM unnest(subjects) s WHERE s ILIKE %s)
                LIMIT %s
                """,
                (like, like, _MAX_CATALOG_RESULTS),
            )
        rows = cur.fetchall()
    return [
        CatalogEntry(
            ol_key=row[0],
            title=row[1],
            authors=list(row[2]),
            subjects=list(row[3]),
            first_publish_year=row[4],
            description=row[5],
            provenance_note=row[6] or "",
        )
        for row in rows
    ]


def _block_from_pg_row(row: Any) -> Block:
    bid, book_id, ordinal, section_path, text, char_start, char_end = row[:7]
    fmt, page, spine_index, anchor = row[7:]
    return Block(
        block_id=bid,
        book_id=book_id,
        ordinal=ordinal,
        section_path=list(section_path),
        text=text,
        char_start=char_start,
        char_end=char_end,
        provenance=Provenance(
            format=fmt,
            page=page,
            spine_index=spine_index,
            anchor=anchor,
            source_sha256="",
        ),
    )


def get_block(block_id: str) -> Block:
    """Fetch one `Block` by id. Raises `KeyError` if `block_id` is unknown —
    `apps/api`'s `GET /v1/blocks/{block_id}` maps that to a 404.

    `Provenance.source_sha256` is required by `homelib_core.models.Provenance`
    but is not a persisted column on `blocks` (specs/indexing.md's schema
    tracks `format`/`page`/`spine_index`/`anchor` only) — reconstructed here
    as `""` rather than invented, since the original file's hash genuinely
    isn't recoverable from this row.
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT block_id, book_id, ordinal, section_path, text, char_start, char_end,
                   format, page, spine_index, anchor
            FROM blocks
            WHERE block_id = %s
            """,
            (block_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"block not found: {block_id!r}")
    return _block_from_pg_row(row)


def get_book_block(book_id: str, ordinal: int) -> Block:
    """One block of ``book_id`` at dense ``ordinal``. Raises ``KeyError`` if missing."""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT block_id, book_id, ordinal, section_path, text, char_start, char_end,
                   format, page, spine_index, anchor
            FROM blocks
            WHERE book_id = %s AND ordinal = %s
            """,
            (book_id, ordinal),
        )
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"block not found: {book_id!r}@{ordinal}")
    return _block_from_pg_row(row)


def build_roadmap(interests: list[str], level: Level, goal: str) -> RoadmapResponse:
    """Agent-tool wrapper over `homelib_rag.roadmap.build_roadmap`, with the
    default LLM client and `search_catalog` wired in — the tool-calling
    surface takes no `client`/`catalog` arguments (specs/agent-tools.md)."""
    return _roadmap_build_roadmap(
        interests, level, goal, client=default_llm_client(), catalog=search_catalog
    )


_TOOL_FUNCTIONS: dict[str, Any] = {
    "search_shelf": search_shelf,
    "search_catalog": search_catalog,
    "build_roadmap": build_roadmap,
    "get_block": get_block,
}


# ── Agent records ───────────────────────────────────────────────────────────


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    round: int
    tool_name: str
    arguments: dict[str, Any]
    result_summary: str
    error: str | None = None


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    final_message: str
    tool_calls: list[ToolCallRecord]
    rounds_used: int
    degraded: bool


def _summarize(result: Any) -> str:
    text = repr(result)
    if len(text) <= _MAX_SUMMARY_CHARS:
        return text
    return text[:_MAX_SUMMARY_CHARS] + "...[truncated]"


def _parse_arguments(raw_arguments: str | None) -> dict[str, Any]:
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def run_agent(
    messages: list[ChatMessage],
    *,
    max_rounds: int = 6,
    client: OpenAICompatibleClient,
) -> AgentResult:
    """Drive the request -> tool -> result loop until the model produces a
    final message with no further tool calls, or `max_rounds` is hit.

    `LLMUnreachableError` from `client.chat(...)` propagates out uncaught —
    turning that into a `200 degraded: true` response is `apps/api`'s job
    (specs/agent-tools.md), not this loop's.
    """
    history = list(messages)
    tool_call_log: list[ToolCallRecord] = []
    last_unknown_tool: str | None = None

    for round_index in range(max_rounds):
        response = client.chat(history, tools=TOOL_SCHEMAS)

        if not response.tool_calls:
            return AgentResult(
                final_message=response.content or "",
                tool_calls=tool_call_log,
                rounds_used=round_index + 1,
                degraded=False,
            )

        history.append(
            ChatMessage(
                role="assistant", content=response.content or "", tool_calls=response.tool_calls
            )
        )

        for tool_call in response.tool_calls:
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")
            call_id = tool_call.get("id", "")
            arguments = _parse_arguments(function.get("arguments"))

            if tool_name not in _TOOL_FUNCTIONS:
                if tool_name == last_unknown_tool:
                    return AgentResult(
                        final_message=(
                            "Reached an unrecoverable state: the model requested the "
                            f"unknown tool {tool_name!r} twice in a row."
                        ),
                        tool_calls=tool_call_log,
                        rounds_used=round_index + 1,
                        degraded=True,
                    )
                last_unknown_tool = tool_name
                tool_call_log.append(
                    ToolCallRecord(
                        round=round_index,
                        tool_name=tool_name,
                        arguments=arguments,
                        result_summary="",
                        error=f"unknown tool: {tool_name}",
                    )
                )
                history.append(
                    ChatMessage(
                        role="tool", content=f"unknown tool: {tool_name}", tool_call_id=call_id
                    )
                )
                continue

            last_unknown_tool = None
            try:
                result = _TOOL_FUNCTIONS[tool_name](**arguments)
            except Exception as exc:  # a single tool failure never crashes the request
                error_message = str(exc)
                logger.warning("run_agent: tool %r raised: %s", tool_name, error_message)
                tool_call_log.append(
                    ToolCallRecord(
                        round=round_index,
                        tool_name=tool_name,
                        arguments=arguments,
                        result_summary="",
                        error=error_message,
                    )
                )
                history.append(
                    ChatMessage(
                        role="tool", content=f"error: {error_message}", tool_call_id=call_id
                    )
                )
                continue

            summary = _summarize(result)
            tool_call_log.append(
                ToolCallRecord(
                    round=round_index,
                    tool_name=tool_name,
                    arguments=arguments,
                    result_summary=summary,
                    error=None,
                )
            )
            history.append(ChatMessage(role="tool", content=summary, tool_call_id=call_id))

    return AgentResult(
        final_message=f"Reached the round limit ({max_rounds}) without a final answer.",
        tool_calls=tool_call_log,
        rounds_used=max_rounds,
        degraded=True,
    )
