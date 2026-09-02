"""Lexical (Postgres FTS) and vector (pgvector) search arms — see specs/indexing.md.

Two independent retrieval arms over the same Postgres store, each returning a
ranked `list[Hit]` a caller can cite back to a page:

- `search_lexical`: `plainto_tsquery('english', q)` against `chunks.tsv`,
  ranked by `ts_rank_cd`.
- `search_vector`: `q` embedded with the pinned `all-MiniLM-L6-v2` model
  (`EMBED_MODEL` env var), cosine distance against `chunk_embeddings.embedding`
  via pgvector's `<=>` operator, `score = 1 - distance`.

Both functions are honest about their own backend being down: a Postgres
connection failure or an embedding-model load failure raises the underlying
exception rather than being swallowed. Degrading to a working single arm is
`homelib_rag.hybrid`'s job, not this module's (specs/hybrid.md).

Connection and embedding are each split into a small, monkeypatchable seam
(`_connect`, `_embed_query`) so unit tests can stub the Postgres round trip
and the embedding model without a live database or a model download —
matching the pattern already used by `rerank.py` (stubs `CrossEncoder`) and
`rewrite.py` (stubs `_call_llm`).
"""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import psycopg
from sentence_transformers import SentenceTransformer

from homelib_rag.models import Hit

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["search_lexical", "search_vector"]

_DEFAULT_DATABASE_URL = "postgresql://homelib:homelib_local_dev@localhost:5432/homelib"
_DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Lazy, thread-safe embedder singleton — mirrors `rerank.py`'s pattern, but
# unlike `rerank`'s "degrade to None" contract, a load failure here is never
# caught: specs/indexing.md requires it to raise at first call rather than
# silently returning zero vectors.
_embed_lock = threading.Lock()
_embedder: SentenceTransformer | None = None


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)


def _connect() -> psycopg.Connection[tuple[Any, ...]]:
    """Open a new Postgres connection. Test seam: monkeypatch this directly.

    Any failure (host down, auth, bad DSN) raises `psycopg`'s own exception —
    not caught here, per specs/indexing.md's error/degradation contract.
    """
    return psycopg.connect(_dsn())


def _load_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is not None:
        return _embedder
    with _embed_lock:
        if _embedder is None:
            model_name = os.environ.get("EMBED_MODEL", _DEFAULT_EMBED_MODEL)
            # Deliberately not wrapped in try/except: a misconfigured
            # `EMBED_MODEL` must raise here, not return zero vectors.
            _embedder = SentenceTransformer(model_name)
        return _embedder


def _embed_query(q: str) -> list[float]:
    """Embed `q` with the pinned model. Test seam: monkeypatch this directly."""
    model = _load_embedder()
    vector: NDArray[Any] = model.encode(q)
    return [float(x) for x in vector]


def _reset_embedder_for_tests() -> None:
    """Reset the lazy embedder singleton. Test-only — not part of the public API."""
    global _embedder
    with _embed_lock:
        _embedder = None


def _validate(q: str, k: int) -> None:
    if not q.strip():
        raise ValueError("q must not be empty")
    if k <= 0:
        raise ValueError("k must be positive")


def _vector_literal(embedding: Sequence[float]) -> str:
    """Render an embedding as pgvector's text input format: `[0.1,0.2,...]`.

    Returned as a plain bound parameter (cast with `::vector` in the query),
    never interpolated into the SQL text itself.
    """
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


def _first_page(cur: psycopg.Cursor[tuple[Any, ...]], block_ids: Sequence[str]) -> int | None:
    """The `page` of the first block in `block_ids` (in that order) that has one.

    `block_ids` order is the chunk's own block order (specs/indexing.md), so
    this is a lookup + Python-side scan rather than relying on SQL row order,
    which `= ANY(...)` does not guarantee.
    """
    if not block_ids:
        return None
    cur.execute(
        "SELECT block_id, page FROM blocks WHERE block_id = ANY(%s)",
        (list(block_ids),),
    )
    page_by_block: dict[str, int | None] = dict(cur.fetchall())
    for block_id in block_ids:
        page = page_by_block.get(block_id)
        if page is not None:
            return page
    return None


def _use_sqlite() -> bool:
    return bool(os.environ.get("HOMELIB_SQLITE_PATH", "").strip())


def search_lexical(q: str, k: int) -> list[Hit]:
    """Full-text search for `q`, ranked best-first."""
    if _use_sqlite():
        from homelib_rag.sqlite_index import search_lexical as sqlite_search_lexical

        return sqlite_search_lexical(q, k)
    _validate(q, k)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT chunk_id, book_id, section_path, text, block_ids,
                   ts_rank_cd(tsv, plainto_tsquery('english', %s)) AS score
            FROM chunks
            WHERE tsv @@ plainto_tsquery('english', %s)
            ORDER BY score DESC
            LIMIT %s
            """,
            (q, q, k),
        )
        rows = cur.fetchall()
        hits = []
        for rank, row in enumerate(rows, start=1):
            chunk_id, book_id, section_path, text, block_ids, score = row
            hits.append(
                Hit(
                    chunk_id=chunk_id,
                    book_id=book_id,
                    score=float(score),
                    rank=rank,
                    text=text,
                    section_path=list(section_path),
                    page=_first_page(cur, block_ids),
                    block_ids=list(block_ids or []),
                )
            )
        return hits


def search_vector(q: str, k: int) -> list[Hit]:
    """Cosine-similarity search over chunk embeddings."""
    if _use_sqlite():
        from homelib_rag.sqlite_index import search_vector as sqlite_search_vector

        return sqlite_search_vector(q, k)
    _validate(q, k)
    vector_literal = _vector_literal(_embed_query(q))
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.chunk_id, c.book_id, c.section_path, c.text, c.block_ids,
                   1 - (ce.embedding <=> %s::vector) AS score
            FROM chunk_embeddings ce
            JOIN chunks c ON c.chunk_id = ce.chunk_id
            ORDER BY ce.embedding <=> %s::vector
            LIMIT %s
            """,
            (vector_literal, vector_literal, k),
        )
        rows = cur.fetchall()
        hits = []
        for rank, row in enumerate(rows, start=1):
            chunk_id, book_id, section_path, text, block_ids, score = row
            hits.append(
                Hit(
                    chunk_id=chunk_id,
                    book_id=book_id,
                    score=float(score),
                    rank=rank,
                    text=text,
                    section_path=list(section_path),
                    page=_first_page(cur, block_ids),
                    block_ids=list(block_ids or []),
                )
            )
        return hits
