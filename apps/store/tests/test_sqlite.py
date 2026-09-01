"""Red tests for WP02 SQLite store — must fail until apps.store is implemented.

Exact names from docs/plan-v2.md WP02. Minimal seed (principals, catalog/book
rows), not the 18/729/9168 ingest pipeline (WP03).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from apps.store.sqlite import (
    PAID_TIER_TABLES,
    PrincipalRequired,
    connect,
    create_demo_session,
    insert_playlist,
    insert_read_progress,
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
    insert_playlist(conn, principal_id="local-user", resource_id=book_id)
    insert_read_progress(conn, principal_id="local-user", resource_id=book_id, char_offset=42)
    conn.commit()
    conn.close()

    again = connect(path)
    items = list_playlist_items(again, "local-user")
    assert [item["resource_id"] for item in items] == [book_id]
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
    insert_playlist(conn, principal_id=session.principal_id, resource_id=book_id)
    insert_read_progress(
        conn, principal_id=session.principal_id, resource_id=book_id, char_offset=7
    )
    conn.commit()
    assert row_counts(conn)["playlist"] >= before["playlist"] + 1

    reset_demo(conn)
    after = row_counts(conn)
    assert after["books"] == before["books"]
    assert after["catalog"] == before["catalog"]
    assert after["playlist"] == before["playlist"]
    assert after["read_progress"] == before["read_progress"]
    assert after["demo_session"] == 0
    assert logical_checksum(conn) == checksum
    conn.close()


def test_private_write_requires_principal(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    with pytest.raises(PrincipalRequired):
        insert_playlist(conn, principal_id=None, resource_id="x")
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
    insert_playlist(conn, principal_id=a.principal_id, resource_id=book_id)
    conn.commit()
    assert list_playlist_items(conn, a.principal_id)
    assert list_playlist_items(conn, b.principal_id) == []
    assert list_read_progress(conn, b.principal_id) == []
    conn.close()


def test_logical_checksum_stable_across_two_builds(tmp_path: Path) -> None:
    """SQLite files are not byte-reproducible; counts + checksum must be."""
    paths = [tmp_path / "a.sqlite", tmp_path / "b.sqlite"]
    checksums: list[str] = []
    counts: list[dict[str, int]] = []
    file_hashes: list[int] = []
    for path in paths:
        conn = connect(path)
        migrate(conn)
        seed(conn, repo_root=REPO_ROOT)
        checksums.append(logical_checksum(conn))
        counts.append(row_counts(conn))
        conn.close()
        file_hashes.append(path.stat().st_size)
    assert checksums[0] == checksums[1]
    assert counts[0] == counts[1]
    # Do not require equal file bytes; only that we did not hash the file.
    assert checksums[0] != str(file_hashes[0])
