"""SQLite-backed helpers for FastAPI when HOMELIB_SQLITE_PATH is set (P0 wire)."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from homelib_core.models import Block, Provenance

from apps.api.schemas import BookSummary
from apps.store.sqlite import connect, migrate, row_counts

__all__ = [
    "open_store",
    "sqlite_counts",
    "sqlite_db_reachable",
    "sqlite_get_block",
    "sqlite_get_book_block",
    "sqlite_list_books",
    "sqlite_log_answer",
    "sqlite_log_query",
    "sqlite_path",
    "sqlite_record_feedback",
]


def sqlite_path() -> Path | None:
    raw = os.environ.get("HOMELIB_SQLITE_PATH", "").strip()
    return Path(raw) if raw else None


def open_store() -> sqlite3.Connection:
    path = sqlite_path()
    if path is None:
        raise RuntimeError("HOMELIB_SQLITE_PATH is not set")
    conn = connect(path)
    migrate(conn)
    return conn


def sqlite_db_reachable() -> bool:
    try:
        with open_store() as conn:
            conn.execute("SELECT 1")
    except Exception:
        return False
    return True


def sqlite_counts() -> tuple[int, int]:
    try:
        with open_store() as conn:
            counts = row_counts(conn)
    except Exception:
        return (0, 0)
    return (int(counts.get("books", 0)), int(counts.get("chunks", 0)))


def sqlite_list_books() -> list[BookSummary]:
    with open_store() as conn:
        rows = conn.execute(
            """
            SELECT b.book_id, b.title, b.authors,
                   (SELECT count(*) FROM blocks bl WHERE bl.book_id = b.book_id),
                   (SELECT count(*) FROM chunks c WHERE c.book_id = b.book_id),
                   COALESCE(
                       (SELECT bl2.format FROM blocks bl2 WHERE bl2.book_id = b.book_id
                        ORDER BY bl2.ordinal LIMIT 1),
                       ''
                   )
            FROM books b
            ORDER BY b.title
            """
        ).fetchall()
    out: list[BookSummary] = []
    for row in rows:
        authors_raw = row[2]
        authors = json.loads(str(authors_raw)) if authors_raw else []
        if not isinstance(authors, list):
            authors = [str(authors_raw)]
        out.append(
            BookSummary(
                book_id=str(row[0]),
                title=str(row[1]),
                authors=[str(a) for a in authors],
                blocks=int(row[3]),
                chunks=int(row[4]),
                format=str(row[5] or ""),
            )
        )
    return out


def _block_from_row(row: Any) -> Block:
    section = json.loads(str(row[3]))
    fmt_raw = str(row[7] or "txt")
    allowed: set[str] = {"epub", "pdf", "txt", "md", "djvu"}
    fmt = fmt_raw if fmt_raw in allowed else "txt"
    return Block(
        block_id=str(row[0]),
        book_id=str(row[1]),
        ordinal=int(row[2]),
        section_path=section if isinstance(section, list) else [],
        text=str(row[4]),
        char_start=int(row[5]),
        char_end=int(row[6]),
        provenance=Provenance(
            format=fmt,  # type: ignore[arg-type]
            page=int(row[8]) if row[8] is not None else None,
            spine_index=int(row[9]) if row[9] is not None else None,
            anchor=str(row[10]) if row[10] is not None else None,
            source_sha256="",
        ),
    )


def sqlite_get_block(block_id: str) -> Block:
    with open_store() as conn:
        row = conn.execute(
            "SELECT block_id, book_id, ordinal, section_path, text, char_start, char_end, "
            "format, page, spine_index, anchor FROM blocks WHERE block_id = ?",
            (block_id,),
        ).fetchone()
    if row is None:
        raise LookupError(block_id)
    return _block_from_row(row)


def sqlite_get_book_block(book_id: str, ordinal: int) -> Block:
    """One page of a book by dense ordinal (Projection Prev/Next)."""
    with open_store() as conn:
        row = conn.execute(
            "SELECT block_id, book_id, ordinal, section_path, text, char_start, char_end, "
            "format, page, spine_index, anchor FROM blocks "
            "WHERE book_id = ? AND ordinal = ?",
            (book_id, ordinal),
        ).fetchone()
    if row is None:
        raise LookupError(f"{book_id}@{ordinal}")
    return _block_from_row(row)


def sqlite_log_query(row: Any) -> None:
    try:
        with open_store() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO query_log ("
                "request_id, ts, latency_ms, arm, k, rerank, rewrite, model, "
                "tokens_prompt, tokens_completion, query_sha256_prefix, degraded, "
                "cost_usd, trace_id, cache_hit, feedback"
                ") VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (
                    row.request_id,
                    row.latency_ms,
                    row.arm,
                    row.k,
                    1 if row.rerank else 0,
                    1 if row.rewrite else 0,
                    row.model,
                    row.tokens_prompt,
                    row.tokens_completion,
                    row.query_sha256_prefix,
                    1 if row.degraded else 0,
                    row.cost_usd,
                    row.trace_id,
                    1 if row.cache_hit else 0,
                ),
            )
            conn.commit()
    except Exception:
        return


def sqlite_log_answer(request_id: str, question: str, answer: str) -> None:
    """Best-effort `answer_log` write — the one place a question's PLAINTEXT
    is ever persisted (specs/monitoring.md's "Online judge" section).

    Callers gate this on `HOMELIB_LOG_ANSWERS=1` (default off); this function
    itself has no opinion on the flag, matching `sqlite_log_query`'s
    never-raise contract so an answer-log failure can never turn into a
    500 on `/v1/ask`.
    """
    try:
        with open_store() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO answer_log (request_id, question, answer, created_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                (request_id, question, answer),
            )
            conn.commit()
    except Exception:
        return


def sqlite_record_feedback(request_id: str, feedback: str, comment: str | None) -> bool:
    with open_store() as conn:
        cur = conn.execute(
            "UPDATE query_log SET feedback = ? WHERE request_id = ?",
            (feedback, request_id),
        )
        conn.commit()
        return cur.rowcount > 0


def query_sha_prefix(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
