"""SQLite store: migrations, minimal seed, principal isolation (WP02).

Additive to v1 Postgres compose. No FTS5, no paid-tier tables, no 18/729/9168
ingest (WP03). Seed uses v1 `data/manifest.yaml` + `data/catalog.jsonl` heads.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

import yaml

LOCAL_USER_ID: Final = "local-user"
_SEED_BOOKS: Final = 2
_SEED_CATALOG: Final = 2
DEMO_SESSION_TTL_HOURS: Final = 24

_RIGHTS_STATUSES: Final = frozenset(
    {
        "public_domain",
        "licensed_bundle",
        "metadata_only",
        "unknown",
        "forbidden",
    }
)

class PrincipalRequired(Exception):
    """A private write was attempted without a principal."""


class UnknownPrincipal(Exception):
    """A private write referenced a principal that does not exist."""


class DemoSessionExpired(Exception):
    """Demo session TTL elapsed."""


@dataclass(frozen=True, slots=True)
class DemoSession:
    id: str
    principal_id: str
    reset_generation: int


def _now() -> datetime:
    return datetime.now(UTC)


def _now_iso() -> str:
    return _now().isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def rights_status_from_manifest(entry: dict[str, Any]) -> str:
    """Resolve manifest rights — explicit `rights_status` only; else fail closed."""
    explicit = entry.get("rights_status")
    if isinstance(explicit, str) and explicit in _RIGHTS_STATUSES:
        return explicit
    return "unknown"


_SQL_V1 = """
CREATE TABLE demo_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    reset_generation INTEGER NOT NULL DEFAULT 0
);
INSERT INTO demo_state (singleton, reset_generation) VALUES (1, 0);

CREATE TABLE principal (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('demo_session', 'local_user')),
    created_at TEXT NOT NULL
);

