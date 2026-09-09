"""dlt ingestion into SQLite — WP03; see specs/ingestion.md and ADR-004."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import struct
import sys
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import dlt
import yaml
from dlt.common.pipeline import LoadInfo
from dlt.destinations import sqlalchemy
from dlt.destinations.impl.sqlalchemy.configuration import SqlalchemyCredentials
from dlt.extract import DltResource
from homelib_core.chunk import chunk_book
from homelib_core.models import BookDoc

from apps.ingest.pipeline import (
    _CHUNK_EMBED_BATCH,
    DEFAULT_EMBED_MODEL,
    EMBED_DIM,
    STAGING_DATASET,
    _iter_books,
    _run_with_retry,
    blocks_resource,
    books_resource,
    catalog_resource,
    chunks_resource,
    embed_texts,
)
from apps.store.sqlite import (
    can_index_text,
    connect,
    migrate,
    rights_status_from_manifest,
    row_counts,
)

__all__ = [
    "CANONICAL_COUNTS",
    "CATALOG_PATH",
    "REPO_ROOT",
    "SNAPSHOT_PATH",
    "expected_chunk_ids_from_snapshot",
    "main",
    "manifest_rights_by_book_id",
    "manifest_rights_from_path",
    "run_sqlite_pipeline",
    "staging_db_path",
]

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "data" / "corpus_snapshot.jsonl.gz"
CATALOG_PATH = REPO_ROOT / "data" / "catalog.jsonl"

CANONICAL_COUNTS: dict[str, int] = {
    "books": 18,
    "blocks": 627,
    "chunks": 9119,
    "chunk_embeddings": 9119,
}


def _serialize_lists(row: dict[str, Any], *, list_fields: tuple[str, ...]) -> dict[str, Any]:
    serialized = dict(row)
    for field in list_fields:
        value = serialized.get(field)
        if isinstance(value, list):
            serialized[field] = json.dumps(value)
    return serialized


@dlt.resource(name="books", write_disposition="replace", primary_key="book_id")
def sqlite_books_resource(snapshot: Path) -> Iterator[dict[str, Any]]:
    for row in books_resource(snapshot):
        yield _serialize_lists(row, list_fields=("authors",))


@dlt.resource(
    name="blocks",
    write_disposition="replace",
    primary_key="block_id",
    columns={
        "section_path": {"data_type": "text"},
        "page": {"data_type": "bigint"},
        "spine_index": {"data_type": "bigint"},
        "anchor": {"data_type": "text"},
    },
)
def sqlite_blocks_resource(snapshot: Path) -> Iterator[dict[str, Any]]:
    for row in blocks_resource(snapshot):
        yield _serialize_lists(row, list_fields=("section_path",))


@dlt.resource(name="chunks", write_disposition="replace", primary_key="chunk_id")
def sqlite_chunks_resource(snapshot: Path) -> Iterator[dict[str, Any]]:
    for row in chunks_resource(snapshot):
        yield _serialize_lists(row, list_fields=("block_ids", "section_path"))


@dlt.resource(
    name="chunk_embeddings",
    write_disposition="replace",
    primary_key="chunk_id",
    columns={"embedding": {"data_type": "text"}},
)
def sqlite_chunk_embeddings_resource(snapshot: Path) -> Iterator[dict[str, Any]]:
    ids: list[str] = []
    texts: list[str] = []
    for doc in _iter_books(snapshot):
        for chunk in chunk_book(doc):
            ids.append(chunk.chunk_id)
            texts.append(chunk.text)
            if len(ids) >= _CHUNK_EMBED_BATCH:
                vectors = embed_texts(texts)
                for chunk_id, vector in zip(ids, vectors, strict=True):
                    yield {"chunk_id": chunk_id, "embedding": json.dumps(vector)}
                ids, texts = [], []
    if ids:
        vectors = embed_texts(texts)
        for chunk_id, vector in zip(ids, vectors, strict=True):
            yield {"chunk_id": chunk_id, "embedding": json.dumps(vector)}


@dlt.resource(
    name="catalog",
    write_disposition="replace",
    primary_key="ol_key",
    columns={"description": {"data_type": "text"}},
)
def sqlite_catalog_resource(catalog: Path) -> Iterator[dict[str, Any]]:
    for row in catalog_resource(catalog):
        yield _serialize_lists(row, list_fields=("authors", "subjects"))


@dlt.source
def sqlite_homelib_source(snapshot: Path, catalog: Path) -> Iterable[DltResource]:
    return [
        sqlite_books_resource(snapshot),
        sqlite_blocks_resource(snapshot),
        sqlite_chunks_resource(snapshot),
        sqlite_chunk_embeddings_resource(snapshot),
        sqlite_catalog_resource(catalog),
    ]


def staging_db_path(canonical_db: Path) -> Path:
    return canonical_db.parent / f"{canonical_db.stem}__{STAGING_DATASET}.sqlite"


def manifest_rights_by_book_id(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    return manifest_rights_from_path(repo_root / "data" / "manifest.yaml")


def manifest_rights_from_path(manifest_path: Path) -> dict[str, str]:
    """`book_id -> rights_status` from a manifest file. Split out from the
    repo-root form because the compose ingest image copies `apps/` and
    `packages/` but mounts `data/` at `/data` — there is no `/app/data`."""
    entries = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise TypeError("manifest.yaml must be a list")
    rights: dict[str, str] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            continue
        book_id = str(raw_entry["book_id"])
        rights[book_id] = rights_status_from_manifest(raw_entry)
    return rights


def expected_chunk_ids_from_snapshot(snapshot: Path = SNAPSHOT_PATH) -> list[str]:
    rights_by_book = manifest_rights_by_book_id()
    chunk_ids: list[str] = []
    with gzip.open(snapshot, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            doc = BookDoc.model_validate_json(line)
            rights = rights_by_book.get(doc.book_id, "unknown")
            if not can_index_text(rights):
                continue
            chunk_ids.extend(chunk.chunk_id for chunk in chunk_book(doc))
    return chunk_ids


def _make_pipeline(canonical_db: Path) -> dlt.Pipeline:
    credentials = SqlalchemyCredentials(f"sqlite:///{canonical_db}")
    pipeline_token = hashlib.sha256(str(canonical_db).encode()).hexdigest()[:16]
    return dlt.pipeline(
        pipeline_name=f"homelib_sqlite_ingest_{pipeline_token}",
        destination=sqlalchemy(credentials=credentials),
        dataset_name=STAGING_DATASET,
        pipelines_dir=str(Path(tempfile.gettempdir()) / f"homelib_sqlite_dlt_{os.getpid()}"),
    )


def _embedding_json_to_blob(embedding: Any) -> bytes:
    if isinstance(embedding, (bytes, bytearray)):
        return bytes(embedding)
    if isinstance(embedding, str):
        vector = json.loads(embedding)
    elif isinstance(embedding, list):
        vector = embedding
    else:
        raise TypeError(f"unsupported embedding type: {type(embedding)!r}")
    return struct.pack(f"{len(vector)}f", *vector)


def _book_id_in_clause(indexable_book_ids: set[str]) -> tuple[str, tuple[str, ...]]:
    if not indexable_book_ids:
        return "NULL", ()
    placeholders = ", ".join("?" for _ in indexable_book_ids)
    return placeholders, tuple(sorted(indexable_book_ids))


def _purge_non_indexable_corpus(conn: sqlite3.Connection, *, indexable_book_ids: set[str]) -> None:
    placeholders, params = _book_id_in_clause(indexable_book_ids)
    if params:
        conn.execute(
            f"DELETE FROM chunk_embeddings WHERE chunk_id IN "
            f"(SELECT chunk_id FROM chunks WHERE book_id NOT IN ({placeholders}))",
            params,
        )
        conn.execute(f"DELETE FROM chunks WHERE book_id NOT IN ({placeholders})", params)
        conn.execute(f"DELETE FROM blocks WHERE book_id NOT IN ({placeholders})", params)
        return
    conn.execute("DELETE FROM chunk_embeddings")
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM blocks")


def _purge_stale_corpus_rows(conn: sqlite3.Connection) -> None:
    """Remove canonical rows whose regenerated IDs disappeared from staging."""
    conn.execute(
        "DELETE FROM chunk_embeddings WHERE NOT EXISTS "
        "(SELECT 1 FROM staging.chunk_embeddings AS incoming "
        "WHERE incoming.chunk_id = chunk_embeddings.chunk_id)"
    )
    conn.execute(
        "DELETE FROM chunks WHERE NOT EXISTS "
        "(SELECT 1 FROM staging.chunks AS incoming WHERE incoming.chunk_id = chunks.chunk_id)"
    )
    conn.execute(
        "DELETE FROM blocks WHERE NOT EXISTS "
        "(SELECT 1 FROM staging.blocks AS incoming WHERE incoming.block_id = blocks.block_id)"
    )


def _sync_books(conn: sqlite3.Connection, *, rights_by_book: dict[str, str]) -> None:
    rows = conn.execute(
        "SELECT book_id, title, authors, language, source_url, license_note FROM staging.books"
    ).fetchall()
    for row in rows:
        book_id = str(row[0])
        conn.execute(
            """
            INSERT INTO books (
                book_id, title, authors, language, source_url, license_note, rights_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (book_id) DO UPDATE SET
                title = excluded.title, authors = excluded.authors,
                language = excluded.language, source_url = excluded.source_url,
                license_note = excluded.license_note, rights_status = excluded.rights_status
            """,
            (
                book_id,
                row[1],
                str(row[2]),
                row[3],
                row[4],
                row[5],
                rights_by_book.get(book_id, "unknown"),
            ),
        )


def _sync_blocks(conn: sqlite3.Connection, *, indexable_book_ids: set[str]) -> None:
    if not indexable_book_ids:
        return
    placeholders, params = _book_id_in_clause(indexable_book_ids)
    rows = conn.execute(
        f"""
        SELECT block_id, book_id, ordinal, section_path, text,
               char_start, char_end, format, page, spine_index, anchor
        FROM staging.blocks WHERE book_id IN ({placeholders})
        """,
        params,
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT INTO blocks (
                block_id, book_id, ordinal, section_path, text,
                char_start, char_end, format, page, spine_index, anchor
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (block_id) DO UPDATE SET
                book_id = excluded.book_id, ordinal = excluded.ordinal,
                section_path = excluded.section_path, text = excluded.text,
                char_start = excluded.char_start, char_end = excluded.char_end,
                format = excluded.format, page = excluded.page,
                spine_index = excluded.spine_index, anchor = excluded.anchor
            """,
            (
                row[0],
                row[1],
                row[2],
                str(row[3]),
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
                row[10],
            ),
        )


