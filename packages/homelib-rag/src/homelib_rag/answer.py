"""Citation-checked answer synthesis — see specs/answer.md.

Synthesizes an `AskResponse` from a question and a set of already-retrieved
`Hit`s, with block-level citations (`book · section_path · page`). The
binding contract this module exists to enforce: every `Citation.chunk_id`
must resolve to a chunk that actually appears in `hits`, and every
`Citation.quote` must be genuinely, verbatim present in that chunk's text —
an answer that cites something it was not given is never passed through as
trustworthy (`_validate_citations`).

A second, related defect this module is built to prevent: a live probe found
the local model, given passages labelled only with title and section,
inventing an author (attributing Ford's *My Life and Work* to Theodore
Roosevelt). Two structural mitigations, not just a prompt tweak:

1. The prompt context lists each passage's book title AND authors
   explicitly (`_book_metadata`/`_build_context_prompt`) — the model is never
   asked to recall or guess an author from a bare title.
2. `Citation.book_title` is never taken from the model's own output at all —
   it is always filled in server-side from `_book_metadata`, looked up by the
   cited chunk's real `book_id`. There is no code path by which a model-
   invented title or author can reach the response.

This module also owns the shared OpenAI-compatible chat-client seam
(`OpenAICompatibleClient`, `LLMUnreachableError`, `ChatMessage`, `LLMResponse`)
used by `homelib_rag.roadmap` and `homelib_rag.agent` — defined once here
because `answer.py` is the simplest, lowest-level LLM-touching module of the
three and both of the others import it, never the reverse.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol

import psycopg
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from homelib_rag.models import Hit

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "AskResponse",
    "ChatMessage",
    "Citation",
    "CitationValidationError",
    "LLMResponse",
    "LLMUnreachableError",
    "LLMUsage",
    "OpenAIClient",
    "OpenAICompatibleClient",
    "TokenUsage",
    "answer",
]

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_API_KEY = "ollama"
_DEFAULT_MODEL = "qwen2.5:7b-instruct"
_DEFAULT_DATABASE_URL = "postgresql://homelib:homelib_local_dev@localhost:5432/homelib"
_TIMEOUT_SECONDS = 30.0

# A passage list this long is not "a few relevant chunks" anymore; cap the
# prompt rather than let an unusually large `hits` list blow the context
# window silently.
_MAX_CONTEXT_HITS = 20

# Citations are made by PASSAGE NUMBER, not by chunk_id. Measured against
# qwen2.5:7b-instruct on the real corpus: asked for a 16-hex chunk_id, the
# model returned `10028766648516879691` — a confident-looking id belonging to
# nothing. Copying a long opaque identifier is precisely what a small model is
# worst at, and there is no reason to ask: the passages are already numbered
# for the reader, and mapping an ordinal back to a real chunk_id is one line
# of code. Same principle as `book_title` — never ask the model for a value
# the system already knows, because then a wrong one has no way in.
_SYSTEM_PROMPT = (
    "You answer a question using ONLY the numbered passages given below — "
    "never outside knowledge. Each passage begins with its number in square "
    "brackets, then the book's title, its authors, the section, and the page. "
    "The author names given are authoritative: never attribute a passage to "
    "an author not listed for it, and never guess an author who is not shown. "
    "For every claim you make, add an entry to `citations` whose `passage` is "
    "the number in square brackets of the passage you are citing — one of the "
    "numbers shown below and nothing else — and whose `quote` is copied "
    "VERBATIM from that passage's text: an exact run of words from it, not a "
    "paraphrase and not a summary. If the passages do not answer the "
    "question, say so plainly and return an empty `citations` list rather "
    "than guessing. Respond with ONLY a JSON object of the form "
    '{"answer": "...", "citations": [{"passage": 1, "quote": "..."}]} '
    "and no other text."
)


# ── Shared OpenAI-compatible client seam ────────────────────────────────────


class LLMUnreachableError(Exception):
    """Raised by an `OpenAICompatibleClient` on any connection/timeout/
    transport failure talking to the chat-completions endpoint, or on an
    empty/malformed response with no usable choice."""


class ChatMessage(BaseModel):
    """One turn in a chat-completion request. See specs/agent-tools.md."""

    model_config = ConfigDict(extra="allow")

    role: str  # "system"|"user"|"assistant"|"tool"
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class LLMUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_tokens: int
    completion_tokens: int


class LLMResponse(BaseModel):
    """The normalized result of one `OpenAICompatibleClient.chat` call."""

    model_config = ConfigDict(extra="allow")

    content: str | None
    tool_calls: list[dict[str, Any]] | None = None
    usage: LLMUsage


class OpenAICompatibleClient(Protocol):
    """The minimal surface `answer.py`/`roadmap.py`/`agent.py` need from an
    OpenAI-compatible chat-completions client. `OpenAIClient` below is the
    production implementation; tests implement this same protocol with a
    scripted fake — no network, no `openai` import required in test code.
    """

    model: str

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        response_format: Mapping[str, Any] | None = None,
    ) -> LLMResponse: ...


class OpenAIClient:
    """Default `OpenAICompatibleClient`, backed by the `openai` SDK against
    an OpenAI-compatible chat-completions endpoint (Ollama `/v1` by default;
    a cloud endpoint is a drop-in override via `LLM_BASE_URL`/`LLM_API_KEY`).

    Every failure mode of the underlying SDK call — connection refused,
    timeout, non-2xx response, an empty `choices` list — is normalized to
    `LLMUnreachableError` at this single seam, so every caller has exactly
    one exception type to handle for "the endpoint didn't work".
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = _TIMEOUT_SECONDS,
    ) -> None:
        self.model = model or os.environ.get("LLM_MODEL", _DEFAULT_MODEL)
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", _DEFAULT_BASE_URL)
        self._timeout = timeout
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=api_key or os.environ.get("LLM_API_KEY", _DEFAULT_API_KEY),
            timeout=timeout,
        )

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        response_format: Mapping[str, Any] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "timeout": self._timeout,
        }
        if tools:
            kwargs["tools"] = list(tools)
        if response_format:
            kwargs["response_format"] = dict(response_format)
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # connection error, timeout, non-2xx, ...
            raise LLMUnreachableError(str(exc)) from exc
        if not response.choices:
            raise LLMUnreachableError("empty LLM response: no choices returned")
        message = response.choices[0].message
        tool_calls: list[dict[str, Any]] | None = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
                if tc.type == "function"
            ]
        usage = response.usage
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            usage=LLMUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            ),
        )


