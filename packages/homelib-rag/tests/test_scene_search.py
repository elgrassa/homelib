"""WP04 scene-search red tests — see specs/scene-search.md."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from homelib_rag import scene_search as scene_search_module
from homelib_rag.scene_search import (
    ResourceNotFoundError,
    ResourceNotSearchableError,
    SceneMode,
    scene_search,
)

from apps.store.sqlite import bump_index_revision, connect, migrate, rebuild_chunks_fts


@pytest.fixture(autouse=True)
def _mock_scene_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    def _fake_embed(_q: str) -> np.ndarray:
        vec = np.zeros(384, dtype=np.float32)
        vec[0] = 1.0
        return vec

    monkeypatch.setattr("homelib_rag.sqlite_index._embed_query", _fake_embed)


def _insert_book(conn: sqlite3.Connection, *, book_id: str) -> None:
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        (book_id, f"Title {book_id}", "[]", "public_domain"),
    )


def _insert_block(
    conn: sqlite3.Connection,
    *,
    block_id: str,
    book_id: str,
    ordinal: int,
    section_path: list[str],
    text: str,
    char_start: int,
    char_end: int,
) -> None:
    conn.execute(
        """
        INSERT INTO blocks (
            block_id, book_id, ordinal, section_path, text, char_start, char_end, format
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'txt')
        """,
        (
            block_id,
            book_id,
            ordinal,
            json.dumps(section_path),
            text,
            char_start,
            char_end,
        ),
    )


def _insert_chunk(
    conn: sqlite3.Connection,
    *,
    chunk_id: str,
    book_id: str,
    block_ids: list[str],
    section_path: list[str],
    text: str,
    char_start: int,
    char_end: int,
    embedding: list[float] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            book_id,
            json.dumps(block_ids),
            json.dumps(section_path),
            text,
            char_start,
            char_end,
        ),
    )
    if embedding is not None:
        conn.execute(
            """
            INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
            VALUES (?, ?, 'test-model', ?)
            """,
            (chunk_id, json.dumps(embedding), len(embedding)),
        )


@pytest.fixture
def scene_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    db_path = tmp_path / "scene.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    conn = connect(db_path)
    migrate(conn)
    book_a = "book-a"
    book_b = "book-b"
    _insert_book(conn, book_id=book_a)
    _insert_book(conn, book_id=book_b)

    text_a1 = "Alpha chapter opens with the lantern flickered in the corridor."
    text_a2 = "Beta chapter mentions discipline and daily practice."
    text_b1 = "Other book talks about unrelated machine learning topics."

    offset = 0
    for block_id, text, chapter in [
        ("a-ch1-b0", text_a1, "Chapter Alpha"),
        ("a-ch2-b0", text_a2, "Chapter Beta"),
        ("b-ch1-b0", text_b1, "Chapter One"),
    ]:
        book_id = book_a if block_id.startswith("a-") else book_b
        _insert_block(
            conn,
            block_id=block_id,
            book_id=book_id,
            ordinal=0 if "ch1" in block_id else 1,
            section_path=[chapter],
            text=text,
            char_start=offset,
            char_end=offset + len(text),
        )
        _insert_chunk(
            conn,
            chunk_id=f"{block_id}-chunk",
            book_id=book_id,
            block_ids=[block_id],
            section_path=[chapter],
            text=text,
            char_start=offset,
            char_end=offset + len(text),
            embedding=[1.0 if book_id == book_a else 0.0] * 384,
        )
        offset += len(text)

    rebuild_chunks_fts(conn)
    bump_index_revision(conn)
    conn.commit()
    yield conn
    conn.close()


def test_exact_offsets_map_to_original_text(scene_db: sqlite3.Connection) -> None:
    response = scene_search(scene_db, "book-a", "lantern flickered", SceneMode.EXACT, k=3)
    assert response.hits
    canonical = "".join(
        str(row[0])
        for row in scene_db.execute(
            "SELECT text FROM blocks WHERE book_id = ? ORDER BY ordinal",
            ("book-a",),
        )
    )
    for hit in response.hits:
        assert canonical[hit.char_start : hit.char_end] == hit.quote


def test_chapter_scope_never_leaks(scene_db: sqlite3.Connection) -> None:
    response = scene_search(
        scene_db,
        "book-a",
        "lantern",
        SceneMode.KEYWORD,
        chapter_id="a-ch1-b0",
        k=5,
    )
    assert response.hits
    for hit in response.hits:
        assert "lantern" in hit.quote.lower()
        assert "discipline" not in hit.quote.lower()


def test_book_scope_survives_rewrite(
    scene_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        scene_search_module,
        "rewrite_query",
        lambda _q: "machine learning unrelated topics",
    )
    response = scene_search(
        scene_db,
        "book-a",
        "original question about alpha",
        SceneMode.ASK,
        k=5,
    )
    assert response.hits
    assert all(hit.resource_id == "book-a" for hit in response.hits)
    assert all("machine learning" not in hit.quote.lower() for hit in response.hits)


def test_open_anchor_always_resolves(scene_db: sqlite3.Connection) -> None:
    response = scene_search(scene_db, "book-a", "lantern", SceneMode.KEYWORD, k=5)
    assert response.hits
    for hit in response.hits:
        row = scene_db.execute(
            "SELECT 1 FROM blocks WHERE block_id = ?",
            (hit.open_anchor,),
        ).fetchone()
        assert row is not None


def test_search_with_llm_unreachable(
    scene_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_llm(_query: str, _hits: list[object]) -> str:
        raise ConnectionError("llm unreachable")

    monkeypatch.setattr(scene_search_module, "_synthesize_ask", _raise_llm)

    exact = scene_search(scene_db, "book-a", "lantern", SceneMode.EXACT, k=3)
    keyword = scene_search(scene_db, "book-a", "lantern", SceneMode.KEYWORD, k=3)
    ask = scene_search(scene_db, "book-a", "lantern", SceneMode.ASK, k=3)

    assert exact.hits
    assert keyword.hits
    assert ask.hits
    assert ask.degraded is True
    assert ask.synthesis is None


def test_vector_down_degrades_flagged(
    scene_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _vector_down(*_args: object, **_kwargs: object) -> list[object]:
        raise RuntimeError("vector backend down")

    monkeypatch.setattr(scene_search_module, "_sqlite_vector", _vector_down)

    response = scene_search(scene_db, "book-a", "lantern", SceneMode.SEMANTIC, k=3)
    assert response.degraded is True
    assert response.hits


def test_unknown_resource_raises_not_found(scene_db: sqlite3.Connection) -> None:
    with pytest.raises(ResourceNotFoundError):
        scene_search(scene_db, "missing-book", "lantern", SceneMode.KEYWORD, k=3)


def test_metadata_only_resource_raises_not_searchable(scene_db: sqlite3.Connection) -> None:
    scene_db.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("meta-only", "Meta", "[]", "metadata_only"),
    )
    scene_db.commit()
    with pytest.raises(ResourceNotSearchableError):
        scene_search(scene_db, "meta-only", "anything", SceneMode.KEYWORD, k=3)


def test_smart_mode_returns_fused_hits(scene_db: sqlite3.Connection) -> None:
    response = scene_search(scene_db, "book-a", "lantern", SceneMode.SMART, k=3)
    assert response.hits
    assert response.mode_used in {"smart", "keyword", "semantic"}


def test_resource_not_found(scene_db: sqlite3.Connection) -> None:
    with pytest.raises(scene_search_module.ResourceNotFoundError):
        scene_search(scene_db, "missing-book", "lantern", SceneMode.KEYWORD, k=3)


def test_resource_not_searchable(scene_db: sqlite3.Connection) -> None:
    scene_db.execute(
        "UPDATE books SET rights_status = ? WHERE book_id = ?",
        ("unknown", "book-a"),
    )
    scene_db.commit()
    with pytest.raises(scene_search_module.ResourceNotSearchableError):
        scene_search(scene_db, "book-a", "lantern", SceneMode.KEYWORD, k=3)


def test_exact_empty_query_returns_no_hits(scene_db: sqlite3.Connection) -> None:
    response = scene_search(scene_db, "book-a", "   ", SceneMode.EXACT, k=3)
    assert response.hits == []


def test_semantic_mode_success(
    scene_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        scene_search_module,
        "_sqlite_vector",
        lambda q, k, **kw: scene_search_module._sqlite_lexical(q, k, **kw),
    )
    response = scene_search(scene_db, "book-a", "lantern", SceneMode.SEMANTIC, k=3)
    assert response.hits
    assert response.mode_used == "semantic"
    assert response.degraded is False


def test_smart_mode_hybrid(scene_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scene_search_module,
        "_sqlite_vector",
        lambda q, k, **kw: scene_search_module._sqlite_lexical(q, k, **kw),
    )
    response = scene_search(scene_db, "book-a", "lantern", SceneMode.SMART, k=3)
    assert response.hits
    assert response.mode_used == "smart"


def test_smart_mode_lexical_only_degraded(
    scene_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail(*_a: object, **_k: object) -> list[object]:
        raise RuntimeError("vector down")

    monkeypatch.setattr(scene_search_module, "_sqlite_vector", _fail)
    response = scene_search(scene_db, "book-a", "lantern", SceneMode.SMART, k=3)
    assert response.hits
    assert response.degraded is True
    assert response.mode_used == "keyword"


def test_smart_mode_vector_only_degraded(
    scene_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from homelib_rag.models import Hit

    def _fail(*_a: object, **_k: object) -> list[object]:
        raise RuntimeError("lexical down")

    def _vector_only(_q: str, _k: int, **kw: object) -> list[Hit]:
        return [
            Hit(
                chunk_id="a-ch1-b0-chunk",
                book_id="book-a",
                score=1.0,
                rank=1,
                text="Alpha chapter opens with the lantern flickered in the corridor.",
                section_path=["Chapter Alpha"],
                page=None,
                block_ids=["a-ch1-b0"],
            )
        ]

    monkeypatch.setattr(scene_search_module, "_sqlite_lexical", _fail)
    monkeypatch.setattr(scene_search_module, "_sqlite_vector", _vector_only)
    response = scene_search(scene_db, "book-a", "lantern", SceneMode.SMART, k=3)
    assert response.hits
    assert response.degraded is True
    assert response.mode_used == "semantic"


def test_ask_success_sets_synthesis(
    scene_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scene_search_module, "_synthesize_ask", lambda _q, _h: "short answer")
    response = scene_search(scene_db, "book-a", "lantern", SceneMode.ASK, k=3)
    assert response.hits
    assert response.synthesis == "short answer"
    assert response.mode_used == "ask"
    assert response.degraded is False


def test_chapter_filter_excludes_other_chapters(scene_db: sqlite3.Connection) -> None:
    response = scene_search(
        scene_db,
        "book-a",
        "lantern",
        SceneMode.KEYWORD,
        chapter_id="a-ch2-b0",
        k=5,
    )
    assert response.hits == []
