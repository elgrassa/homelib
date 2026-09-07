"""Shelf / collection-meta Ask routing — inventory & recommend-from-available.

Passage RAG (`answer.answer`) only sees retrieved chunks. Collection questions
("what do you have?", "which available romance book…") need the book list /
catalog, not passages. This module detects that intent and builds a grounded
`AskResponse` from shelf titles/authors (optionally appending catalog links).
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from homelib_rag.answer import AskResponse, TokenUsage

__all__ = [
    "ShelfBookRef",
    "answer_shelf_meta",
    "is_shelf_meta_intent",
]

# Content questions about a work stay on the passage path even if they mention
# "book" or "shelf".
_CONTENT_QUESTION = re.compile(
    r"\b("
    r"who wrote|author of|wrote\b|written by|"
    r"quote|passage|chapter|page\s+\d|"
    r"what does\b|according to|meaning of|summarize|explain|"
    r"where (does|do)|when (does|did)|how (does|did)"
    r")\b",
    re.IGNORECASE,
)

# Inventory, recommend-from-available, genre-among-shelf, "what do you have".
_SHELF_META_QUESTION = re.compile(
    r"("
    r"what do you have|"
    r"what('s| is) (on )?(my |the )?shelf|"
    r"what books?( do you have| are (available|on)| have you)|"
    r"which .{0,60}\bbooks?\b|"
    r"\bavailable .{0,40}\bbooks?\b|"
    r"from available books?|"
    r"on (the |my )?shelf|"
    r"(recommend|suggest|more interesting).{0,60}(book|shelf|available)|"
    r"(available|shelf).{0,40}(more interesting|recommend|suggest)|"
    r"(romance|fiction|biography|philosophy|history|poetry|classic).{0,40}"
    r"(available|shelf|book)|"
    r"list (my |the |available )?books|"
    r"\binventory\b|"
    r"what from available"
    r")",
    re.IGNORECASE,
)

_GENRE_TOKEN = re.compile(
    r"\b(romance|fiction|biography|philosophy|history|poetry|classic|"
    r"autobiography|essay|essays|management|economics|war|stoicism)\b",
    re.IGNORECASE,
)


class _CatalogLink(Protocol):
    title: str
    authors: list[str]
    ol_key: str
    provenance_note: str


@dataclass(frozen=True)
class ShelfBookRef:
    """Minimal shelf row for Ask shelf-meta answers (title + authors)."""

    title: str
    authors: tuple[str, ...]

    @classmethod
    def from_parts(cls, title: str, authors: Sequence[str]) -> ShelfBookRef:
        return cls(title=title, authors=tuple(authors))


def is_shelf_meta_intent(question: str) -> bool:
    """True when Ask should use shelf/catalog metadata instead of passages.

    Rule: match inventory / recommend-from-available / genre-among-shelf cues,
    unless the question is clearly about passage content of a work (who wrote,
    quote, chapter, …).
    """
    text = question.strip()
    if not text:
        return False
    if _CONTENT_QUESTION.search(text):
        return False
    return _SHELF_META_QUESTION.search(text) is not None


def _format_book_line(book: ShelfBookRef) -> str:
    authors = ", ".join(book.authors) if book.authors else "unknown author"
    return f"{book.title} — {authors}"


def _genre_from_question(question: str) -> str | None:
    match = _GENRE_TOKEN.search(question)
    return match.group(1).lower() if match else None


def _book_matches_genre(book: ShelfBookRef, genre: str) -> bool:
    haystack = f"{book.title} {' '.join(book.authors)}".lower()
    return genre in haystack


def _catalog_link_line(entry: _CatalogLink) -> str:
    key = entry.ol_key if entry.ol_key.startswith("/") else f"/{entry.ol_key}"
    url = f"https://openlibrary.org{key}"
    authors = ", ".join(entry.authors) if entry.authors else "unknown author"
    note = entry.provenance_note.strip() or "Open Library"
    return f"{entry.title} — {authors} ({note}: {url})"


def answer_shelf_meta(
    question: str,
    books: Sequence[ShelfBookRef],
    *,
    arm_used: str = "shelf_meta",
    catalog_entries: Sequence[_CatalogLink] | None = None,
) -> AskResponse:
    """Grounded Ask answer from shelf titles/authors (no passage LLM call)."""
    start = time.monotonic()
    shelf = list(books)
    genre = _genre_from_question(question)

    if not shelf:
        body = (
            "This shelf has no books yet. Add or ingest titles, then ask again "
            "about what is available."
        )
    elif genre:
        matched = [b for b in shelf if _book_matches_genre(b, genre)]
        if matched:
            lines = "\n".join(f"- {_format_book_line(b)}" for b in matched)
            body = (
                f"From the available shelf books matching {genre!r} "
                f"({len(matched)} of {len(shelf)}):\n{lines}"
            )
        else:
            available = "\n".join(f"- {_format_book_line(b)}" for b in shelf)
            body = (
                f"None of the available shelf books match {genre!r} by title "
                f"or author. Here is what is on the shelf ({len(shelf)} books):\n"
                f"{available}"
            )
    else:
        lines = "\n".join(f"- {_format_book_line(b)}" for b in shelf)
        body = f"On this shelf ({len(shelf)} books):\n{lines}"

    if catalog_entries:
        extras = "\n".join(f"- {_catalog_link_line(e)}" for e in catalog_entries[:5])
        if extras:
            body = (
                f"{body}\n\nRelated lawful catalog matches "
                f"(not necessarily on this shelf):\n{extras}"
            )

    latency_ms = int((time.monotonic() - start) * 1000)
    return AskResponse(
        request_id=str(uuid.uuid4()),
        answer=body,
        citations=[],
        arm_used=arm_used,
        degraded=False,
        latency_ms=latency_ms,
        tokens=TokenUsage(prompt=0, completion=0),
    )
