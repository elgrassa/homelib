"""WP04 SQLite index tests — FTS5 + cached NumPy matrix."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest
from homelib_rag.sqlite_index import (
    _load_matrix,
    _reset_caches_for_tests,
    search_lexical,
    search_vector,
)

from apps.store.sqlite import bump_index_revision, connect, migrate, rebuild_chunks_fts


@pytest.fixture
def sqlite_index_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    db_path = tmp_path / "index.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-1", "Book", "[]", "public_domain"),
    )
    text_phrase = "The reciprocal rank fusion algorithm improves retrieval quality."
    text_scattered = "Reciprocal ideas appear far apart. Rank is elsewhere. Fusion later."
    for ordinal, (block_id, text) in enumerate(
        [("b-phrase", text_phrase), ("b-scatter", text_scattered)]
    ):
        conn.execute(
            """
            INSERT INTO blocks (
                block_id, book_id, ordinal, section_path, text, char_start, char_end, format
            ) VALUES (?, 'book-1', ?, '["Chapter 1"]', ?, ?, ?, 'txt')
            """,
            (block_id, ordinal, text, 0 if ordinal == 0 else len(text_phrase), len(text)),
        )
        conn.execute(
            """
            INSERT INTO chunks (
                chunk_id, book_id, block_ids, section_path, text, char_start, char_end
            ) VALUES (?, 'book-1', ?, '["Chapter 1"]', ?, ?, ?)
            """,
            (
                f"c-{ordinal}",
                json.dumps([block_id]),
                text,
                0 if ordinal == 0 else len(text_phrase),
                len(text) if ordinal == 0 else len(text_phrase) + len(text),
            ),
        )
        vector = np.zeros(384, dtype=np.float32)
        vector[ordinal] = 1.0
        conn.execute(
            """
            INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
            VALUES (?, ?, 'test-model', 384)
            """,
            (f"c-{ordinal}", json.dumps(vector.tolist())),
        )
    rebuild_chunks_fts(conn)
    bump_index_revision(conn)
    conn.commit()
    _reset_caches_for_tests()
    yield conn
    conn.close()


def test_search_lexical_ranks_exact_phrase_above_scattered_terms(
    sqlite_index_db: sqlite3.Connection,
) -> None:
    hits = search_lexical("reciprocal rank fusion algorithm", 5, conn=sqlite_index_db)
    assert hits
    assert hits[0].chunk_id == "c-0"


def test_search_vector_finds_semantic_match_without_shared_terms(
    sqlite_index_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_embed(_q: str) -> np.ndarray:
        vec = np.zeros(384, dtype=np.float32)
        vec[1] = 1.0
        return vec

    monkeypatch.setattr("homelib_rag.sqlite_index._embed_query", _fake_embed)
    hits = search_vector("paraphrase with no lexical overlap", 5, conn=sqlite_index_db)
    assert hits
    assert hits[0].chunk_id == "c-1"
    lexical = search_lexical("paraphrase with no lexical overlap", 5, conn=sqlite_index_db)
    assert all(hit.chunk_id != "c-1" for hit in lexical)


def test_matrix_cache_reuses_revision(sqlite_index_db: sqlite3.Connection) -> None:
    first = _load_matrix(sqlite_index_db)
    second = _load_matrix(sqlite_index_db)
    assert first is second


def test_search_lexical_rejects_empty_query(sqlite_index_db: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="q must not be empty"):
        search_lexical("   ", 5, conn=sqlite_index_db)


def test_sqlite_path_unset_raises_on_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)
    with pytest.raises(RuntimeError, match="HOMELIB_SQLITE_PATH"):
        search_lexical("query", 5)


def test_matrix_cache_rebuilds_after_revision_bump(
    sqlite_index_db: sqlite3.Connection,
) -> None:
    first = _load_matrix(sqlite_index_db)
    sqlite_index_db.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('c-new', 'book-1', '["b-phrase"]', '["Chapter 1"]', 'extra chunk', 0, 11)
        """
    )
    sqlite_index_db.execute(
        """
        INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
        VALUES ('c-new', ?, 'test-model', 384)
        """,
        (json.dumps([0.0] * 384),),
    )
    bump_index_revision(sqlite_index_db)
    sqlite_index_db.commit()
    _reset_caches_for_tests()
    second = _load_matrix(sqlite_index_db)
    assert first is not second
    assert first.revision != second.revision


