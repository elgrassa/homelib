"""dlt ingestion into SQLite — WP03; see specs/ingestion.md and ADR-004.

Mirrors the v1 Postgres ELT split: dlt owns a sibling staging database
(`<stem>__homelib_staging.sqlite`), then `_sync_staging_to_canonical` upserts
into the canonical tables created by `apps.store.sqlite` migrations. Rights are
enforced at sync time: only `public_domain` and `licensed_bundle` books get
blocks/chunks/embeddings.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

import dlt
import yaml
from dlt.common.pipeline import LoadInfo
from dlt.destinations import sqlalchemy
from dlt.destinations.impl.sqlalchemy.configuration import SqlalchemyCredentials
from dlt.pipeline.exceptions import PipelineStepFailed
from homelib_core.chunk import chunk_book
from homelib_core.models import BookDoc

from apps.ingest.pipeline import (
    DEFAULT_EMBED_MODEL,
    EMBED_DIM,
    STAGING_DATASET,
    _RUN_RETRY_ATTEMPTS,
    _RUN_RETRY_DELAY_SECONDS,
    homelib_source,
)
from apps.store.sqlite import can_index_text, connect, migrate

__all__ = [
    "CANONICAL_COUNTS",
    "REPO_ROOT",
    "SNAPSHOT_PATH",
    "CATALOG_PATH",
    "expected_chunk_ids_from_snapshot",
    "manifest_rights_by_book_id",
    "run_sqlite_pipeline",
    "staging_db_path",
]

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "data" / "corpus_snapshot.jsonl.gz"
CATALOG_PATH = REPO_ROOT / "data" / "catalog.jsonl"

CANONICAL_COUNTS: dict[str, int] = {
    "books": 18,
    "blocks": 729,
    "chunks": 9168,
    "chunk_embeddings": 9168,
}


def staging_db_path(canonical_db: Path) -> Path:
    """Path to the dlt-owned staging SQLite file for `canonical_db`."""
    return canonical_db.parent / f"{canonical_db.name}__{STAGING_DATASET}.sqlite"


def manifest_rights_by_book_id(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """Map manifest `book_id` → `rights_status` using the same rules as WP02 seed."""
    from apps.store.sqlite import _rights_status_from_manifest

    manifest_path = repo_root / "data" / "manifest.yaml"
    entries = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise TypeError("manifest.yaml must be a list")
    rights: dict[str, str] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            continue
        book_id = str(raw_entry["book_id"])
        rights[book_id] = _rights_status_from_manifest(raw_entry)
    return rights


def expected_chunk_ids_from_snapshot(snapshot: Path = SNAPSHOT_PATH) -> list[str]:
    """Deterministic v1 chunk ids from the committed snapshot (ground-truth guard)."""
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
    return dlt.pipeline(
        pipeline_name="homelib_sqlite_ingest",
        destination=sqlalchemy(credentials=credentials),
        dataset_name=STAGING_DATASET,
        pipelines_dir=str(
            Path(tempfile.gettempdir()) / f"homelib_sqlite_dlt_{os.getpid()}"
        ),
    )


def _json_list(value: Any) -> list[str]:
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _sync_books(
    conn: sqlite3.Connection,
    *,
    rights_by_book: dict[str, str],
) -> None:
    rows = conn.execute(
        "SELECT book_id, title, authors, language, source_url, license_note "
        "FROM staging.books"
    ).fetchall()
    for row in rows:
        book_id = str(row[0])
        rights_status = rights_by_book.get(book_id, "unknown")
        conn.execute(
            """
            INSERT INTO books (
                book_id, title, authors, language, source_url, license_note, rights_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (book_id) DO UPDATE SET
                title = excluded.title,
                authors = excluded.authors,
                language = excluded.language,
                source_url = excluded.source_url,
                license_note = excluded.license_note,
                rights_status = excluded.rights_status
            """,
            (
                book_id,
                row[1],
                row[2] if isinstance(row[2], str) else json.dumps(_json_list(row[2])),
                row[3],
                row[4],
                row[5],
                rights_status,
            ),
        )


def _sync_blocks(conn: sqlite3.Connection, *, indexable_book_ids: set[str]) -> None:
    if not indexable_book_ids:
        return
    placeholders = ",".join("?" for _ in indexable_book_ids)
    rows = conn.execute(
        f"""
        SELECT block_id, book_id, ordinal, section_path, text,
               char_start, char_end, format, page, spine_index, anchor
        FROM staging.blocks
        WHERE book_id IN ({placeholders})
        """,
        tuple(sorted(indexable_book_ids)),
    ).fetchall()
    for row in rows:
        section_path = row[3] if isinstance(row[3], str) else json.dumps(_json_list(row[3]))
        conn.execute(
            """
            INSERT INTO blocks (
                block_id, book_id, ordinal, section_path, text,
                char_start, char_end, format, page, spine_index, anchor
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (block_id) DO UPDATE SET
                book_id = excluded.book_id,
                ordinal = excluded.ordinal,
                section_path = excluded.section_path,
                text = excluded.text,
                char_start = excluded.char_start,
                char_end = excluded.char_end,
                format = excluded.format,
                page = excluded.page,
                spine_index = excluded.spine_index,
                anchor = excluded.anchor
            """,
            (
                row[0],
                row[1],
                row[2],
                section_path,
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
    placeholders = ",".join("?" for _ in indexable_book_ids)
    rows = conn.execute(
        f"""
        SELECT chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        FROM staging.chunks
        WHERE book_id IN ({placeholders})
        """,
        tuple(sorted(indexable_book_ids)),
    ).fetchall()
    for row in rows:
        block_ids = row[2] if isinstance(row[2], str) else json.dumps(_json_list(row[2]))
        section_path = row[3] if isinstance(row[3], str) else json.dumps(_json_list(row[3]))
        conn.execute(
            """
            INSERT INTO chunks (
                chunk_id, book_id, block_ids, section_path, text, char_start, char_end
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (chunk_id) DO UPDATE SET
                book_id = excluded.book_id,
                block_ids = excluded.block_ids,
                section_path = excluded.section_path,
                text = excluded.text,
                char_start = excluded.char_start,
                char_end = excluded.char_end
            """,
            (row[0], row[1], block_ids, section_path, row[4], row[5], row[6]),
        )


def _sync_chunk_embeddings(conn: sqlite3.Connection, *, indexable_book_ids: set[str]) -> None:
    if not indexable_book_ids:
        return
    placeholders = ",".join("?" for _ in indexable_book_ids)
    rows = conn.execute(
        f"""
        SELECT e.chunk_id, e.embedding
        FROM staging.chunk_embeddings e
        JOIN staging.chunks c ON c.chunk_id = e.chunk_id
        WHERE c.book_id IN ({placeholders})
        """,
        tuple(sorted(indexable_book_ids)),
    ).fetchall()
    for chunk_id, embedding in rows:
        if isinstance(embedding, str):
            embedding_json = embedding
        else:
            embedding_json = json.dumps(_json_list(embedding))
        conn.execute(
            """
            INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (chunk_id) DO UPDATE SET
                embedding = excluded.embedding,
                model = excluded.model,
                dim = excluded.dim
            """,
            (chunk_id, embedding_json, DEFAULT_EMBED_MODEL, EMBED_DIM),
        )


def _sync_catalog(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT ol_key, title, authors, subjects, first_publish_year, description, provenance_note
        FROM staging.catalog
        """
    ).fetchall()
    for row in rows:
        authors = row[2] if isinstance(row[2], str) else json.dumps(_json_list(row[2]))
        subjects = row[3] if isinstance(row[3], str) else json.dumps(_json_list(row[3]))
        conn.execute(
            """
            INSERT INTO catalog (
                ol_key, title, authors, subjects, first_publish_year, description, provenance_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (ol_key) DO UPDATE SET
                title = excluded.title,
                authors = excluded.authors,
                subjects = excluded.subjects,
                first_publish_year = excluded.first_publish_year,
                description = excluded.description,
                provenance_note = excluded.provenance_note
            """,
            (row[0], row[1], authors, subjects, row[4], row[5], row[6]),
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
        conn.execute("BEGIN")
        _sync_books(conn, rights_by_book=rights_by_book)
        _sync_blocks(conn, indexable_book_ids=indexable_book_ids)
        _sync_chunks(conn, indexable_book_ids=indexable_book_ids)
        _sync_chunk_embeddings(conn, indexable_book_ids=indexable_book_ids)
        _sync_catalog(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("DETACH DATABASE staging")
        conn.close()


def _run_with_retry(pipeline: dlt.Pipeline, snapshot: Path, catalog: Path) -> LoadInfo:
    last_error: Exception | None = None
    for attempt in range(1, _RUN_RETRY_ATTEMPTS + 1):
        pipeline.abort_packages()
        try:
            return pipeline.run(homelib_source(snapshot, catalog))
        except FileNotFoundError as exc:
            last_error = exc
            logger.warning("sqlite pipeline.run attempt %d failed: %s", attempt, exc)
        except PipelineStepFailed as exc:
            if not isinstance(exc.__cause__, FileNotFoundError):
                raise
            last_error = exc
            logger.warning("sqlite pipeline.run attempt %d failed: %s", attempt, exc)
        time.sleep(_RUN_RETRY_DELAY_SECONDS)
    assert last_error is not None
    raise last_error


def run_sqlite_pipeline(
    db_path: Path,
    *,
    snapshot: Path = SNAPSHOT_PATH,
    catalog: Path = CATALOG_PATH,
    repo_root: Path = REPO_ROOT,
    rights_by_book: dict[str, str] | None = None,
) -> LoadInfo:
    """Load the corpus snapshot into `db_path` via dlt → SQLite staging → canonical."""
    conn = connect(db_path)
    migrate(conn)
    conn.close()

    resolved_rights = (
        rights_by_book if rights_by_book is not None else manifest_rights_by_book_id(repo_root)
    )
    pipeline = _make_pipeline(db_path)
    info = _run_with_retry(pipeline, snapshot, catalog)
    _sync_staging_to_canonical(db_path, rights_by_book=resolved_rights)
    return info
