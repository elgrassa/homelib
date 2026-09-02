"""SQLite dispatch on homelib_rag.index when HOMELIB_SQLITE_PATH is set."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest
from homelib_rag import index as index_module

from apps.store.sqlite import bump_index_revision, connect, migrate, rebuild_chunks_fts


@pytest.fixture
def sqlite_dispatch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    db_path = tmp_path / "dispatch.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-d", "Dispatch", "[]", "public_domain"),
    )
    text = "Dispatch test chunk about leadership and focus."
    conn.execute(
        """
        INSERT INTO blocks (
            block_id, book_id, ordinal, section_path, text, char_start, char_end, format
        ) VALUES ('bd-0', 'book-d', 0, '["Ch1"]', ?, 0, ?, 'txt')
        """,
        (text, len(text)),
    )
    conn.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('cd-0', 'book-d', '["bd-0"]', '["Ch1"]', ?, 0, ?)
        """,
        (text, len(text)),
    )
    vector = np.zeros(384, dtype=np.float32)
    vector[0] = 1.0
    conn.execute(
        """
        INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
        VALUES ('cd-0', ?, 'test-model', 384)
        """,
        (json.dumps(vector.tolist()),),
    )
    rebuild_chunks_fts(conn)
    bump_index_revision(conn)
    conn.commit()

    def _fake_embed(_q: str) -> list[float]:
        return vector.tolist()

    monkeypatch.setattr("homelib_rag.sqlite_index._embed_query", lambda q: vector)
    monkeypatch.setattr(index_module, "_embed_query", _fake_embed)
    yield conn
    conn.close()


def test_index_search_lexical_dispatches_to_sqlite(sqlite_dispatch_db: sqlite3.Connection) -> None:
    hits = index_module.search_lexical("leadership focus", 5)
    assert hits
    assert hits[0].chunk_id == "cd-0"


def test_index_search_vector_dispatches_to_sqlite(sqlite_dispatch_db: sqlite3.Connection) -> None:
    hits = index_module.search_vector("leadership focus", 5)
    assert hits
    assert hits[0].chunk_id == "cd-0"