def test_search_lexical_scoped_to_book(sqlite_index_db: sqlite3.Connection) -> None:
    sqlite_index_db.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-2", "Other", "[]", "public_domain"),
    )
    sqlite_index_db.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('c-other', 'book-2', '["b-other"]', '["Ch"]', 'reciprocal rank fusion', 0, 22)
        """
    )
    rebuild_chunks_fts(sqlite_index_db)
    hits = search_lexical("reciprocal rank fusion", 5, book_id="book-1", conn=sqlite_index_db)
    assert hits
    assert all(hit.book_id == "book-1" for hit in hits)


def test_sqlite_path_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)
    from homelib_rag.sqlite_index import sqlite_path

    assert sqlite_path() is None


def test_search_validation_errors(sqlite_index_db: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="q must not be empty"):
        search_lexical("", 1, conn=sqlite_index_db)
    with pytest.raises(ValueError, match="k must be positive"):
        search_lexical("reciprocal", 0, conn=sqlite_index_db)


def test_search_lexical_opens_own_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "own.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-1", "Book", "[]", "public_domain"),
    )
    text = "Standalone lexical connection test phrase."
    conn.execute(
        """
        INSERT INTO blocks (
            block_id, book_id, ordinal, section_path, text, char_start, char_end, format
        ) VALUES ('b0', 'book-1', 0, '["Ch"]', ?, 0, ?, 'txt')
        """,
        (text, len(text)),
    )
    conn.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('c0', 'book-1', '["b0"]', '["Ch"]', ?, 0, ?)
        """,
        (text, len(text)),
    )
    rebuild_chunks_fts(conn)
    bump_index_revision(conn)
    conn.commit()
    conn.close()

    hits = search_lexical("standalone lexical", 3)
    assert hits
    assert hits[0].chunk_id == "c0"


def test_search_vector_book_filter_and_page(
    sqlite_index_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqlite_index_db.execute("UPDATE blocks SET page = 7 WHERE block_id = 'b-phrase'")
    sqlite_index_db.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-2", "Other", "[]", "public_domain"),
    )
    sqlite_index_db.execute(
        """
        INSERT INTO blocks (
            block_id, book_id, ordinal, section_path, text, char_start, char_end, format, page
        ) VALUES ('b-other', 'book-2', 0, '["Ch"]', 'other book chunk', 0, 16, 'txt', 1)
        """
    )
    sqlite_index_db.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('c-other', 'book-2', '["b-other"]', '["Ch"]', 'other book chunk', 0, 16)
        """
    )
    vec = np.zeros(384, dtype=np.float32)
    vec[0] = 1.0
    sqlite_index_db.execute(
        """
        INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
        VALUES ('c-other', ?, 'test-model', 384)
        """,
        (json.dumps(vec.tolist()),),
    )
    rebuild_chunks_fts(sqlite_index_db)
    bump_index_revision(sqlite_index_db)
    sqlite_index_db.commit()
    _reset_caches_for_tests()

    def _fake_embed(_q: str) -> np.ndarray:
        vec = np.zeros(384, dtype=np.float32)
        vec[0] = 1.0
        return vec

    monkeypatch.setattr("homelib_rag.sqlite_index._embed_query", _fake_embed)
    hits = search_vector("anything", 5, book_id="book-2", conn=sqlite_index_db)
    assert hits
    assert hits[0].book_id == "book-2"
    assert hits[0].page == 1

    lexical = search_lexical("chunk", 5, book_id="book-2", conn=sqlite_index_db)
    assert lexical
    assert lexical[0].page == 1


def test_search_vector_without_conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "vec.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-1", "Book", "[]", "public_domain"),
    )
    text = "Vector path opens its own sqlite connection."
    conn.execute(
        """
        INSERT INTO blocks (
            block_id, book_id, ordinal, section_path, text, char_start, char_end, format
        ) VALUES ('b0', 'book-1', 0, '["Ch"]', ?, 0, ?, 'txt')
        """,
        (text, len(text)),
    )
    conn.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('c0', 'book-1', '["b0"]', '["Ch"]', ?, 0, ?)
        """,
        (text, len(text)),
    )
    vec = np.zeros(384, dtype=np.float32)
    vec[0] = 1.0
    conn.execute(
        """
        INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
        VALUES ('c0', ?, 'test-model', 384)
        """,
        (json.dumps(vec.tolist()),),
    )
    bump_index_revision(conn)
    conn.commit()
    conn.close()
    _reset_caches_for_tests()

    monkeypatch.setattr(
        "homelib_rag.sqlite_index._embed_query",
        lambda _q: vec,
    )
    hits = search_vector("vector path", 3)
    assert hits
    assert hits[0].chunk_id == "c0"