CREATE TABLE demo_session (
    id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES principal(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    reset_generation INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE books (
    book_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '[]',
    language TEXT NOT NULL DEFAULT 'en',
    source_url TEXT NOT NULL DEFAULT '',
    license_note TEXT NOT NULL DEFAULT '',
    rights_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (rights_status IN (
            'public_domain', 'licensed_bundle', 'metadata_only', 'unknown', 'forbidden'
        ))
);

CREATE TABLE catalog (
    ol_key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '[]',
    subjects TEXT NOT NULL DEFAULT '[]',
    first_publish_year INTEGER,
    description TEXT,
    provenance_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE playlist (
    id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES principal(id) ON DELETE CASCADE,
    last_opened_item_id TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE playlist_item (
    id TEXT PRIMARY KEY,
    playlist_id TEXT NOT NULL REFERENCES playlist(id) ON DELETE CASCADE,
    resource_id TEXT NOT NULL,
    book_id TEXT,
    ordinal INTEGER NOT NULL,
    origin TEXT NOT NULL,
    status TEXT NOT NULL,
    accepted_at TEXT,
    manual INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE read_progress (
    principal_id TEXT NOT NULL REFERENCES principal(id) ON DELETE CASCADE,
    resource_id TEXT NOT NULL,
    book_id TEXT,
    block_id TEXT,
    char_offset INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, resource_id)
);

CREATE TABLE query_log (
    request_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    arm TEXT NOT NULL,
    k INTEGER NOT NULL,
    rerank INTEGER NOT NULL DEFAULT 0,
    rewrite INTEGER NOT NULL DEFAULT 0,
    model TEXT NOT NULL DEFAULT '',
    tokens_prompt INTEGER NOT NULL DEFAULT 0,
    tokens_completion INTEGER NOT NULL DEFAULT 0,
    query_sha256_prefix TEXT NOT NULL,
    degraded INTEGER NOT NULL DEFAULT 0,
    feedback TEXT,
    principal_id TEXT REFERENCES principal(id) ON DELETE SET NULL
);

CREATE TABLE conversation (
    id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES principal(id) ON DELETE CASCADE,
    wing_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE feedback (
    request_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES principal(id) ON DELETE CASCADE,
    vote TEXT NOT NULL,
    comment TEXT
);
"""

_SQL_V2 = """
CREATE TABLE listen_progress (
    principal_id TEXT NOT NULL REFERENCES principal(id) ON DELETE CASCADE,
    resource_id TEXT NOT NULL,
    book_id TEXT,
    block_id TEXT,
    char_offset INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, resource_id)
);

CREATE TABLE areas (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    copy TEXT,
    principal_id TEXT REFERENCES principal(id) ON DELETE CASCADE
);

CREATE TABLE wings (
    id TEXT PRIMARY KEY,
    area_id TEXT NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'topic',
    copy TEXT,
    principal_id TEXT REFERENCES principal(id) ON DELETE CASCADE
);

CREATE TABLE bookmarks (
    id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES principal(id) ON DELETE CASCADE,
    resource_id TEXT NOT NULL,
    book_id TEXT,
    block_id TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);
"""

MIGRATIONS: Final[tuple[tuple[int, str], ...]] = ((1, _SQL_V1), (2, _SQL_V2))


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _run_sql_script(conn: sqlite3.Connection, sql: str) -> None:
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    for statement in statements:
        conn.execute(statement)


def migrate(conn: sqlite3.Connection, target_version: int | None = None) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {int(row[0]) for row in conn.execute("SELECT version FROM schema_migrations")}
    latest = max(version for version, _ in MIGRATIONS)
    target = latest if target_version is None else target_version
    if target < 1 or target > latest:
        raise ValueError(f"target_version must be 1..{latest}, got {target}")
    for version, sql in MIGRATIONS:
        if version > target or version in applied:
            continue
        conn.execute("BEGIN")
        try:
            _run_sql_script(conn, sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, _now_iso()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _require_principal(principal_id: str | None) -> str:
    if principal_id is None or not principal_id.strip():
        raise PrincipalRequired("private write requires a non-null principal")
    return principal_id


def _current_reset_generation(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT reset_generation FROM demo_state WHERE singleton = 1").fetchone()
    if row is None:
        raise RuntimeError("demo_state singleton missing")
    return int(row[0])


def _enforce_active_demo_session(conn: sqlite3.Connection, principal_id: str) -> None:
    row = conn.execute(
        "SELECT ds.expires_at FROM demo_session ds "
        "JOIN principal p ON p.id = ds.principal_id "
        "WHERE ds.principal_id = ? AND p.kind = 'demo_session'",
        (principal_id,),
    ).fetchone()
    if row is None:
        return
    expires_at = datetime.fromisoformat(str(row[0]))
    if expires_at <= _now():
        raise DemoSessionExpired(f"demo session expired at {expires_at.isoformat()}")


def _require_write_principal(conn: sqlite3.Connection, principal_id: str | None) -> str:
    owner = _require_principal(principal_id)
    row = conn.execute("SELECT 1 FROM principal WHERE id = ?", (owner,)).fetchone()
    if row is None:
        raise UnknownPrincipal(f"unknown principal: {owner}")
    _enforce_active_demo_session(conn, owner)
    return owner


def _ensure_local_user(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO principal (id, kind, created_at) VALUES (?, 'local_user', ?)",
        (LOCAL_USER_ID, _now_iso()),
    )


def seed(conn: sqlite3.Connection, *, repo_root: Path) -> None:
    _ensure_local_user(conn)
    manifest_path = repo_root / "data" / "manifest.yaml"
    catalog_path = repo_root / "data" / "catalog.jsonl"
    books = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(books, list):
        raise TypeError(f"manifest.yaml must be a list, got {type(books)!r}")
    for raw_entry in books[:_SEED_BOOKS]:
        if not isinstance(raw_entry, dict):
            raise TypeError("manifest entries must be mappings")
        entry: dict[str, Any] = raw_entry
        rights_status = rights_status_from_manifest(entry)
        conn.execute(
            "INSERT OR IGNORE INTO books "
            "(book_id, title, authors, language, source_url, license_note, rights_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entry["book_id"],
                entry["title"],
                json.dumps(list(entry.get("authors") or [])),
                entry.get("language") or "en",
                entry.get("source_url") or "",
                entry.get("license_note") or "",
                rights_status,
            ),
        )
    loaded = 0
    with catalog_path.open(encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            record = json.loads(raw)
            if "ol_key" not in record:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO catalog "
                "(ol_key, title, authors, subjects, first_publish_year, "
                "description, provenance_note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record["ol_key"],
                    record["title"],
                    json.dumps(list(record.get("authors") or [])),
                    json.dumps(list(record.get("subjects") or [])),
                    record.get("first_publish_year"),
                    record.get("description"),
                    record.get("provenance_note") or "",
                ),
            )
            loaded += 1
            if loaded >= _SEED_CATALOG:
                break
    if _table_exists(conn, "areas"):
        conn.execute(
            "INSERT OR IGNORE INTO areas (id, name, copy, principal_id) "
            "VALUES ('area-seed', 'Ideas in Common', 'Seed area', NULL)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO wings (id, area_id, name, kind, copy, principal_id) "
            "VALUES ('wing-seed', 'area-seed', 'Surprise Me', 'hidden', 'Seed wing', NULL)"
        )
    conn.commit()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    count_sql = {
        "books": "SELECT COUNT(*) FROM books",
        "catalog": "SELECT COUNT(*) FROM catalog",
        "playlist": "SELECT COUNT(*) FROM playlist",
        "playlist_item": "SELECT COUNT(*) FROM playlist_item",
        "read_progress": "SELECT COUNT(*) FROM read_progress",
        "demo_session": "SELECT COUNT(*) FROM demo_session",
        "principal": "SELECT COUNT(*) FROM principal",
        "areas": "SELECT COUNT(*) FROM areas",
        "wings": "SELECT COUNT(*) FROM wings",
        "conversation": "SELECT COUNT(*) FROM conversation",
        "feedback": "SELECT COUNT(*) FROM feedback",
        "bookmarks": "SELECT COUNT(*) FROM bookmarks",
    }
    for name, sql in count_sql.items():
        if not _table_exists(conn, name):
            counts[name] = 0
            continue
        counts[name] = int(conn.execute(sql).fetchone()[0])
    return counts


def logical_checksum(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    seed_sql = {
        "books": "SELECT * FROM books ORDER BY book_id",
        "catalog": "SELECT * FROM catalog ORDER BY ol_key",
        "areas": "SELECT * FROM areas ORDER BY id",
        "wings": "SELECT * FROM wings ORDER BY id",
    }
    for table, sql in seed_sql.items():
        if not _table_exists(conn, table):
            continue
        rows = conn.execute(sql).fetchall()
        for row in rows:
            digest.update(json.dumps(dict(row), sort_keys=True, default=str).encode())
    return digest.hexdigest()


def create_demo_session(conn: sqlite3.Connection) -> DemoSession:
    principal_id = _new_id()
    session_id = _new_id()
    created = _now()
    expires = created + timedelta(hours=DEMO_SESSION_TTL_HOURS)
    generation = _current_reset_generation(conn)
    with conn:
        conn.execute(
            "INSERT INTO principal (id, kind, created_at) VALUES (?, 'demo_session', ?)",
            (principal_id, created.isoformat()),
        )
        conn.execute(
            "INSERT INTO demo_session (id, principal_id, created_at, expires_at, reset_generation) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                principal_id,
                created.isoformat(),
                expires.isoformat(),
                generation,
            ),
        )
    return DemoSession(id=session_id, principal_id=principal_id, reset_generation=generation)


def _current_playlist_id(conn: sqlite3.Connection, principal_id: str) -> str:
    row = conn.execute("SELECT id FROM playlist WHERE principal_id = ?", (principal_id,)).fetchone()
    if row is not None:
        return str(row[0])
    playlist_id = _new_id()
    conn.execute(
        "INSERT INTO playlist (id, principal_id, updated_at) VALUES (?, ?, ?)",
        (playlist_id, principal_id, _now_iso()),
    )
    return playlist_id


def insert_playlist(
    conn: sqlite3.Connection,
    *,
    principal_id: str | None,
    resource_id: str,
    book_id: str | None = None,
) -> str:
    owner = _require_write_principal(conn, principal_id)
    playlist_id = _current_playlist_id(conn, owner)
    item_id = _new_id()
    ordinal_row = conn.execute(
        "SELECT COALESCE(MAX(ordinal), -1) + 1 FROM playlist_item WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchone()
    ordinal = int(ordinal_row[0]) if ordinal_row is not None else 0
    with conn:
        conn.execute(
            "INSERT INTO playlist_item "
            "(id, playlist_id, resource_id, book_id, ordinal, origin, status, accepted_at, manual) "
            "VALUES (?, ?, ?, ?, ?, 'manual_shelf', 'queued', ?, 1)",
            (item_id, playlist_id, resource_id, book_id, ordinal, _now_iso()),
        )
        conn.execute(
            "UPDATE playlist SET updated_at = ? WHERE id = ?",
            (_now_iso(), playlist_id),
        )
    return item_id


def insert_read_progress(
    conn: sqlite3.Connection,
    *,
    principal_id: str | None,
    resource_id: str,
    char_offset: int,
    block_id: str | None = None,
    book_id: str | None = None,
) -> None:
    owner = _require_write_principal(conn, principal_id)
    with conn:
        conn.execute(
            "INSERT INTO read_progress "
            "(principal_id, resource_id, book_id, block_id, char_offset, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (principal_id, resource_id) DO UPDATE SET "
            "char_offset = excluded.char_offset, updated_at = excluded.updated_at, "
            "block_id = excluded.block_id, book_id = excluded.book_id",
            (owner, resource_id, book_id, block_id, char_offset, _now_iso()),
        )


def insert_conversation(
    conn: sqlite3.Connection,
    *,
    principal_id: str | None,
    wing_id: str | None = None,
) -> str:
    owner = _require_write_principal(conn, principal_id)
    conversation_id = _new_id()
    with conn:
        conn.execute(
            "INSERT INTO conversation (id, principal_id, wing_id, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, owner, wing_id, _now_iso()),
        )
    return conversation_id


def insert_feedback(
    conn: sqlite3.Connection,
    *,
    principal_id: str | None,
    request_id: str,
    vote: str,
    comment: str | None = None,
) -> None:
    owner = _require_write_principal(conn, principal_id)
    with conn:
        conn.execute(
            "INSERT INTO feedback (request_id, principal_id, vote, comment) VALUES (?, ?, ?, ?)",
            (request_id, owner, vote, comment),
        )


def insert_area(
    conn: sqlite3.Connection,
    *,
    principal_id: str | None,
    name: str,
    copy: str | None = None,
) -> str:
    owner = _require_write_principal(conn, principal_id)
    area_id = _new_id()
    with conn:
        conn.execute(
            "INSERT INTO areas (id, name, copy, principal_id) VALUES (?, ?, ?, ?)",
            (area_id, name, copy, owner),
        )
    return area_id


def insert_bookmark(
    conn: sqlite3.Connection,
    *,
    principal_id: str | None,
    resource_id: str,
    block_id: str,
    char_start: int,
    char_end: int,
    book_id: str | None = None,
    note: str | None = None,
) -> str:
    owner = _require_write_principal(conn, principal_id)
    bookmark_id = _new_id()
    with conn:
        conn.execute(
            "INSERT INTO bookmarks "
            "(id, principal_id, resource_id, book_id, block_id, char_start, char_end, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                bookmark_id,
                owner,
                resource_id,
                book_id,
                block_id,
                char_start,
                char_end,
                note,
                _now_iso(),
            ),
        )
    return bookmark_id


def list_bookmarks(conn: sqlite3.Connection, principal_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, resource_id, book_id, block_id, char_start, char_end, note "
        "FROM bookmarks WHERE principal_id = ? ORDER BY created_at",
        (principal_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_playlist_items(conn: sqlite3.Connection, principal_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT i.id, i.playlist_id, i.resource_id, i.book_id, i.ordinal, i.status "
        "FROM playlist_item i JOIN playlist p ON p.id = i.playlist_id "
        "WHERE p.principal_id = ? AND i.status != 'removed' "
        "ORDER BY i.ordinal",
        (principal_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_read_progress(conn: sqlite3.Connection, principal_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT principal_id, resource_id, book_id, char_offset, block_id "
        "FROM read_progress WHERE principal_id = ?",
        (principal_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_conversations(conn: sqlite3.Connection, principal_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, principal_id, wing_id, created_at FROM conversation WHERE principal_id = ?",
        (principal_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_areas(conn: sqlite3.Connection, principal_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, copy, principal_id FROM areas "
        "WHERE principal_id = ? OR principal_id IS NULL",
        (principal_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def reset_demo(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            "UPDATE demo_state SET reset_generation = reset_generation + 1 WHERE singleton = 1"
        )
        conn.execute("DELETE FROM principal WHERE kind = 'demo_session'")


def books_default_rights_status(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT dflt_value FROM pragma_table_info('books') WHERE name = 'rights_status'"
    ).fetchone()
    return str(row[0]) if row is not None else ""