def _sync_chunks(conn: sqlite3.Connection, *, indexable_book_ids: set[str]) -> None:
    if not indexable_book_ids:
        return
    placeholders, params = _book_id_in_clause(indexable_book_ids)
    rows = conn.execute(
        f"""
        SELECT chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        FROM staging.chunks WHERE book_id IN ({placeholders})
        """,
        params,
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT INTO chunks (
                chunk_id, book_id, block_ids, section_path, text, char_start, char_end
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (chunk_id) DO UPDATE SET
                book_id = excluded.book_id, block_ids = excluded.block_ids,
                section_path = excluded.section_path, text = excluded.text,
                char_start = excluded.char_start, char_end = excluded.char_end
            """,
            (row[0], row[1], str(row[2]), str(row[3]), row[4], row[5], row[6]),
        )


def _sync_chunk_embeddings(conn: sqlite3.Connection, *, indexable_book_ids: set[str]) -> None:
    if not indexable_book_ids:
        return
    placeholders, params = _book_id_in_clause(indexable_book_ids)
    rows = conn.execute(
        f"""
        SELECT e.chunk_id, e.embedding
        FROM staging.chunk_embeddings e
        JOIN staging.chunks c ON c.chunk_id = e.chunk_id
        WHERE c.book_id IN ({placeholders})
        """,
        params,
    ).fetchall()
    for chunk_id, embedding in rows:
        conn.execute(
            """
            INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (chunk_id) DO UPDATE SET
                embedding = excluded.embedding, model = excluded.model, dim = excluded.dim
            """,
            (chunk_id, _embedding_json_to_blob(embedding), DEFAULT_EMBED_MODEL, EMBED_DIM),
        )


def _sync_catalog(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT ol_key, title, authors, subjects, first_publish_year, description, provenance_note
        FROM staging.catalog
        """
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT INTO catalog (
                ol_key, title, authors, subjects, first_publish_year, description, provenance_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (ol_key) DO UPDATE SET
                title = excluded.title, authors = excluded.authors,
                subjects = excluded.subjects, first_publish_year = excluded.first_publish_year,
                description = excluded.description, provenance_note = excluded.provenance_note
            """,
            (row[0], row[1], str(row[2]), str(row[3]), row[4], row[5], row[6]),
        )


def _sync_staging_to_canonical(
    canonical_db: Path,
    *,
    rights_by_book: dict[str, str],
) -> None:
    staging_path = staging_db_path(canonical_db)
    if not staging_path.exists():
        raise FileNotFoundError(f"dlt staging database missing: {staging_path}")

    indexable_book_ids = {
        book_id for book_id, status in rights_by_book.items() if can_index_text(status)
    }

    conn = connect(canonical_db)
    try:
        conn.execute("ATTACH DATABASE ? AS staging", (str(staging_path),))
        with conn:
            _sync_books(conn, rights_by_book=rights_by_book)
            _purge_non_indexable_corpus(conn, indexable_book_ids=indexable_book_ids)
            _purge_stale_corpus_rows(conn)
            _sync_blocks(conn, indexable_book_ids=indexable_book_ids)
            _sync_chunks(conn, indexable_book_ids=indexable_book_ids)
            _sync_chunk_embeddings(conn, indexable_book_ids=indexable_book_ids)
            _sync_catalog(conn)
            from apps.store.sqlite import bump_index_revision, rebuild_chunks_fts

            rebuild_chunks_fts(conn)
            bump_index_revision(conn)
    finally:
        try:
            conn.execute("DETACH DATABASE staging")
        finally:
            conn.close()

    staging_path.unlink(missing_ok=True)


def run_sqlite_pipeline(
    db_path: Path,
    *,
    snapshot: Path = SNAPSHOT_PATH,
    catalog: Path = CATALOG_PATH,
    repo_root: Path = REPO_ROOT,
    rights_by_book: dict[str, str] | None = None,
) -> LoadInfo:
    conn = connect(db_path)
    migrate(conn)
    conn.close()

    resolved_rights = (
        rights_by_book if rights_by_book is not None else manifest_rights_by_book_id(repo_root)
    )
    pipeline = _make_pipeline(db_path)
    try:
        info = _run_with_retry(
            pipeline,
            snapshot,
            catalog,
            source=sqlite_homelib_source(snapshot, catalog),
        )
        _sync_staging_to_canonical(db_path, rights_by_book=resolved_rights)
    finally:
        # The dlt working dir is per-run scratch under the OS temp dir. Left in
        # place it never goes away (41 dirs / ~8GB found on 2026-09-04).
        shutil.rmtree(pipeline.pipelines_dir, ignore_errors=True)
    return info


# ── CLI ──────────────────────────────────────────────────────────────────────
#
# `python -m apps.ingest.sqlite_pipeline` is what `just seed-sqlite` and the
# cold-clone drill run inside the compose `ingest` one-shot. Every argument
# has an environment default so the container needs no argv: SNAPSHOT /
# CATALOG are the same variables the Postgres pipeline reads, the manifest is
# looked up beside the snapshot (both live under the mounted /data), and the
# database is HOMELIB_SQLITE_PATH — the exact file the API opens.
#
# Exit 1 on a seed that produced no indexable chunks: a silent success here
# is the bug this CLI exists to close (the API creates an empty schema on
# first connect, so "the file exists" proves nothing).

_SEED_REPORT_KEYS = ("books", "blocks", "chunks", "chunk_embeddings", "catalog")


def _default_db_path() -> Path:
    raw = os.environ.get("HOMELIB_SQLITE_PATH", "").strip()
    return Path(raw) if raw else REPO_ROOT / "data" / "homelib.sqlite"


def _default_manifest_path(snapshot: Path) -> Path:
    raw = os.environ.get("MANIFEST", "").strip()
    if raw:
        return Path(raw)
    beside_snapshot = snapshot.parent / "manifest.yaml"
    if beside_snapshot.exists():
        return beside_snapshot
    return REPO_ROOT / "data" / "manifest.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m apps.ingest.sqlite_pipeline",
        description="dlt ingestion of the committed corpus snapshot + catalog into SQLite.",
    )
    snapshot_default = Path(os.environ.get("SNAPSHOT", str(SNAPSHOT_PATH)))
    parser.add_argument("--db", type=Path, default=_default_db_path())
    parser.add_argument("--snapshot", type=Path, default=snapshot_default)
    parser.add_argument(
        "--catalog", type=Path, default=Path(os.environ.get("CATALOG", str(CATALOG_PATH)))
    )
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args(argv)
    manifest: Path = args.manifest or _default_manifest_path(args.snapshot)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rights_by_book = manifest_rights_from_path(manifest)
    run_sqlite_pipeline(
        args.db, snapshot=args.snapshot, catalog=args.catalog, rights_by_book=rights_by_book
    )

    conn = connect(args.db)
    try:
        counts = row_counts(conn)
    finally:
        conn.close()
    report = {key: counts.get(key, 0) for key in _SEED_REPORT_KEYS}
    print(json.dumps({"db": str(args.db), **report}))
    if report["books"] == 0 or report["chunks"] == 0:
        print(
            f"seed produced no indexable corpus in {args.db} "
            f"(books={report['books']}, chunks={report['chunks']})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
