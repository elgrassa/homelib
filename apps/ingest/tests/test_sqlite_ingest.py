"""WP03 SQLite ingest red tests — see docs/plan-v2.md and specs/rights.md."""

from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

import pytest
from homelib_core.models import Block, BookDoc, Provenance

from apps.ingest.sqlite_pipeline import (
    CANONICAL_COUNTS,
    REPO_ROOT,
    SNAPSHOT_PATH,
    expected_chunk_ids_from_snapshot,
    run_sqlite_pipeline,
)
from apps.store.sqlite import connect, migrate, row_counts

pytestmark = pytest.mark.slow


def _fake_embeddings(texts: list[str]) -> list[list[float]]:
    return [[float(index) / 384.0] * 384 for index, _ in enumerate(texts)]


@pytest.fixture(autouse=True)
def _mock_embed_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.ingest.pipeline as pipeline_mod
    import apps.ingest.sqlite_pipeline as sqlite_pipeline_mod

    monkeypatch.setattr(pipeline_mod, "embed_texts", _fake_embeddings)
    monkeypatch.setattr(sqlite_pipeline_mod, "embed_texts", _fake_embeddings)


def _book(
    book_id: str,
    *,
    text: str = (
        "Sentence one about leadership. Sentence two about discipline. "
        "Sentence three about practice. Sentence four about mastery."
    ),
) -> BookDoc:
    block = Block(
        block_id=f"{book_id}-b0",
        book_id=book_id,
        ordinal=0,
        section_path=["Chapter One"],
        text=text,
        char_start=0,
        char_end=len(text),
        provenance=Provenance(format="txt", source_sha256="deadbeef"),
    )
    return BookDoc(
        book_id=book_id,
        title=f"Title {book_id}",
        authors=["Author One"],
        language="en",
        source_url="https://example.org",
        license_note="Public domain",
        blocks=[block],
        canonical_text=text,
    )


def _write_snapshot(path: Path, docs: list[BookDoc]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc.model_dump(mode="json")) + "\n")


def _fresh_db(tmp_path: Path) -> Path:
    return tmp_path / "homelib.sqlite"


def _corpus_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "books": int(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]),
        "blocks": int(conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]),
        "chunks": int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]),
        "chunk_embeddings": int(
            conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()[0]
        ),
    }


def test_chunk_ids_match_v1_snapshot(tmp_path: Path) -> None:
    db_path = _fresh_db(tmp_path)
    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)

    expected_ids = set(expected_chunk_ids_from_snapshot(SNAPSHOT_PATH))
    conn = connect(db_path)
    loaded_ids = {
        str(row[0]) for row in conn.execute("SELECT chunk_id FROM chunks ORDER BY chunk_id")
    }
    conn.close()

    assert loaded_ids == expected_ids
    assert len(loaded_ids) == CANONICAL_COUNTS["chunks"]


def test_second_run_no_duplicates(tmp_path: Path) -> None:
    db_path = _fresh_db(tmp_path)
    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)
    conn = connect(db_path)
    first = _corpus_counts(conn)
    conn.close()
    assert first == CANONICAL_COUNTS

    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)
    conn = connect(db_path)
    second = _corpus_counts(conn)
    conn.close()
    assert second == first


def test_every_citation_resolves(tmp_path: Path) -> None:
    db_path = _fresh_db(tmp_path)
    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)
    conn = connect(db_path)

    orphan_blocks = conn.execute(
        """
        SELECT c.chunk_id, value AS block_id
        FROM chunks c, json_each(c.block_ids) AS value
        LEFT JOIN blocks b ON b.block_id = value
        WHERE b.block_id IS NULL
        LIMIT 5
        """
    ).fetchall()
    assert orphan_blocks == []

    with gzip.open(SNAPSHOT_PATH, "rt", encoding="utf-8") as handle:
        canonical_by_book = {
            BookDoc.model_validate_json(line.strip()).book_id: BookDoc.model_validate_json(
                line.strip()
            ).canonical_text
            for line in handle
            if line.strip()
        }

    rows = conn.execute(
        "SELECT chunk_id, book_id, block_ids, text, char_start, char_end FROM chunks"
    ).fetchall()
    for chunk_id, book_id, block_ids_json, text, char_start, char_end in rows:
        canonical = canonical_by_book[book_id]
        assert canonical[char_start:char_end] == text, chunk_id
        for block_id in json.loads(str(block_ids_json)):
            block = conn.execute(
                "SELECT text, char_start, char_end FROM blocks WHERE block_id = ?",
                (block_id,),
            ).fetchone()
            assert block is not None, block_id

    conn.close()


def test_metadata_only_never_indexed(tmp_path: Path) -> None:
    snapshot = tmp_path / "rights.jsonl.gz"
    book_id = "metadata-only-book"
    _write_snapshot(snapshot, [_book(book_id)])
    db_path = _fresh_db(tmp_path)
    rights = {book_id: "metadata_only"}

    run_sqlite_pipeline(db_path, snapshot=snapshot, rights_by_book=rights)

    conn = connect(db_path)
    book_row = conn.execute(
        "SELECT rights_status FROM books WHERE book_id = ?", (book_id,)
    ).fetchone()
    block_count = conn.execute(
        "SELECT COUNT(*) FROM blocks WHERE book_id = ?", (book_id,)
    ).fetchone()
    chunk_count = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE book_id = ?", (book_id,)
    ).fetchone()
    conn.close()

    assert book_row is not None and book_row[0] == "metadata_only"
    assert int(block_count[0]) == 0
    assert int(chunk_count[0]) == 0


def test_unknown_rights_fail_closed(tmp_path: Path) -> None:
    snapshot = tmp_path / "unknown.jsonl.gz"
    book_id = "unknown-rights-book"
    _write_snapshot(snapshot, [_book(book_id)])
    db_path = _fresh_db(tmp_path)
    rights = {book_id: "unknown"}

    run_sqlite_pipeline(db_path, snapshot=snapshot, rights_by_book=rights)

    conn = connect(db_path)
    book_row = conn.execute(
        "SELECT rights_status FROM books WHERE book_id = ?", (book_id,)
    ).fetchone()
    block_count = conn.execute(
        "SELECT COUNT(*) FROM blocks WHERE book_id = ?", (book_id,)
    ).fetchone()
    chunk_count = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE book_id = ?", (book_id,)
    ).fetchone()
    embedding_count = conn.execute(
        """
        SELECT COUNT(*) FROM chunk_embeddings e
        JOIN chunks c ON c.chunk_id = e.chunk_id
        WHERE c.book_id = ?
        """,
        (book_id,),
    ).fetchone()
    conn.close()

    assert book_row is not None and book_row[0] == "unknown"
    assert int(block_count[0]) == 0
    assert int(chunk_count[0]) == 0
    assert int(embedding_count[0]) == 0


def test_wp03_does_not_break_wp02_seed_counts(tmp_path: Path) -> None:
    """Migrate + seed still works after v3 corpus tables exist."""
    db_path = _fresh_db(tmp_path)
    conn = connect(db_path)
    migrate(conn)
    from apps.store.sqlite import seed

    seed(conn, repo_root=REPO_ROOT)
    before = row_counts(conn)
    conn.close()

    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)
    conn = connect(db_path)
    after_seed_tables = {
        key: row_counts(conn)[key] for key in ("playlist", "principal", "areas", "wings")
    }
    conn.close()

    assert after_seed_tables["principal"] == before["principal"]
    assert after_seed_tables["areas"] == before["areas"]