# ── AskResponse-shaped output ────────────────────────────────────────────


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: int
    completion: int


class Citation(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk_id: str
    book_id: str
    book_title: str
    section_path: list[str]
    page: int | None
    quote: str


class AskResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    answer: str
    citations: list[Citation]
    arm_used: str
    degraded: bool
    latency_ms: int
    tokens: TokenUsage


class CitationValidationError(Exception):
    """Raised when a citation cites a chunk_id absent from `hits`, or a
    `quote` is not a verbatim substring of the matching hit's text."""


class _RawCitation(BaseModel):
    """The shape the LLM is asked to produce for one citation.

    Deliberately has NO `book_title`, `book_id` or `chunk_id` field. The model
    is never asked for any of them, so it cannot supply an invented one:
    `answer()` fills them in from the hit at `passage` and from
    `_book_metadata`. `passage` is the 1-based number shown in the prompt,
    which is small enough for a 7B model to copy reliably — a 16-hex chunk_id
    demonstrably was not.
    """

    model_config = ConfigDict(extra="allow")

    passage: int
    quote: str


class _RawAnswer(BaseModel):
    """The shape the LLM is asked to produce, before citation validation."""

    model_config = ConfigDict(extra="allow")

    answer: str
    citations: list[_RawCitation] = Field(default_factory=list)


# ── Book metadata lookup (test seam) ────────────────────────────────────────


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)


