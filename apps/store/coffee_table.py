"""Coffee Table playlist ops — product §5.6 / specs/coffee-table.md (WP07)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.store.sqlite import (
    _current_playlist_id,
    _new_id,
    _now_iso,
    _require_write_principal,
)

__all__ = [
    "Playlist",
    "PlaylistItem",
    "PlaylistOrigin",
    "PlaylistStatus",
    "accept_proposed",
    "add_item",
    "get_playlist",
    "patch_items",
    "propose_items",
    "remove_item",
    "set_last_opened",
]


class PlaylistOrigin(StrEnum):
    MENTOR_PROPOSAL = "mentor_proposal"
    MANUAL_SHELF = "manual_shelf"
    MANUAL_DISCOVER = "manual_discover"
    ROADMAP = "roadmap"


class PlaylistStatus(StrEnum):
    PROPOSED = "proposed"
    QUEUED = "queued"
    READING = "reading"
    LISTENING = "listening"
    PAUSED = "paused"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    REMOVED = "removed"


class PlaylistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    resource_id: str
    book_id: str | None = None
    ordinal: int
    origin: PlaylistOrigin
    status: PlaylistStatus
    accepted_at: datetime | None = None
    manual: bool = False


class Playlist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    principal_id: str
    items: list[PlaylistItem] = Field(default_factory=list)
    last_opened_item_id: str | None = None
    updated_at: datetime


def _parse_ts(raw: str | None) -> datetime | None:
    if raw is None or raw == "":
        return None
    return datetime.fromisoformat(raw)


def _row_to_item(row: sqlite3.Row | tuple[Any, ...]) -> PlaylistItem:
    data = (
        dict(row)
        if isinstance(row, sqlite3.Row)
        else {
            "id": row[0],
            "resource_id": row[1],
            "book_id": row[2],
            "ordinal": row[3],
            "origin": row[4],
            "status": row[5],
            "accepted_at": row[6],
            "manual": row[7],
        }
    )
    return PlaylistItem(
        id=str(data["id"]),
        resource_id=str(data["resource_id"]),
        book_id=str(data["book_id"]) if data["book_id"] is not None else None,
        ordinal=int(data["ordinal"]),
        origin=PlaylistOrigin(str(data["origin"])),
        status=PlaylistStatus(str(data["status"])),
        accepted_at=_parse_ts(str(data["accepted_at"]) if data["accepted_at"] else None),
        manual=bool(int(data["manual"])),
    )


def get_playlist(
    conn: sqlite3.Connection,
    principal_id: str,
    *,
    include_removed: bool = False,
) -> Playlist:
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    meta = conn.execute(
        "SELECT id, principal_id, last_opened_item_id, updated_at FROM playlist WHERE id = ?",
        (playlist_id,),
    ).fetchone()
    assert meta is not None
    if include_removed:
        rows = conn.execute(
            "SELECT id, resource_id, book_id, ordinal, origin, status, accepted_at, manual "
            "FROM playlist_item WHERE playlist_id = ? ORDER BY ordinal ASC",
            (playlist_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, resource_id, book_id, ordinal, origin, status, accepted_at, manual "
            "FROM playlist_item WHERE playlist_id = ? AND status != 'removed' "
            "ORDER BY ordinal ASC",
            (playlist_id,),
        ).fetchall()
    return Playlist(
        id=str(meta[0]),
        principal_id=str(meta[1]),
        items=[_row_to_item(r) for r in rows],
        last_opened_item_id=str(meta[2]) if meta[2] is not None else None,
        updated_at=datetime.fromisoformat(str(meta[3])),
    )


def propose_items(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    resource_ids: list[str],
    origin: PlaylistOrigin = PlaylistOrigin.MENTOR_PROPOSAL,
) -> Playlist:
    """Insert AI proposals as `proposed`. Skips completed/removed resources (no silent reinsert)."""
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    blocked = {
        str(r[0])
        for r in conn.execute(
            "SELECT resource_id FROM playlist_item "
            "WHERE playlist_id = ? AND status IN ('completed', 'removed')",
            (playlist_id,),
        ).fetchall()
    }
    with conn:
        for resource_id in resource_ids:
            if resource_id in blocked:
                continue
            existing = conn.execute(
                "SELECT id FROM playlist_item WHERE playlist_id = ? AND resource_id = ? "
                "AND status NOT IN ('removed')",
                (playlist_id, resource_id),
            ).fetchone()
            if existing is not None:
                continue
            ordinal_row = conn.execute(
                "SELECT COALESCE(MAX(ordinal), -1) + 1 FROM playlist_item WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            ordinal = int(ordinal_row[0]) if ordinal_row else 0
            conn.execute(
                "INSERT INTO playlist_item ("
                "id, playlist_id, resource_id, book_id, ordinal, origin, "
                "status, accepted_at, manual"
                ") VALUES (?, ?, ?, ?, ?, ?, 'proposed', NULL, 0)",
                (_new_id(), playlist_id, resource_id, resource_id, ordinal, origin.value),
            )
        conn.execute(
            "UPDATE playlist SET updated_at = ? WHERE id = ?",
            (_now_iso(), playlist_id),
        )
    return get_playlist(conn, owner)


def accept_proposed(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    accept_item_ids: list[str] | None = None,
) -> Playlist:
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    if accept_item_ids is None:
        rows = conn.execute(
            "SELECT id FROM playlist_item WHERE playlist_id = ? AND status = 'proposed'",
            (playlist_id,),
        ).fetchall()
        ids = [str(r[0]) for r in rows]
    else:
        ids = list(accept_item_ids)
        for item_id in ids:
            row = conn.execute(
                "SELECT id FROM playlist_item WHERE id = ? AND playlist_id = ?",
                (item_id, playlist_id),
            ).fetchone()
            if row is None:
                raise LookupError(item_id)
    now = _now_iso()
    with conn:
        for item_id in ids:
            conn.execute(
                "UPDATE playlist_item SET status = 'queued', accepted_at = ? "
                "WHERE id = ? AND playlist_id = ? AND status = 'proposed'",
                (now, item_id, playlist_id),
            )
        conn.execute(
            "UPDATE playlist SET updated_at = ? WHERE id = ?",
            (now, playlist_id),
        )
    return get_playlist(conn, owner)


def add_item(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    resource_id: str,
    origin: PlaylistOrigin,
    book_id: str | None = None,
) -> Playlist:
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    manual = origin in (PlaylistOrigin.MANUAL_SHELF, PlaylistOrigin.MANUAL_DISCOVER)
    status = PlaylistStatus.QUEUED if manual else PlaylistStatus.PROPOSED
    accepted = _now_iso() if manual else None
    ordinal_row = conn.execute(
        "SELECT COALESCE(MAX(ordinal), -1) + 1 FROM playlist_item WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchone()
    ordinal = int(ordinal_row[0]) if ordinal_row else 0
    with conn:
        conn.execute(
            "INSERT INTO playlist_item "
            "(id, playlist_id, resource_id, book_id, ordinal, origin, status, accepted_at, manual) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _new_id(),
                playlist_id,
                resource_id,
                book_id,
                ordinal,
                origin.value,
                status.value,
                accepted,
                1 if manual else 0,
            ),
        )
        conn.execute(
            "UPDATE playlist SET updated_at = ? WHERE id = ?",
            (_now_iso(), playlist_id),
        )
    return get_playlist(conn, owner)


def patch_items(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    updates: list[dict[str, Any]],
) -> Playlist:
    """Apply ordinal/status patches. Duplicate/gap ordinals → ValueError (422)."""
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    ordinals: list[int] = []
    for upd in updates:
        item_id = str(upd["id"])
        row = conn.execute(
            "SELECT id FROM playlist_item WHERE id = ? AND playlist_id = ?",
            (item_id, playlist_id),
        ).fetchone()
        if row is None:
            raise LookupError(item_id)
        if upd.get("ordinal") is not None:
            ordinals.append(int(upd["ordinal"]))
    if ordinals:
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("duplicate ordinals")
        if sorted(ordinals) != list(range(min(ordinals), min(ordinals) + len(ordinals))):
            # Allow partial patch of subset only if dense among themselves starting at any base;
            # still reject gaps inside the provided set.
            expected = list(range(min(ordinals), max(ordinals) + 1))
            if sorted(ordinals) != expected:
                raise ValueError("gapped ordinals")
    with conn:
        for upd in updates:
            item_id = str(upd["id"])
            if upd.get("status") is not None:
                conn.execute(
                    "UPDATE playlist_item SET status = ? WHERE id = ? AND playlist_id = ?",
                    (str(upd["status"]), item_id, playlist_id),
                )
            if upd.get("ordinal") is not None:
                conn.execute(
                    "UPDATE playlist_item SET ordinal = ? WHERE id = ? AND playlist_id = ?",
                    (int(upd["ordinal"]), item_id, playlist_id),
                )
        conn.execute(
            "UPDATE playlist SET updated_at = ? WHERE id = ?",
            (_now_iso(), playlist_id),
        )
    return get_playlist(conn, owner)


def remove_item(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    item_id: str,
) -> Playlist:
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    row = conn.execute(
        "SELECT id FROM playlist_item WHERE id = ? AND playlist_id = ?",
        (item_id, playlist_id),
    ).fetchone()
    if row is None:
        raise LookupError(item_id)
    with conn:
        conn.execute(
            "UPDATE playlist_item SET status = 'removed' WHERE id = ? AND playlist_id = ?",
            (item_id, playlist_id),
        )
        conn.execute(
            "UPDATE playlist SET updated_at = ? WHERE id = ?",
            (_now_iso(), playlist_id),
        )
    return get_playlist(conn, owner)


def set_last_opened(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    item_id: str,
) -> Playlist:
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    with conn:
        conn.execute(
            "UPDATE playlist SET last_opened_item_id = ?, updated_at = ? WHERE id = ?",
            (item_id, _now_iso(), playlist_id),
        )
    return get_playlist(conn, owner)


def regenerate_proposals(
    conn: sqlite3.Connection,
    *,
    principal_id: str,
    resource_ids: list[str],
) -> Playlist:
    """Mentor regen: drop only non-manual `proposed` rows; never touch manual/active."""
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    with conn:
        conn.execute(
            "DELETE FROM playlist_item "
            "WHERE playlist_id = ? AND status = 'proposed' AND manual = 0",
            (playlist_id,),
        )
    return propose_items(conn, principal_id=owner, resource_ids=resource_ids)
