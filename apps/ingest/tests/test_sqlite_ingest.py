"""WP03 SQLite ingest red tests — see docs/plan-v2.md and specs/rights.md."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sqlite3
import struct
from pathlib import Path

import pytest
from homelib_core.models import Block, BookDoc, Provenance

from apps.ingest.sqlite_pipeline import (
    CANONICAL_COUNTS,
    REPO_ROOT,
    SNAPSHOT_PATH,
    _sync_staging_to_canonical,
    expected_chunk_ids_from_snapshot,
    manifest_rights_by_book_id,
    run_sqlite_pipeline,
    staging_db_path,
)
from apps.store.sqlite import connect, migrate

GROUND_TRUTH_PATH = REPO_ROOT / "evals" / "ground_truth.jsonl"
INGEST_DIR = REPO_ROOT / "apps" / "ingest"
V1_CHUNK_IDS_SHA256 = "349733ec7a8537112fccccfe0c50a14f5f58d89aa979c16685bef0c3683f4206"


def _fake_embeddings(texts: list[str]) -> list[list[float]]:
    return [[float(i) / 384.0] * 384 for i, _ in enumerate(texts)]


@pytest.fixture(autouse=True)
def _mock_embed_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.ingest.pipeline as pipeline_mod
    import apps.ingest.sqlite_pipeline as sqlite_pipeline_mod

    monkeypatch.setattr(pipeline_mod, "embed_texts", _fake_embeddings)
    monkeypatch.setattr(sqlite_pipeline_mod, "embed_texts", _fake_embeddings)


@pytest.fixture(scope="module")
def ingested_corpus_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_path = tmp_path_factory.mktemp("wp03-corpus") / "homelib.sqlite"
    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)
    return db_path


def _book(book_id: str) -> BookDoc:
    text = (
        "Sentence one about leadership. Sentence two about discipline. "
        "Sentence three about practice. Sentence four about mastery."
    )
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


def _create_minimal_staging(staging_path: Path) -> None:
    conn = connect(staging_path)
    for ddl in (
        "CREATE TABLE books (book_id TEXT, title TEXT, authors TEXT, language TEXT, "
        "source_url TEXT, license_note TEXT)",
        "CREATE TABLE blocks (block_id TEXT, book_id TEXT, ordinal INTEGER, "
        "section_path TEXT, text TEXT, char_start INTEGER, char_end INTEGER, "
        "format TEXT, page INTEGER, spine_index INTEGER, anchor TEXT)",
        "CREATE TABLE chunks (chunk_id TEXT, book_id TEXT, block_ids TEXT, "
        "section_path TEXT, text TEXT, char_start INTEGER, char_end INTEGER)",
        "CREATE TABLE chunk_embeddings (chunk_id TEXT, embedding TEXT)",
        "CREATE TABLE catalog (ol_key TEXT, title TEXT, authors TEXT, subjects TEXT, "
        "first_publish_year INTEGER, description TEXT, provenance_note TEXT)",
    ):
        conn.execute(ddl)
    conn.execute("INSERT INTO books VALUES ('b1', 'T', '[]', 'en', '', 'note')")
    conn.commit()
    conn.close()


def test_staging_db_path_uses_dataset_suffix(tmp_path: Path) -> None:
    assert staging_db_path(tmp_path / "homelib.sqlite").name == "homelib__homelib_staging.sqlite"


def test_manifest_rights_maps_explicit_public_domain() -> None:
    rights = manifest_rights_by_book_id(REPO_ROOT)
    assert rights["franklin-autobiography"] == "public_domain"
    assert len(rights) == 18


def test_expected_chunk_ids_match_canonical_count() -> None:
    assert len(expected_chunk_ids_from_snapshot(SNAPSHOT_PATH)) == CANONICAL_COUNTS["chunks"]


def test_manifest_rights_skips_non_dict_entries(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "manifest.yaml").write_text(
        "- plain string\n- book_id: ok-book\n  license_note: Public domain (US)\n"
    )
    assert manifest_rights_by_book_id(tmp_path) == {"ok-book": "unknown"}


def test_sync_staging_rolls_back_on_catalog_error(tmp_path: Path) -> None:
    import apps.ingest.sqlite_pipeline as mod

    db_path = _fresh_db(tmp_path)
    _create_minimal_staging(staging_db_path(db_path))
    conn = connect(db_path)
    migrate(conn)
    before = int(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0])
    conn.close()
    original = mod._sync_catalog
    mod._sync_catalog = lambda _c: (_ for _ in ()).throw(RuntimeError("catalog sync failed"))
    try:
        with pytest.raises(RuntimeError, match="catalog sync failed"):
            _sync_staging_to_canonical(db_path, rights_by_book={"b1": "public_domain"})
    finally:
        mod._sync_catalog = original
    conn = connect(db_path)
    assert int(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]) == before
    conn.close()


def test_sync_staging_removes_block_replaced_by_new_provenance_id(tmp_path: Path) -> None:
    db_path = _fresh_db(tmp_path)
    staging_path = staging_db_path(db_path)
    _create_minimal_staging(staging_path)

    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, rights_status) VALUES ('b1', 'T', 'public_domain')"
    )
    conn.execute(
        "INSERT INTO blocks "
        "(block_id, book_id, ordinal, section_path, text, char_start, char_end, format) "
        "VALUES ('old-section-id', 'b1', 0, '[\"Wrong\"]', 'text', 0, 4, 'txt')"
    )
    conn.commit()
    conn.close()

    staging = connect(staging_path)
    staging.execute(
        "INSERT INTO blocks VALUES "
        "('correct-section-id', 'b1', 0, '[\"Correct\"]', 'text', 0, 4, 'txt', NULL, NULL, "
        "'correct')"
    )
    staging.commit()
    staging.close()

    _sync_staging_to_canonical(db_path, rights_by_book={"b1": "public_domain"})

    conn = connect(db_path)
    block_ids = [str(row[0]) for row in conn.execute("SELECT block_id FROM blocks")]
    conn.close()
    assert block_ids == ["correct-section-id"]


def test_sync_chunk_embeddings_stores_float32_blob(tmp_path: Path) -> None:
    import apps.ingest.sqlite_pipeline as mod

    db_path = _fresh_db(tmp_path)
    staging_path = staging_db_path(db_path)
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, rights_status) VALUES ('b1', 'T', 'public_domain')"
    )
    conn.execute(
        "INSERT INTO chunks (chunk_id, book_id, block_ids, section_path, text, "
        "char_start, char_end) VALUES ('c1', 'b1', '[]', '[]', 'text', 0, 4)"
    )
    conn.commit()
    conn.close()
    conn = connect(staging_path)
    conn.execute("CREATE TABLE chunks (chunk_id TEXT, book_id TEXT)")
    conn.execute("CREATE TABLE chunk_embeddings (chunk_id TEXT, embedding TEXT)")
    conn.execute("INSERT INTO chunks VALUES ('c1', 'b1')")
    conn.execute("INSERT INTO chunk_embeddings VALUES ('c1', ?)", (json.dumps([0.1, 0.2, 0.3]),))
    conn.commit()
    conn.close()
    conn = connect(db_path)
    conn.execute("ATTACH DATABASE ? AS staging", (str(staging_path),))
    mod._sync_chunk_embeddings(conn, indexable_book_ids={"b1"})
    conn.commit()
    row = conn.execute("SELECT embedding FROM chunk_embeddings WHERE chunk_id='c1'").fetchone()
    conn.close()
    assert row is not None and isinstance(row[0], bytes)
    assert struct.unpack("3f", row[0]) == pytest.approx((0.1, 0.2, 0.3))


def test_banned_sources_absent_from_ingest() -> None:
    patterns = (
        re.compile(r"\bimport\s+kaggle\b"),
        re.compile(r"kaggle\.com"),
        re.compile(r"libgen"),
        re.compile(r"sci-hub"),
        re.compile(r"annas-archive"),
    )
    offenders = []
    for path in INGEST_DIR.rglob("*.py"):
        if "tests" in path.relative_to(INGEST_DIR).parts:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line.lower()) for p in patterns):
                offenders.append(f"{path}:{i}")
    assert not offenders


@pytest.mark.slow
def test_chunk_ids_match_v1_snapshot(ingested_corpus_db: Path) -> None:
    expected_ids = sorted(expected_chunk_ids_from_snapshot(SNAPSHOT_PATH))
    assert hashlib.sha256("\n".join(expected_ids).encode()).hexdigest() == V1_CHUNK_IDS_SHA256
    conn = connect(ingested_corpus_db)
    loaded = {str(r[0]) for r in conn.execute("SELECT chunk_id FROM chunks")}
    gt = {
        json.loads(line)["chunk_id"]
        for line in GROUND_TRUTH_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert not gt - loaded
    assert loaded == set(expected_ids)
    conn.close()


@pytest.mark.slow
def test_second_run_no_duplicates(tmp_path: Path) -> None:
    db_path = _fresh_db(tmp_path)
    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)
    conn = connect(db_path)
    first = _corpus_counts(conn)
    conn.close()
    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)
    conn = connect(db_path)
    second = _corpus_counts(conn)
    conn.close()
    assert first == CANONICAL_COUNTS and second == first


@pytest.mark.slow
def test_metadata_only_never_indexed(tmp_path: Path) -> None:
    snapshot = tmp_path / "m.jsonl.gz"
    book_id = "metadata-only-book"
    _write_snapshot(snapshot, [_book(book_id)])
    db_path = _fresh_db(tmp_path)
    run_sqlite_pipeline(db_path, snapshot=snapshot, rights_by_book={book_id: "metadata_only"})
    conn = connect(db_path)
    assert (
        int(conn.execute("SELECT COUNT(*) FROM blocks WHERE book_id=?", (book_id,)).fetchone()[0])
        == 0
    )
    conn.close()


@pytest.mark.slow
def test_unknown_rights_fail_closed(tmp_path: Path) -> None:
    snapshot = tmp_path / "u.jsonl.gz"
    book_id = "unknown-rights-book"
    _write_snapshot(snapshot, [_book(book_id)])
    db_path = _fresh_db(tmp_path)
    run_sqlite_pipeline(db_path, snapshot=snapshot, rights_by_book={book_id: "unknown"})
    conn = connect(db_path)
    assert (
        int(conn.execute("SELECT COUNT(*) FROM chunks WHERE book_id=?", (book_id,)).fetchone()[0])
        == 0
    )
    conn.close()


@pytest.mark.slow
def test_rights_downgrade_purges_indexed_text(tmp_path: Path) -> None:
    snapshot = tmp_path / "d.jsonl.gz"
    book_id = "downgrade-book"
    _write_snapshot(snapshot, [_book(book_id)])
    db_path = _fresh_db(tmp_path)
    run_sqlite_pipeline(db_path, snapshot=snapshot, rights_by_book={book_id: "public_domain"})
    run_sqlite_pipeline(db_path, snapshot=snapshot, rights_by_book={book_id: "unknown"})
    conn = connect(db_path)
    assert (
        int(conn.execute("SELECT COUNT(*) FROM chunks WHERE book_id=?", (book_id,)).fetchone()[0])
        == 0
    )
    conn.close()


@pytest.mark.slow
def test_staging_file_removed_after_successful_sync(tmp_path: Path) -> None:
    db_path = _fresh_db(tmp_path)
    run_sqlite_pipeline(db_path, snapshot=SNAPSHOT_PATH)
    assert not staging_db_path(db_path).exists()


@pytest.mark.slow
def test_run_sqlite_pipeline_cleans_up_dlt_tmpdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: every run left a ``homelib_sqlite_dlt_<pid>`` dir in the OS
    temp directory (41 of them, ~8GB, found 2026-09-04). The dlt working dir is
    per-run scratch and must not outlive the run."""
    import tempfile

    scratch = tmp_path / "os-tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(scratch))
    snapshot = tmp_path / "c.jsonl.gz"
    book_id = "cleanup-book"
    _write_snapshot(snapshot, [_book(book_id)])

    run_sqlite_pipeline(
        _fresh_db(tmp_path), snapshot=snapshot, rights_by_book={book_id: "public_domain"}
    )

    assert not list(scratch.glob("homelib_sqlite_dlt_*")), sorted(scratch.iterdir())