def _book_metadata(book_ids: Sequence[str]) -> dict[str, tuple[str, list[str]]]:
    """`book_id -> (title, authors)` for every id in `book_ids`.

    Test seam: monkeypatch this directly to avoid a live Postgres. `Hit`
    (specs/indexing.md) carries no title/authors — only `answer()` needs
    them, for the prompt context and for `Citation.book_title`, so the
    lookup lives here rather than being threaded through `Hit`.
    """
    if not book_ids:
        return {}
    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT book_id, title, authors FROM books WHERE book_id = ANY(%s)",
            (list(set(book_ids)),),
        )
        return {row[0]: (row[1], list(row[2])) for row in cur.fetchall()}


def _build_context_prompt(
    question: str, hits: list[Hit], book_meta: dict[str, tuple[str, list[str]]]
) -> str:
    lines = [f"Question: {question}", "", "Passages:"]
    for i, hit in enumerate(hits[:_MAX_CONTEXT_HITS], start=1):
        title, authors = book_meta.get(hit.book_id, ("(unknown title)", []))
        section = " / ".join(hit.section_path) if hit.section_path else "(no section)"
        page = hit.page if hit.page is not None else "unknown"
        lines.append(
            f"[{i}] chunk_id={hit.chunk_id!r} book={title!r} authors={authors!r} "
            f"section={section!r} page={page}"
        )
        lines.append(hit.text)
        lines.append("")
    return "\n".join(lines)


def _collapse_whitespace(text: str) -> str:
    """Whitespace-insensitive form for quote comparison.

    Book text is hard-wrapped, so a chunk holds "division of labour\nin this
    factory" while the model returns it re-flowed onto one line. Byte-for-byte
    that is not a substring, yet nothing was fabricated — the difference is a
    line break a typesetter chose a century ago. Measured live before this
    change: 3 of 3 sampled questions degraded on exactly that.

    This is the smallest loosening that admits real quotes, and deliberately
    the only one. Word order, wording and punctuation still have to match
    exactly, so a paraphrase is rejected as firmly as before — which is the
    whole point of the check.
    """
    return " ".join(text.split())


def _resolve_quote(raw_citation: _RawCitation, context_hits: list[Hit]) -> Hit | None:
    """The passage a quote actually came from, or `None` if it came from none.

    The model's `passage` number is treated as a hint, not as truth. It is
    checked first — it is usually right, and preferring it keeps attribution
    stable when the same sentence appears twice — but if the quote is not in
    that passage, every other shown passage is searched before giving up.

    This is not leniency. Observed live: asked what makes writing clear, the
    model returned a real, verbatim sentence of Taylor on scientific
    management while citing the number of a completely different extract. The
    words were genuine; only the label was wrong. Binding the citation to the
    passage the text demonstrably occupies is *stronger* attribution than
    trusting a number the model typed — the same reason `book_title` and
    `chunk_id` are never taken from its output either. The model is reliable
    at copying text and unreliable at bookkeeping, so it does the copying and
    this function does the bookkeeping.

    A quote present in no shown passage still returns `None`, and the caller
    degrades: there is nothing to bind it to, and the answer is not grounded.
    """
    needle = _collapse_whitespace(raw_citation.quote)
    if not needle:
        return None

    hinted = raw_citation.passage - 1
    if 0 <= hinted < len(context_hits):
        candidate = context_hits[hinted]
        if needle in _collapse_whitespace(candidate.text):
            return candidate

    for index, candidate in enumerate(context_hits):
        if index == hinted:
            continue
        if needle in _collapse_whitespace(candidate.text):
            logger.info(
                "citation named passage %d but its quote is in passage %d; "
                "reattributing to where the text actually is",
                raw_citation.passage,
                index + 1,
            )
            return candidate
    return None


def _validate_citations(citations: list[Citation], hits: list[Hit]) -> None:
    """Raise `CitationValidationError` unless every citation is genuine.

    Two checks per citation, per specs/answer.md: `chunk_id` must equal one
    of `hits`' `chunk_id` values, and `quote` must be an exact substring of
    that hit's `text`. `Citation.book_title`/`book_id` are not re-checked
    here because `answer()` never lets the model set them in the first
    place (see `_RawCitation`) — they are always the real stored values.
    """
    hit_by_id = {hit.chunk_id: hit for hit in hits}
    for citation in citations:
        hit = hit_by_id.get(citation.chunk_id)
        if hit is None:
            raise CitationValidationError(
                f"citation cites chunk_id {citation.chunk_id!r}, which is not in the retrieved hits"
            )
        if _collapse_whitespace(citation.quote) not in _collapse_whitespace(hit.text):
            raise CitationValidationError(
                f"citation quote for chunk_id {citation.chunk_id!r} is not a verbatim "
                "substring of that chunk's text"
            )