def test_fts_query_drops_english_stopwords_like_plainto_tsquery() -> None:
    """Questions must not AND-require 'what'/'is' — that zeroed lexical@5 on SQLite."""
    from homelib_rag.sqlite_index import _fts_query, _fts_query_or

    assert _fts_query("What is compound interest?") == '"compound" "interest"'
    assert _fts_query("How does compound interest work?") == '"compound" "interest" "work"'
    assert _fts_query_or("money described") == '"money" OR "described"'


def test_search_lexical_or_fallback_when_and_matches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``money described`` AND-matches nothing if the words never co-occur.

    Without an OR fallback, smart scene search fell through to weak vectors
    and returned unrelated passages (Shelf "Open the scene" looked broken).
    """
    from homelib_rag.sqlite_index import _reset_caches_for_tests, search_lexical

    from apps.store.sqlite import bump_index_revision, connect, migrate, rebuild_chunks_fts

    db_path = tmp_path / "or_fallback.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    _reset_caches_for_tests()
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-1", "Book", "[]", "public_domain"),
    )
    rows = [
        ("b0", 0, "Friends raised money to buy a new dog."),
        ("b1", 1, "She described the garden in careful detail."),
        ("b2", 2, "Learning to read with raised letters."),
    ]
    for block_id, ordinal, text in rows:
        conn.execute(
            """
            INSERT INTO blocks (
                block_id, book_id, ordinal, section_path, text, char_start, char_end, format
            ) VALUES (?, 'book-1', ?, '[]', ?, 0, ?, 'txt')
            """,
            (block_id, ordinal, text, len(text)),
        )
        chunk_id = f"c{ordinal}"
        conn.execute(
            """
            INSERT INTO chunks (
                chunk_id, book_id, block_ids, section_path, text, char_start, char_end
            ) VALUES (?, 'book-1', ?, '[]', ?, 0, ?)
            """,
            (chunk_id, json.dumps([block_id]), text, len(text)),
        )
    rebuild_chunks_fts(conn)
    bump_index_revision(conn)
    conn.commit()

    and_hits = search_lexical("money described", 5, book_id="book-1", conn=conn)
    assert any("money" in h.text.lower() for h in and_hits)
    # Overlap re-rank: the money passage must outrank "described"-only and
    # the unrelated "learning to read" filler.
    assert "money" in and_hits[0].text.lower()
    conn.close()
    _reset_caches_for_tests()


def test_load_matrix_accepts_float32_blob_embeddings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ingest stores embeddings as float32 BLOBs; JSON-only decode fully degraded vector."""
    db_path = tmp_path / "blob.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-1", "Book", "[]", "public_domain"),
    )
    text = "Compound interest grows wealth over time."
    conn.execute(
        """
        INSERT INTO blocks (
            block_id, book_id, ordinal, section_path, text, char_start, char_end, format
        ) VALUES ('b0', 'book-1', 0, '["Ch"]', ?, 0, ?, 'txt')
        """,
        (text, len(text)),
    )
    conn.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('c-blob', 'book-1', '["b0"]', '["Ch"]', ?, 0, ?)
        """,
        (text, len(text)),
    )
    vec = np.zeros(384, dtype=np.float32)
    vec[3] = 1.0
    conn.execute(
        """
        INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
        VALUES ('c-blob', ?, 'test-model', 384)
        """,
        (vec.tobytes(),),
    )
    rebuild_chunks_fts(conn)
    bump_index_revision(conn)
    conn.commit()
    _reset_caches_for_tests()

    cache = _load_matrix(conn)
    assert cache.chunk_ids == ["c-blob"]
    assert cache.matrix.shape == (1, 384)

    monkeypatch.setattr(
        "homelib_rag.sqlite_index._embed_query",
        lambda _q: vec,
    )
    hits = search_vector("wealth grows", 3, conn=conn)
    assert hits
    assert hits[0].chunk_id == "c-blob"
    lexical = search_lexical("What is compound interest?", 3, conn=conn)
    assert lexical
    assert lexical[0].chunk_id == "c-blob"
    conn.close()
