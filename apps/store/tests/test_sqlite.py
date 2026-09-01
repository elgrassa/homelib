"""Red tests for WP02 SQLite store — must fail until apps.store is implemented.

Exact names from docs/plan-v2.md WP02. Minimal seed (principals, catalog/book
rows), not the 18/729/9168 ingest pipeline (WP03).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apps.store.sqlite import (
    DEMO_SESSION_TTL_HOURS,
    PAID_TIER_TABLES,
    DemoSessionExpired,
    PrincipalRequired,
    books_default_rights_status,
    connect,
    create_demo_session,
    insert_area,
    insert_conversation,
    insert_feedback,
    insert_playlist,
    insert_read_progress,
    list_areas,
    list_conversations,
    list_playlist_items,
    list_read_progress,
    logical_checksum,
    migrate,
    reset_demo,
    row_counts,
    seed,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _fresh(tmp_path: Path) -> Path:
    return tmp_path / "homelib.sqlite"


def _first_book(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT book_id FROM books ORDER BY book_id LIMIT 1").fetchone()
    assert row is not None
    return str(row[0])


def test_fresh_migration_then_upgrade(tmp_path: Path) -> None:
    path = _fresh(tmp_path)
    conn = connect(path)
    migrate(conn, target_version=1)
    versions = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    assert versions == {1}
    conn.execute(
        "INSERT INTO principal (id, kind, created_at) VALUES ('local-user', 'local_user', 't')"
    )
    conn.execute("INSERT INTO books (book_id, title) VALUES ('keep-me', 'Kept Across Upgrade')")
    conn.commit()

    migrate(conn, target_version=None)
    versions = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    assert versions == {1, 2}
    title = conn.execute("SELECT title FROM books WHERE book_id = 'keep-me'").fetchone()
    assert title is not None and title[0] == "Kept Across Upgrade"
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "listen_progress" in tables
    assert "areas" in tables
    assert "bookmarks" in tables
    assert tables.isdisjoint(PAID_TIER_TABLES)
    with pytest.raises(ValueError, match="target_version"):
        migrate(conn, target_version=0)
    conn.close()


def test_fk_enforced(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO playlist (id, principal_id, updated_at) VALUES ('p1', 'no-such', 't')"
        )
    conn.close()


def test_seed_rerun_zero_new_rows(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    reset_demo(conn)
    first = row_counts(conn)
    checksum = logical_checksum(conn)
    seed(conn, repo_root=REPO_ROOT)
    assert row_counts(conn) == first
    assert logical_checksum(conn) == checksum
    conn.close()


def test_restart_persists(tmp_path: Path) -> None:
    path = _fresh(tmp_path)
    conn = connect(path)
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    book_id = _first_book(conn)
    insert_playlist(conn, principal_id="local-user", resource_id=book_id, book_id=book_id)
    insert_read_progress(
        conn, principal_id="local-user", resource_id=book_id, book_id=book_id, char_offset=42
    )
    conn.commit()
    conn.close()

    again = connect(path)
    items = list_playlist_items(again, "local-user")
    assert [item["resource_id"] for item in items] == [book_id]
    assert items[0]["book_id"] == book_id
    progress = list_read_progress(again, "local-user")
    assert progress[0]["char_offset"] == 42
    again.close()


def test_demo_reset_restores_seed(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    before = row_counts(conn)
    checksum = logical_checksum(conn)
    session = create_demo_session(conn)
    book_id = _first_book(conn)
    insert_playlist(conn, principal_id=session.principal_id, resource_id=book_id, book_id=book_id)
    insert_read_progress(
        conn, principal_id=session.principal_id, resource_id=book_id, char_offset=7
    )
    insert_conversation(conn, principal_id=session.principal_id)
    conn.commit()
    assert row_counts(conn)["playlist"] >= before["playlist"] + 1
    assert row_counts(conn)["conversation"] >= before["conversation"] + 1

    reset_demo(conn)
    after = row_counts(conn)
    assert after["books"] == before["books"]
    assert after["catalog"] == before["catalog"]
    assert after["areas"] == before["areas"]
    assert after["wings"] == before["wings"]
    assert after["playlist"] == before["playlist"]
    assert after["playlist_item"] == before["playlist_item"]
    assert after["read_progress"] == before["read_progress"]
    assert after["conversation"] == before["conversation"]
    assert after["demo_session"] == 0
    assert logical_checksum(conn) == checksum

    conn.execute("UPDATE books SET title = 'CORRUPTED' WHERE book_id = ?", (book_id,))
    assert logical_checksum(conn) != checksum
    conn.close()


def test_private_write_requires_principal(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    with pytest.raises(PrincipalRequired):
        insert_playlist(conn, principal_id=None, resource_id="x")
    with pytest.raises(PrincipalRequired):
        insert_read_progress(conn, principal_id=None, resource_id="x", char_offset=1)
    with pytest.raises(PrincipalRequired):
        insert_conversation(conn, principal_id=None)
    with pytest.raises(PrincipalRequired):
        insert_feedback(conn, principal_id=None, request_id="r1", vote="up")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO playlist (id, principal_id, updated_at) VALUES ('p1', NULL, 't')")
    conn.close()


def test_demo_sessions_cannot_read_each_other(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    a = create_demo_session(conn)
    b = create_demo_session(conn)
    book_id = _first_book(conn)
    insert_playlist(conn, principal_id=a.principal_id, resource_id=book_id, book_id=book_id)
    insert_read_progress(conn, principal_id=a.principal_id, resource_id=book_id, char_offset=11)
    insert_conversation(conn, principal_id=a.principal_id)
    insert_area(conn, principal_id=a.principal_id, name="Session A wing")
    conn.commit()
    assert list_playlist_items(conn, a.principal_id)
    assert list_read_progress(conn, a.principal_id)
    assert list_conversations(conn, a.principal_id)
    assert list_areas(conn, a.principal_id)
    assert list_playlist_items(conn, b.principal_id) == []
    assert list_read_progress(conn, b.principal_id) == []
    assert list_conversations(conn, b.principal_id) == []
    assert list_areas(conn, b.principal_id) == []
    conn.close()


def test_logical_checksum_stable_across_two_builds(tmp_path: Path) -> None:
    """SQLite files are not byte-reproducible; counts + checksum must be."""
    paths = [tmp_path / "a.sqlite", tmp_path / "b.sqlite"]
    checksums: list[str] = []
    counts: list[dict[str, int]] = []
    for path in paths:
        conn = connect(path)
        migrate(conn)
        seed(conn, repo_root=REPO_ROOT)
        checksums.append(logical_checksum(conn))
        counts.append(row_counts(conn))
        conn.close()
    assert checksums[0] == checksums[1]
    assert counts[0] == counts[1]

    conn = connect(paths[0])
    book_id = _first_book(conn)
    conn.execute("UPDATE books SET title = 'mutated' WHERE book_id = ?", (book_id,))
    assert logical_checksum(conn) != checksums[0]
    conn.close()


def test_unknown_rights_default_fail_closed(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    assert books_default_rights_status(conn) == "'unknown'"
    conn.execute("INSERT INTO books (book_id, title) VALUES ('no-rights', 'No Rights')")
    row = conn.execute("SELECT rights_status FROM books WHERE book_id = 'no-rights'").fetchone()
    assert row is not None and row[0] == "unknown"
    conn.close()


def test_seed_reads_rights_status_from_manifest(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    rows = conn.execute("SELECT rights_status FROM books").fetchall()
    assert rows
    assert all(str(row[0]) == "public_domain" for row in rows)
    conn.close()


def test_demo_session_ttl_and_reset_generation(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    session = create_demo_session(conn)
    row = conn.execute(
        "SELECT created_at, expires_at, reset_generation FROM demo_session WHERE id = ?",
        (session.id,),
    ).fetchone()
    assert row is not None
    created = datetime.fromisoformat(str(row[0]))
    expires = datetime.fromisoformat(str(row[1]))
    assert expires > created
    assert expires - created == timedelta(hours=DEMO_SESSION_TTL_HOURS)
    assert int(row[2]) == session.reset_generation == 0

    reset_demo(conn)
    generation = conn.execute(
        "SELECT reset_generation FROM demo_state WHERE singleton = 1"
    ).fetchone()
    assert generation is not None and int(generation[0]) == 1
    conn.close()


def test_expired_demo_session_write_is_refused(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    session = create_demo_session(conn)
    conn.execute(
        "UPDATE demo_session SET expires_at = ? WHERE id = ?",
        ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), session.id),
    )
    conn.commit()
    with pytest.raises(DemoSessionExpired):
        insert_playlist(conn, principal_id=session.principal_id, resource_id="x")
    conn.close()


def test_playlist_does_not_silently_copy_resource_id_to_book_id(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    book_id = _first_book(conn)
    insert_playlist(
        conn,
        principal_id="local-user",
        resource_id="discover-only-resource",
        book_id=book_id,
    )
    items = list_playlist_items(conn, "local-user")
    assert items[0]["resource_id"] == "discover-only-resource"
    assert items[0]["book_id"] == book_id
    conn.close()


def test_migration_is_transactional_on_failure(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    broken = ((3, "CREATE TABLE broken_v3 (id TEXT PRIMARY KEY); INVALID SQL;"),)
    original = __import__("apps.store.sqlite", fromlist=["MIGRATIONS"]).MIGRATIONS
    module = __import__("apps.store.sqlite", fromlist=["migrate"])
    try:
        module.MIGRATIONS = original + broken  # type: ignore[assignment]
        with pytest.raises(sqlite3.OperationalError):
            module.migrate(conn, target_version=3)
        versions = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        assert versions == {1, 2}
        assert not module._table_exists(conn, "broken_v3")
    finally:
        module.MIGRATIONS = original  # type: ignore[assignment]
    conn.close()