def _degraded_response(arm_used: str, reason: str) -> AskResponse:
    logger.warning("answer() returning a degraded response: %s", reason)
    return AskResponse(
        request_id=str(uuid.uuid4()),
        answer=("I couldn't produce a verified answer right now. Please try again in a moment."),
        citations=[],
        arm_used=arm_used,
        degraded=True,
        latency_ms=0,
        tokens=TokenUsage(prompt=0, completion=0),
    )


def answer(
    question: str,
    hits: list[Hit],
    *,
    client: OpenAICompatibleClient,
    arm_used: str,
) -> AskResponse:
    """Synthesize an `AskResponse` for `question` from already-retrieved `hits`.

    Never raises: an unreachable LLM, a malformed LLM response, or a
    hallucinated/invalid citation all produce a `_degraded_response(...)`
    instead of propagating — this function's contract is "always a usable
    `AskResponse`," matching specs/answer.md's degradation rule.
    """
    start = time.monotonic()
    try:
        book_meta = _book_metadata([hit.book_id for hit in hits])
    except Exception as exc:  # DB unreachable, etc. — never let this 500 the request
        logger.warning("answer(): failed to load book metadata: %s", exc)
        return _degraded_response(arm_used, f"failed to load book metadata: {exc}")

    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(role="user", content=_build_context_prompt(question, hits, book_meta)),
    ]

    try:
        response = client.chat(messages, response_format={"type": "json_object"})
    except LLMUnreachableError as exc:
        return _degraded_response(arm_used, f"LLM unreachable: {exc}")
    except Exception as exc:  # belt-and-braces: never let an LLM call 500 this request
        logger.exception("answer(): unexpected error calling the LLM")
        return _degraded_response(arm_used, f"unexpected LLM error: {exc}")

    raw_content = response.content or ""
    try:
        parsed = _RawAnswer.model_validate_json(raw_content)
    except ValidationError as exc:
        return _degraded_response(arm_used, f"malformed LLM output: {exc}")

    # Only the passages actually shown to the model are citable. Slicing the
    # same way `_build_context_prompt` does keeps the two in step.
    context_hits = hits[:_MAX_CONTEXT_HITS]
    citations: list[Citation] = []
    for raw_citation in parsed.citations:
        source = _resolve_quote(raw_citation, context_hits)
        if source is None:
            return _degraded_response(
                arm_used,
                f"citation quote {raw_citation.quote[:60]!r} does not appear in any "
                "of the passages provided",
            )
        title, _authors = book_meta.get(source.book_id, ("(unknown title)", []))
        citations.append(
            Citation(
                chunk_id=source.chunk_id,
                book_id=source.book_id,
                book_title=title,
                section_path=source.section_path,
                page=source.page,
                quote=raw_citation.quote,
            )
        )

    try:
        _validate_citations(citations, hits)
    except CitationValidationError as exc:
        return _degraded_response(arm_used, str(exc))

    latency_ms = int((time.monotonic() - start) * 1000)
    return AskResponse(
        request_id=str(uuid.uuid4()),
        answer=parsed.answer,
        citations=citations,
        arm_used=arm_used,
        degraded=False,
        latency_ms=latency_ms,
        tokens=TokenUsage(
            prompt=response.usage.prompt_tokens, completion=response.usage.completion_tokens
        ),
    )


_default_client_lock = threading.Lock()
_default_client: OpenAIClient | None = None


def default_llm_client() -> OpenAIClient:
    """Process-wide lazy `OpenAIClient` singleton, built from env vars."""
    global _default_client
    if _default_client is None:
        with _default_client_lock:
            if _default_client is None:
                _default_client = OpenAIClient()
    return _default_client
