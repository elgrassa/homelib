"""SQLite FTS5 + cached NumPy embedding matrix — see specs/indexing.md, ADR-004."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from homelib_rag.models import Hit

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["search_lexical", "search_vector", "sqlite_path"]

_DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_EMBED_DIM = 384

_embed_lock = threading.Lock()
_embedder: Any = None
_matrix_lock = threading.Lock()
_matrix_cache: _MatrixCache | None = None


@dataclass(frozen=True, slots=True)
class _MatrixCache:
    revision: str
    chunk_ids: list[str]
    matrix: NDArray[np.float32]


def sqlite_path() -> Path | None:
    raw = os.environ.get("HOMELIB_SQLITE_PATH", "").strip()
    return Path(raw) if raw else None


def _connect() -> sqlite3.Connection:
    path = sqlite_path()
    if path is None:
        raise RuntimeError("HOMELIB_SQLITE_PATH is not set")
    from apps.store.sqlite import connect, migrate

    conn = connect(path)
    migrate(conn)
    return conn


def _validate(q: str, k: int) -> None:
    if not q.strip():
        raise ValueError("q must not be empty")
    if k <= 0:
        raise ValueError("k must be positive")


def _fts_query(q: str) -> str:
    tokens = re.findall(r"\w+", q, flags=re.UNICODE)
    if not tokens:
        raise ValueError("q must not be empty")
    return " ".join(f'"{token}"' for token in tokens)


def _json_list(raw: str) -> list[str]:
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise TypeError(f"expected JSON list, got {type(parsed)!r}")
    return [str(item) for item in parsed]


def _first_page(conn: sqlite3.Connection, block_ids: list[str]) -> int | None:
    if not block_ids:
        return None
    placeholders = ",".join("?" for _ in block_ids)
    rows = conn.execute(
        f"SELECT block_id, page FROM blocks WHERE block_id IN ({placeholders})",  # noqa: S608
        block_ids,
    ).fetchall()
    page_by_block = {str(row[0]): row[1] for row in rows}
    for block_id in block_ids:
        page = page_by_block.get(block_id)
        if page is not None:
            return int(page)
    return None


def _row_to_hit(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    rank: int,
    score: float,
) -> Hit:
    block_ids = _json_list(str(row["block_ids"]))
    section_path = _json_list(str(row["section_path"]))
    return Hit(
        chunk_id=str(row["chunk_id"]),
        book_id=str(row["book_id"]),
        score=float(score),
        rank=rank,
        text=str(row["text"]),
        section_path=section_path,
        page=_first_page(conn, block_ids),
        block_ids=block_ids,
    )


def search_lexical(
    q: str,
    k: int,
    *,
    book_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[Hit]:
    _validate(q, k)
    owns_conn = conn is None
    db = _connect() if owns_conn else conn
    assert db is not None
    try:
        fts_q = _fts_query(q)
        params: list[Any] = [fts_q]
        sql = """
            SELECT c.chunk_id, c.book_id, c.block_ids, c.section_path, c.text,
                   bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
        """
        if book_id is not None:
            sql += " AND c.book_id = ?"
            params.append(book_id)
        sql += " ORDER BY score LIMIT ?"
        params.append(k)
        rows = db.execute(sql, params).fetchall()
        return [
            _row_to_hit(db, row, rank=rank, score=-float(row["score"]))
            for rank, row in enumerate(rows, start=1)
        ]
    finally:
        if owns_conn:
            db.close()


def _load_embedder() -> Any:
    global _embedder
    if _embedder is not None:
        return _embedder
    with _embed_lock:
        if _embedder is None:
            from sentence_transformers import SentenceTransformer

            model_name = os.environ.get("EMBED_MODEL", _DEFAULT_EMBED_MODEL)
            _embedder = SentenceTransformer(model_name)
        return _embedder


def _embed_query(q: str) -> NDArray[np.float32]:
    model = _load_embedder()
    vector: NDArray[Any] = model.encode(q)
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr
    return arr / norm


def _load_matrix(conn: sqlite3.Connection) -> _MatrixCache:
    global _matrix_cache
    from apps.store.sqlite import current_index_revision

    revision = current_index_revision(conn)
    if _matrix_cache is not None and _matrix_cache.revision == revision:
        return _matrix_cache

    with _matrix_lock:
        if _matrix_cache is not None and _matrix_cache.revision == revision:
            return _matrix_cache
        rows = conn.execute(
            """
            SELECT e.chunk_id, e.embedding
            FROM chunk_embeddings e
            JOIN chunks c ON c.chunk_id = e.chunk_id
            ORDER BY e.chunk_id
            """
        ).fetchall()
        chunk_ids: list[str] = []
        vectors: list[NDArray[np.float32]] = []
        for chunk_id, embedding_json in rows:
            raw = json.loads(str(embedding_json))
            arr = np.asarray(raw, dtype=np.float32)
            norm = float(np.linalg.norm(arr))
            if norm > 0.0:
                arr = arr / norm
            chunk_ids.append(str(chunk_id))
            vectors.append(arr)
        matrix = np.vstack(vectors) if vectors else np.empty((0, _EMBED_DIM), dtype=np.float32)
        _matrix_cache = _MatrixCache(revision=revision, chunk_ids=chunk_ids, matrix=matrix)
        return _matrix_cache


def _reset_caches_for_tests() -> None:
    global _embedder, _matrix_cache
    with _embed_lock:
        _embedder = None
    with _matrix_lock:
        _matrix_cache = None


def search_vector(
    q: str,
    k: int,
    *,
    book_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[Hit]:
    _validate(q, k)
    owns_conn = conn is None
    db = _connect() if owns_conn else conn
    assert db is not None
    try:
        cache = _load_matrix(db)
        if cache.matrix.shape[0] == 0:
            return []
        query_vec = _embed_query(q)
        scores = cache.matrix @ query_vec
        ranked_idx = np.argsort(scores)[::-1]

        hits: list[Hit] = []
        for idx in ranked_idx:
            if len(hits) >= k:
                break
            chunk_id = cache.chunk_ids[int(idx)]
            row = db.execute(
                """
                SELECT chunk_id, book_id, block_ids, section_path, text
                FROM chunks WHERE chunk_id = ?
                """,
                (chunk_id,),
            ).fetchone()
            if row is None:
                continue
            if book_id is not None and str(row["book_id"]) != book_id:
                continue
            hits.append(
                _row_to_hit(
                    db,
                    row,
                    rank=len(hits) + 1,
                    score=float(scores[int(idx)]),
                )
            )
        return hits
    finally:
        if owns_conn:
            db.close()
