"""Read/listen progress — specs/progress.md (WP07)."""

from __future__ import annotations

import sqlite3
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from apps.store.sqlite import _now_iso, _require_write_principal

__all__ = ["ProgressEvent", "ProgressKind", "get_progress", "upsert_progress"]


class ProgressKind(StrEnum):
    READ = "read"
    LISTEN = "listen"


class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str
    kind: ProgressKind
    block_id: str | None = None
    char_offset: int | None = None
    book_id: str | None = None


_UPSERT_READ = (
    "INSERT INTO read_progress "
    "(principal_id, resource_id, book_id, block_id, char_offset, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (principal_id, resource_id) DO UPDATE SET "
    "char_offset = excluded.char_offset, updated_at = excluded.updated_at, "
    "block_id = excluded.block_id, book_id = excluded.book_id"
)
_UPSERT_LISTEN = (
    "INSERT INTO listen_progress "
    "(principal_id, resource_id, book_id, block_id, char_offset, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (principal_id, resource_id) DO UPDATE SET "
    "char_offset = excluded.char_offset, updated_at = excluded.updated_at, "
    "block_id = excluded.block_id, book_id = excluded.book_id"
)
_SELECT_READ = (
    "SELECT principal_id, resource_id, book_id, block_id, char_offset, updated_at "
    "FROM read_progress WHERE principal_id = ? AND resource_id = ?"
)
_SELECT_LISTEN = (
    "SELECT principal_id, resource_id, book_id, block_id, char_offset, updated_at "
    "FROM listen_progress WHERE principal_id = ? AND resource_id = ?"
)


def upsert_progress(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    event: ProgressEvent,
) -> None:
    owner = _require_write_principal(conn, principal_id)
    book = conn.execute(
        "SELECT book_id FROM books WHERE book_id = ?",
        (event.resource_id,),
    ).fetchone()
    if book is None:
        raise LookupError(event.resource_id)
    sql = _UPSERT_READ if event.kind is ProgressKind.READ else _UPSERT_LISTEN
    with conn:
        conn.execute(
            sql,
            (
                owner,
                event.resource_id,
                event.book_id or event.resource_id,
                event.block_id,
                event.char_offset,
                _now_iso(),
            ),
        )


def get_progress(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    resource_id: str,
    kind: ProgressKind,
) -> dict[str, object] | None:
    owner = _require_write_principal(conn, principal_id)
    sql = _SELECT_READ if kind is ProgressKind.READ else _SELECT_LISTEN
    row = conn.execute(sql, (owner, resource_id)).fetchone()
    if row is None:
        return None
    return {
        "principal_id": row[0],
        "resource_id": row[1],
        "book_id": row[2],
        "block_id": row[3],
        "char_offset": row[4],
        "updated_at": row[5],
    }