# ── H2: the seed CLI the compose one-shot and the drill run ──────────────────


_CATALOG_HEADER = '{"_provenance": "test fixture"}\n'
_CATALOG_ROW = json.dumps(
    {
        "ol_key": "/works/OLTEST1W",
        "title": "Test Catalog Book",
        "authors": ["Fixture Author"],
        "subjects": ["testing"],
        "first_publish_year": 2001,
        "description": None,
        "provenance_note": "test fixture",
    }
)


def _write_catalog(path: Path) -> None:
    # dlt only creates staging.catalog when the resource yields a row, and the
    # sync step selects from it unconditionally — an empty file is not "no catalog".
    path.write_text(_CATALOG_HEADER + _CATALOG_ROW + "\n", encoding="utf-8")


def _write_manifest(path: Path, rights: dict[str, str]) -> None:
    path.write_text(
        "".join(
            f"- book_id: {book_id}\n  rights_status: {status}\n"
            for book_id, status in rights.items()
        ),
        encoding="utf-8",
    )


@pytest.mark.slow
def test_cli_main_seeds_db_and_reports_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`python -m apps.ingest.sqlite_pipeline` with env defaults only (the
    compose one-shot passes no argv): seeds the file named by
    HOMELIB_SQLITE_PATH, finds the manifest beside SNAPSHOT, prints counts,
    exits 0."""
    from apps.ingest.sqlite_pipeline import main

    data = tmp_path / "data"
    data.mkdir()
    _write_snapshot(data / "corpus_snapshot.jsonl.gz", [_book("cli-book")])
    _write_manifest(data / "manifest.yaml", {"cli-book": "public_domain"})
    _write_catalog(data / "catalog.jsonl")
    db = data / "homelib.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db))
    monkeypatch.setenv("SNAPSHOT", str(data / "corpus_snapshot.jsonl.gz"))
    monkeypatch.setenv("CATALOG", str(data / "catalog.jsonl"))
    monkeypatch.delenv("MANIFEST", raising=False)

    assert main([]) == 0

    report = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert report["books"] == 1
    assert report["chunks"] >= 1
    assert report["chunk_embeddings"] == report["chunks"]
    conn = connect(db)
    try:
        assert _corpus_counts(conn)["books"] == 1
    finally:
        conn.close()


@pytest.mark.slow
def test_cli_main_exits_nonzero_on_empty_seed(tmp_path: Path) -> None:
    """A seed that indexes nothing (every book rights-gated out) must fail
    loudly — an empty-but-migrated SQLite file is exactly what the API would
    otherwise happily serve as 'ok'."""
    from apps.ingest.sqlite_pipeline import main

    data = tmp_path / "data"
    data.mkdir()
    _write_snapshot(data / "corpus_snapshot.jsonl.gz", [_book("gated")])
    _write_manifest(data / "manifest.yaml", {"gated": "metadata_only"})
    _write_catalog(data / "catalog.jsonl")

    rc = main(
        [
            "--db",
            str(data / "homelib.sqlite"),
            "--snapshot",
            str(data / "corpus_snapshot.jsonl.gz"),
            "--catalog",
            str(data / "catalog.jsonl"),
            "--manifest",
            str(data / "manifest.yaml"),
        ]
    )
    assert rc == 1
