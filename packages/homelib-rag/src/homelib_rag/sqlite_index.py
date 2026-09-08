"""SQLite FTS5 + cached NumPy embedding matrix — see specs/indexing.md, ADR-004."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from homelib_core.models import CatalogEntry

from homelib_rag.models import Hit

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = [
    "book_metadata",
    "browse_catalog",
    "catalog_row_count",
    "search_catalog",
    "search_lexical",
    "search_vector",
    "sqlite_path",
]

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


# Align with Postgres `plainto_tsquery('english', …)`: drop function words so
# a question like "What is compound interest?" becomes compound & interest,
# not a mandatory AND over "What"/"is" that matches almost nothing in FTS5.
_FTS_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
        "how",
        "does",
        "did",
        "do",
        "can",
        "could",
        "would",
        "should",
        "about",
    }
)


def _fts_content_tokens(q: str) -> list[str]:
    tokens = [
        token
        for token in re.findall(r"\w+", q, flags=re.UNICODE)
        if token.lower() not in _FTS_STOPWORDS and len(token) > 1
    ]
    if not tokens:
        # Fall back to raw tokens so a stopword-only query still errors clearly
        # only when nothing alphanumeric remains at all.
        tokens = re.findall(r"\w+", q, flags=re.UNICODE)
    if not tokens:
        raise ValueError("q must not be empty")
    return tokens


def _fts_query(q: str) -> str:
    """FTS5 AND of content tokens (space-separated quoted terms)."""
    return " ".join(f'"{token}"' for token in _fts_content_tokens(q))


def _fts_query_or(q: str) -> str:
    """FTS5 OR of content tokens — used when AND matches nothing."""
    return " OR ".join(f'"{token}"' for token in _fts_content_tokens(q))


def _decode_embedding(raw: object) -> NDArray[np.float32]:
    """Decode a stored embedding: float32 BLOB (ingest) or JSON list (unit fixtures)."""
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if isinstance(raw, (bytes, bytearray)):
        arr = np.frombuffer(bytes(raw), dtype=np.float32).copy()
    elif isinstance(raw, str):
        parsed = json.loads(raw)
        arr = np.asarray(parsed, dtype=np.float32)
    elif isinstance(raw, list):
        arr = np.asarray(raw, dtype=np.float32)
    else:
        raise TypeError(f"unsupported embedding type: {type(raw)!r}")
    if arr.ndim != 1:
        raise ValueError(f"embedding must be 1-D, got shape {arr.shape}")
    return arr


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


def _lexical_rows(
    db: sqlite3.Connection,
    fts_q: str,
    *,
    book_id: str | None,
    k: int,
) -> list[Any]:
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
    return db.execute(sql, params).fetchall()


def _term_overlap(text: str, tokens: list[str]) -> int:
    lower = text.lower()
    return sum(1 for token in tokens if token.lower() in lower)


def _earliest_matched_token_index(text: str, tokens: list[str]) -> int:
    """Index of the first query token that appears in ``text`` (or len(tokens)).

    Used only for OR-fallback tie-breaks so ``money described`` prefers the
    money passage over a strong BM25 hit on the filler word alone.
    """
    lower = text.lower()
    for index, token in enumerate(tokens):
        if token.lower() in lower:
            return index
    return len(tokens)


def search_lexical(
    q: str,
    k: int,
    *,
    book_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[Hit]:
    """BM25 over FTS5.

    Prefer an AND of content tokens (precise). When that returns nothing and
    the query has multiple content tokens — e.g. ``money described`` with no
    chunk holding both words — fall back to OR, then re-rank by how many
    query terms appear in the passage so a rare filler word ("described")
    cannot bury the topical term ("money"). Related semantic hits stay the
    vector arm's job; this only stops lexical from going silent.
    """
    _validate(q, k)
    owns_conn = conn is None
    db = _connect() if owns_conn else conn
    assert db is not None
    try:
        tokens = _fts_content_tokens(q)
        rows = _lexical_rows(db, _fts_query(q), book_id=book_id, k=k)
        if not rows and len(tokens) > 1:
            # Pull a wider OR pool, then prefer multi-term overlap.
            pool = _lexical_rows(db, _fts_query_or(q), book_id=book_id, k=max(k * len(tokens), k))
            ranked = sorted(
                pool,
                key=lambda row: (
                    -_term_overlap(str(row["text"]), tokens),
                    _earliest_matched_token_index(str(row["text"]), tokens),
                    float(row["score"]),  # bm25: more negative is better
                ),
            )
            rows = ranked[:k]
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
        for chunk_id, embedding_raw in rows:
            arr = _decode_embedding(embedding_raw)
            if arr.shape[0] != _EMBED_DIM:
                raise ValueError(
                    f"embedding dim {arr.shape[0]} != {_EMBED_DIM} for chunk {chunk_id}"
                )
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


# ── Metadata lookups (the SQLite side of the seams in answer.py / agent.py) ──
#
# `answer._book_metadata` and `agent.search_catalog` were Postgres-only while
# retrieval already dispatched here on HOMELIB_SQLITE_PATH — so on a SQLite-only
# host every ask came back degraded ("failed to load book metadata") after a
# perfectly good retrieval. Both seams now dispatch to these on the same env
# predicate as `search_lexical`/`search_vector` (ADR-004).

_MAX_CATALOG_RESULTS = 20
_MAX_DISCOVER_BROWSE = 100


def _json_list_or_empty(raw: object) -> list[str]:
    if raw is None:
        return []
    try:
        return _json_list(str(raw))
    except (TypeError, ValueError):
        return []


def book_metadata(
    book_ids: Sequence[str], *, conn: sqlite3.Connection | None = None
) -> dict[str, tuple[str, list[str]]]:
    """`book_id -> (title, authors)` from the SQLite `books` table.

    `authors` is stored as JSON text (default `'[]'`); a malformed value
    decodes to `[]` rather than failing the whole answer — the title is the
    load-bearing part of the citation, the author list is context.
    """
    ids = sorted({str(b) for b in book_ids})
    if not ids:
        return {}
    owns_conn = conn is None
    db = _connect() if owns_conn else conn
    assert db is not None
    try:
        placeholders = ",".join("?" for _ in ids)
        rows = db.execute(
            f"SELECT book_id, title, authors FROM books WHERE book_id IN ({placeholders})",  # noqa: S608
            ids,
        ).fetchall()
        return {str(row[0]): (str(row[1]), _json_list_or_empty(row[2])) for row in rows}
    finally:
        if owns_conn:
            db.close()


def search_catalog(
    query: str,
    subjects: Sequence[str] | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[CatalogEntry]:
    """SQLite twin of `homelib_rag.agent.search_catalog`: subject overlap when
    `subjects` is given, otherwise a case-insensitive title/subject substring
    match. `authors`/`subjects` are JSON text columns and are decoded here.
    """
    if not query.strip():
        raise ValueError("query must not be empty")
    owns_conn = conn is None
    db = _connect() if owns_conn else conn
    assert db is not None
    try:
        rows = db.execute(
            """
            SELECT ol_key, title, authors, subjects, first_publish_year,
                   description, provenance_note
            FROM catalog
            """
        ).fetchall()
    finally:
        if owns_conn:
            db.close()

    wanted = {s.lower() for s in subjects} if subjects else None
    needle = query.lower()
    out: list[CatalogEntry] = []
    for row in rows:
        entry_subjects = _json_list_or_empty(row[3])
        if wanted is not None:
            if not any(s.lower() in wanted for s in entry_subjects):
                continue
        elif needle not in str(row[1]).lower() and not any(
            needle in s.lower() for s in entry_subjects
        ):
            continue
        out.append(
            CatalogEntry(
                ol_key=str(row[0]),
                title=str(row[1]),
                authors=_json_list_or_empty(row[2]),
                subjects=entry_subjects,
                first_publish_year=row[4],
                description=row[5],
                provenance_note=str(row[6] or ""),
            )
        )
        if len(out) >= _MAX_CATALOG_RESULTS:
            break
    return out


def catalog_row_count(*, conn: sqlite3.Connection | None = None) -> int:
    """Total rows in the seeded Open Library catalog snapshot."""
    owns_conn = conn is None
    db = _connect() if owns_conn else conn
    assert db is not None
    try:
        row = db.execute("SELECT COUNT(*) FROM catalog").fetchone()
        return int(row[0]) if row else 0
    finally:
        if owns_conn:
            db.close()


def browse_catalog(
    query: str | None = None,
    *,
    limit: int = 50,
    offset: int = 0,
    conn: sqlite3.Connection | None = None,
) -> tuple[list[CatalogEntry], int]:
    """Discover browse over the committed catalog table (empty query = title order).

    Unlike `search_catalog`, empty/whitespace `query` is allowed. Returns
    ``(page, match_count)``.
    """
    capped = max(1, min(int(limit), _MAX_DISCOVER_BROWSE))
    start = max(0, int(offset))
    owns_conn = conn is None
    db = _connect() if owns_conn else conn
    assert db is not None
    needle = (query or "").strip().lower()
    try:
        rows = db.execute(
            """
            SELECT ol_key, title, authors, subjects, first_publish_year,
                   description, provenance_note
            FROM catalog
            ORDER BY title COLLATE NOCASE
            """
        ).fetchall()
    finally:
        if owns_conn:
            db.close()

    matched: list[CatalogEntry] = []
    for row in rows:
        entry_subjects = _json_list_or_empty(row[3])
        if (
            needle
            and needle not in str(row[1]).lower()
            and not any(needle in s.lower() for s in entry_subjects)
        ):
            continue
        matched.append(
            CatalogEntry(
                ol_key=str(row[0]),
                title=str(row[1]),
                authors=_json_list_or_empty(row[2]),
                subjects=entry_subjects,
                first_publish_year=row[4],
                description=row[5],
                provenance_note=str(row[6] or ""),
            )
        )
    return matched[start : start + capped], len(matched)
