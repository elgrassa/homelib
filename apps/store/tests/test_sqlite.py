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
    DemoSessionExpired,
    PrincipalRequired,
    UnknownPrincipal,
    books_default_rights_status,
    connect,
    create_demo_session,
    insert_area,
    insert_bookmark,
    insert_conversation,
    insert_feedback,
    insert_playlist,
    insert_read_progress,
    list_areas,
    list_bookmarks,
    list_conversations,
    list_playlist_items,
    list_read_progress,
    logical_checksum,
    migrate,
    reset_demo,
    rights_status_from_manifest,
    row_counts,
    seed,
)

PAID_TIER_TABLES = frozenset(
    {
        "household_profile",
        "household_profiles",
        "licence_entitlement",
        "license_entitlement",
        "commercial_licence",
        "silver_memory",
        "audio_generation_job",
        "obsidian_sync",
        "apple_device",
    }
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
    # migrate ensures the well-known selfhosted principal (Coffee Table / playlists).
    local = conn.execute("SELECT kind FROM principal WHERE id = 'local-user'").fetchone()
    assert local is not None and local[0] == "local_user"
    conn.execute("INSERT INTO books (book_id, title) VALUES ('keep-me', 'Kept Across Upgrade')")
    conn.commit()

    migrate(conn, target_version=None)
    versions = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    assert versions == {1, 2, 3, 4, 5, 6}
    title = conn.execute("SELECT title FROM books WHERE book_id = 'keep-me'").fetchone()
    assert title is not None and title[0] == "Kept Across Upgrade"
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "listen_progress" in tables
    assert "areas" in tables
    assert "bookmarks" in tables
    assert "blocks" in tables
    assert "chunks" in tables
    assert "chunk_embeddings" in tables
    assert "chunks_fts" in tables
    assert "index_state" in tables
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
    insert_bookmark(
        conn,
        principal_id=a.principal_id,
        resource_id=book_id,
        block_id=f"{book_id}-b0",
        char_start=0,
        char_end=5,
        book_id=book_id,
    )
    conn.commit()
    a_areas = list_areas(conn, a.principal_id)
    assert any(area["name"] == "Session A wing" for area in a_areas)
    assert any(area["id"] == "area-seed" for area in a_areas)
    assert list_playlist_items(conn, a.principal_id)
    assert list_read_progress(conn, a.principal_id)
    assert list_conversations(conn, a.principal_id)
    assert list_bookmarks(conn, a.principal_id)
    assert list_playlist_items(conn, b.principal_id) == []
    assert list_read_progress(conn, b.principal_id) == []
    assert list_conversations(conn, b.principal_id) == []
    assert list_bookmarks(conn, b.principal_id) == []
    b_areas = list_areas(conn, b.principal_id)
    assert any(area["id"] == "area-seed" for area in b_areas)
    assert not any(area["name"] == "Session A wing" for area in b_areas)
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


def test_can_index_text_allows_only_bundle_and_public_domain() -> None:
    from apps.store.sqlite import can_index_text

    assert can_index_text("public_domain")
    assert can_index_text("licensed_bundle")
    assert not can_index_text("unknown")
    assert not can_index_text("metadata_only")
    assert not can_index_text("forbidden")


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


def test_rights_status_requires_explicit_manifest_field() -> None:
    entry = {
        "book_id": "note-only",
        "license_note": "Public domain (US) — Project Gutenberg",
    }
    assert rights_status_from_manifest(entry) == "unknown"


def test_unknown_principal_write_is_refused(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    with pytest.raises(UnknownPrincipal):
        insert_playlist(conn, principal_id="no-such-principal", resource_id="x")
    conn.close()


def test_failed_write_leaves_no_partial_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import apps.store.sqlite as sqlite_mod

    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    book_id = _first_book(conn)
    before_playlist = int(conn.execute("SELECT COUNT(*) FROM playlist").fetchone()[0])
    before_items = int(conn.execute("SELECT COUNT(*) FROM playlist_item").fetchone()[0])
    real_now = sqlite_mod._now_iso
    calls = {"count": 0}

    def flaky_now_iso() -> str:
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("simulated failure mid-write")
        return real_now()

    monkeypatch.setattr(sqlite_mod, "_now_iso", flaky_now_iso)
    with pytest.raises(RuntimeError, match="simulated failure"):
        insert_playlist(conn, principal_id="local-user", resource_id=book_id, book_id=book_id)
    after_playlist = int(conn.execute("SELECT COUNT(*) FROM playlist").fetchone()[0])
    after_items = int(conn.execute("SELECT COUNT(*) FROM playlist_item").fetchone()[0])
    assert after_playlist == before_playlist
    assert after_items == before_items
    conn.close()


def test_migration_is_transactional_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import apps.store.sqlite as sqlite_mod

    conn = connect(_fresh(tmp_path))
    migrate(conn)
    original = sqlite_mod.MIGRATIONS
    # Computed rather than hardcoded: a version number that collides with a
    # real migration is silently skipped as "already applied" instead of
    # ever running, which would make this test pass for the wrong reason as
    # soon as a later commit's migration reused that number.
    baseline_versions = {version for version, _ in original}
    broken_version = max(baseline_versions) + 1
    broken = ((broken_version, "CREATE TABLE broken_vN (id TEXT PRIMARY KEY); INVALID SQL;"),)
    try:
        monkeypatch.setattr(sqlite_mod, "MIGRATIONS", original + broken)
        with pytest.raises(sqlite3.OperationalError):
            sqlite_mod.migrate(conn, target_version=broken_version)
        versions = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        assert versions == baseline_versions
        assert not sqlite_mod._table_exists(conn, "broken_vN")
    finally:
        monkeypatch.setattr(sqlite_mod, "MIGRATIONS", original)
    conn.close()


def test_migration_5_adds_cost_usd_column(tmp_path: Path) -> None:
    """C1 (specs/monitoring.md): `query_log.cost_usd` exists after migrating
    a fresh store to latest, defaults to 0, and an upgrade from version 4
    (the pre-C1 schema) preserves existing rows while adding the column."""
    conn = connect(_fresh(tmp_path))
    migrate(conn, target_version=4)
    conn.execute(
        "INSERT INTO query_log (request_id, ts, latency_ms, arm, k, query_sha256_prefix) "
        "VALUES ('r-pre-c1', 't', 1, 'hybrid', 5, 'abc')"
    )
    conn.commit()

    migrate(conn, target_version=None)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(query_log)")}
    assert "cost_usd" in columns
    row = conn.execute("SELECT cost_usd FROM query_log WHERE request_id = 'r-pre-c1'").fetchone()
    assert row is not None
    assert row[0] == 0
    conn.close()


def test_migration_6_adds_judge_columns_and_answer_log_table(tmp_path: Path) -> None:
    """C6 (specs/monitoring.md "Online judge"): `query_log.relevance` /
    `judge_model` exist and default to NULL, `answer_log` exists, and an
    upgrade from version 5 preserves existing `query_log` rows."""
    conn = connect(_fresh(tmp_path))
    migrate(conn, target_version=5)
    conn.execute(
        "INSERT INTO query_log (request_id, ts, latency_ms, arm, k, query_sha256_prefix) "
        "VALUES ('r-pre-c6', 't', 1, 'hybrid', 5, 'abc')"
    )
    conn.commit()

    migrate(conn, target_version=None)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(query_log)")}
    assert {"relevance", "judge_model"} <= columns
    row = conn.execute(
        "SELECT relevance, judge_model FROM query_log WHERE request_id = 'r-pre-c6'"
    ).fetchone()
    assert tuple(row) == (None, None)

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "answer_log" in tables
    answer_log_columns = {row[1] for row in conn.execute("PRAGMA table_info(answer_log)")}
    assert answer_log_columns == {"request_id", "question", "answer", "created_at"}
    conn.close()


def test_query_log_principal_delete_sets_null(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    conn.execute(
        "INSERT INTO principal (id, kind, created_at) VALUES ('p-del', 'demo_session', 't')"
    )
    conn.execute(
        "INSERT INTO query_log "
        "(request_id, ts, latency_ms, arm, k, query_sha256_prefix, principal_id) "
        "VALUES ('r1', 't', 1, 'hybrid', 5, 'abc', 'p-del')"
    )
    conn.commit()
    conn.execute("DELETE FROM principal WHERE id = 'p-del'")
    conn.commit()
    row = conn.execute("SELECT principal_id FROM query_log WHERE request_id = 'r1'").fetchone()
    assert row is not None and row[0] is None
    conn.close()


def test_wings_cascade_when_area_deleted(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    conn.execute("DELETE FROM areas WHERE id = 'area-seed'")
    conn.commit()
    wing_count = int(conn.execute("SELECT COUNT(*) FROM wings").fetchone()[0])
    assert wing_count == 0
    conn.close()


def test_insert_feedback_persists_for_principal(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    insert_feedback(
        conn,
        principal_id="local-user",
        request_id="req-feedback-1",
        vote="up",
        comment="helpful",
    )
    row = conn.execute(
        "SELECT vote, comment FROM feedback WHERE request_id = 'req-feedback-1'"
    ).fetchone()
    assert row is not None
    assert row[0] == "up"
    assert row[1] == "helpful"
    conn.close()


def test_seed_rejects_invalid_manifest_shape(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    bad_root = tmp_path / "bad-root"
    (bad_root / "data").mkdir(parents=True)
    (bad_root / "data" / "manifest.yaml").write_text("not_a_list: true\n")
    (bad_root / "data" / "catalog.jsonl").write_text("")
    with pytest.raises(TypeError, match=r"manifest.yaml must be a list"):
        seed(conn, repo_root=bad_root)

    (bad_root / "data" / "manifest.yaml").write_text("- plain string\n")
    with pytest.raises(TypeError, match="manifest entries must be mappings"):
        seed(conn, repo_root=bad_root)
    conn.close()


def test_row_counts_zero_before_v2_tables_exist(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn, target_version=1)
    counts = row_counts(conn)
    assert counts["areas"] == 0
    assert counts["wings"] == 0
    assert counts["bookmarks"] == 0
    conn.close()


def test_rights_status_rejects_unknown_explicit_value() -> None:
    entry = {"book_id": "bad-rights", "rights_status": "not-a-real-status"}
    assert rights_status_from_manifest(entry) == "unknown"


def test_second_playlist_item_reuses_playlist_row(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    seed(conn, repo_root=REPO_ROOT)
    book_id = _first_book(conn)
    insert_playlist(conn, principal_id="local-user", resource_id=book_id, book_id=book_id)
    insert_playlist(conn, principal_id="local-user", resource_id="second-resource")
    playlist_count = int(
        conn.execute("SELECT COUNT(*) FROM playlist WHERE principal_id = 'local-user'").fetchone()[
            0
        ]
    )
    item_count = int(conn.execute("SELECT COUNT(*) FROM playlist_item").fetchone()[0])
    assert playlist_count == 1
    assert item_count == 2
    conn.close()


def test_seed_skips_catalog_rows_without_ol_key(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    root = tmp_path / "seed-root"
    (root / "data").mkdir(parents=True)
    (root / "data" / "manifest.yaml").write_text(
        "- book_id: only-book\n  title: Only\n  rights_status: public_domain\n"
    )
    (root / "data" / "catalog.jsonl").write_text(
        "\n"
        '{"title": "missing ol_key"}\n'
        '{"ol_key": "OL1", "title": "One", "authors": [], "subjects": []}\n'
        '{"ol_key": "OL2", "title": "Two", "authors": [], "subjects": []}\n'
        '{"ol_key": "OL3", "title": "Three", "authors": [], "subjects": []}\n'
    )
    seed(conn, repo_root=root)
    assert int(conn.execute("SELECT COUNT(*) FROM catalog").fetchone()[0]) == 2
    conn.close()


def test_logical_checksum_ignores_tables_missing_at_v1(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn, target_version=1)
    seed(conn, repo_root=REPO_ROOT)
    checksum = logical_checksum(conn)
    assert isinstance(checksum, str)
    assert len(checksum) == 64
    conn.close()


def test_missing_demo_state_raises_before_session_create(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn, target_version=1)
    conn.execute("DELETE FROM demo_state")
    conn.commit()
    with pytest.raises(RuntimeError, match="demo_state singleton missing"):
        create_demo_session(conn)
    conn.close()


def test_seed_with_blank_catalog_file_loads_books_only(tmp_path: Path) -> None:
    conn = connect(_fresh(tmp_path))
    migrate(conn)
    root = tmp_path / "blank-catalog"
    (root / "data").mkdir(parents=True)
    (root / "data" / "manifest.yaml").write_text(
        "- book_id: solo-book\n  title: Solo\n  rights_status: public_domain\n"
    )
    (root / "data" / "catalog.jsonl").write_text("\n\n")
    seed(conn, repo_root=root)
    assert int(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]) == 1
    assert int(conn.execute("SELECT COUNT(*) FROM catalog").fetchone()[0]) == 0
    conn.close()


def test_index_revision_bumps_after_fts_rebuild(tmp_path: Path) -> None:
    from apps.store.sqlite import (
        bump_index_revision,
        current_index_revision,
        rebuild_chunks_fts,
    )

    conn = connect(_fresh(tmp_path))
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("b1", "T", "[]", "public_domain"),
    )
    conn.execute(
        """
        INSERT INTO chunks (chunk_id, book_id, block_ids, section_path, text, char_start, char_end)
        VALUES ('c1', 'b1', '[]', '[]', 'hello', 0, 5)
        """,
    )
    rebuild_chunks_fts(conn)
    before = current_index_revision(conn)
    bump_index_revision(conn)
    after = current_index_revision(conn)
    assert after
    assert after == before or before == ""
    conn.close()


def test_rebuild_chunks_fts_noop_before_v4(tmp_path: Path) -> None:
    from apps.store.sqlite import rebuild_chunks_fts

    conn = connect(_fresh(tmp_path))
    migrate(conn, target_version=3)
    rebuild_chunks_fts(conn)
    conn.close()


def test_bump_index_revision_noop_before_v4(tmp_path: Path) -> None:
    from apps.store.sqlite import bump_index_revision, current_index_revision

    conn = connect(_fresh(tmp_path))
    migrate(conn, target_version=3)
    assert bump_index_revision(conn) == ""
    assert current_index_revision(conn) == ""
    conn.close()


def test_compute_index_revision_stable(tmp_path: Path) -> None:
    from apps.store.sqlite import compute_index_revision

    conn = connect(_fresh(tmp_path))
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("b1", "T", "[]", "public_domain"),
    )
    conn.execute(
        """
        INSERT INTO chunks (chunk_id, book_id, block_ids, section_path, text, char_start, char_end)
        VALUES ('c1', 'b1', '[]', '[]', 'hello', 0, 5)
        """,
    )
    assert compute_index_revision(conn) == compute_index_revision(conn)
    conn.close()
