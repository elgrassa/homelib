"""Within-book scene search — see specs/scene-search.md."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from homelib_rag.models import Hit
from homelib_rag.rerank import rerank
from homelib_rag.rewrite import rewrite_query

logger = logging.getLogger(__name__)

__all__ = ["SceneHit", "SceneMode", "SceneSearchResponse", "scene_search"]

_CONTEXT_CHARS = 80


class SceneMode(StrEnum):
    EXACT = "exact"
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    SMART = "smart"
    ASK = "ask"


class SceneHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str
    chapter_id: str | None
    block_id: str
    chunk_id: str | None
    char_start: int
    char_end: int
    quote: str
    prev_context: str
    next_context: str
    open_anchor: str


class SceneSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    resource_id: str
    hits: list[SceneHit]
    mode_used: str
    degraded: bool
    latency_ms: int
    synthesis: str | None = None


class ResourceNotFoundError(LookupError):
    pass


class ResourceNotSearchableError(RuntimeError):
    pass


def _json_list(raw: str) -> list[str]:
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise TypeError(f"expected JSON list, got {type(parsed)!r}")
    return [str(item) for item in parsed]


def _book_rights(conn: sqlite3.Connection, resource_id: str) -> tuple[bool, str]:
    row = conn.execute(
        "SELECT rights_status FROM books WHERE book_id = ?",
        (resource_id,),
    ).fetchone()
    if row is None:
        raise ResourceNotFoundError(resource_id)
    rights_status = str(row[0])
    from apps.store.sqlite import can_index_text

    return can_index_text(rights_status), rights_status


def _chapter_section(conn: sqlite3.Connection, chapter_id: str) -> str | None:
    row = conn.execute(
        "SELECT section_path FROM blocks WHERE block_id = ?",
        (chapter_id,),
    ).fetchone()
    if row is None:
        return None
    paths = _json_list(str(row[0]))
    return paths[0] if paths else None


def _chunk_in_chapter(conn: sqlite3.Connection, block_ids_json: str, chapter_section: str) -> bool:
    for block_id in _json_list(block_ids_json):
        row = conn.execute(
            "SELECT section_path FROM blocks WHERE block_id = ?",
            (block_id,),
        ).fetchone()
        if row is None:
            continue
        paths = _json_list(str(row[0]))
        if paths and paths[0] == chapter_section:
            return True
    return False


def _filter_hits_to_scope(
    conn: sqlite3.Connection,
    hits: list[Hit],
    *,
    resource_id: str,
    chapter_id: str | None,
) -> list[Hit]:
    chapter_section = _chapter_section(conn, chapter_id) if chapter_id else None
    scoped: list[Hit] = []
    for hit in hits:
        if hit.book_id != resource_id:
            continue
        if chapter_section is not None:
            row = conn.execute(
                "SELECT block_ids FROM chunks WHERE chunk_id = ?",
                (hit.chunk_id,),
            ).fetchone()
            if row is None or not _chunk_in_chapter(conn, str(row[0]), chapter_section):
                continue
        scoped.append(hit)
    return [hit.model_copy(update={"rank": rank}) for rank, hit in enumerate(scoped, start=1)]


def _canonical_text(conn: sqlite3.Connection, book_id: str) -> str:
    rows = conn.execute(
        "SELECT text FROM blocks WHERE book_id = ? ORDER BY ordinal",
        (book_id,),
    ).fetchall()
    return "".join(str(row[0]) for row in rows)


def _context_window(canonical: str, start: int, end: int) -> tuple[str, str, str]:
    quote = canonical[start:end]
    prev_context = canonical[max(0, start - _CONTEXT_CHARS) : start]
    next_context = canonical[end : min(len(canonical), end + _CONTEXT_CHARS)]
    return quote, prev_context, next_context


def _exact_hits(
    conn: sqlite3.Connection,
    *,
    resource_id: str,
    query: str,
    chapter_id: str | None,
    k: int,
) -> list[SceneHit]:
    canonical = _canonical_text(conn, resource_id)
    stripped = query.strip()
    if not stripped:
        return []
    pattern = re.compile(
        r"\s+".join(re.escape(part) for part in stripped.split()),
        flags=re.IGNORECASE,
    )
    chapter_section = _chapter_section(conn, chapter_id) if chapter_id else None
    scene_hits: list[SceneHit] = []
    for match in pattern.finditer(canonical):
        if len(scene_hits) >= k:
            break
        char_start, char_end = match.start(), match.end()
        block_row = conn.execute(
            """
            SELECT block_id, section_path
            FROM blocks
            WHERE book_id = ? AND char_start <= ? AND char_end >= ?
            ORDER BY ordinal
            LIMIT 1
            """,
            (resource_id, char_start, char_start),
        ).fetchone()
        if block_row is None:
            continue
        if chapter_section is not None:
            paths = _json_list(str(block_row["section_path"]))
            if not paths or paths[0] != chapter_section:
                continue
        quote, prev_context, next_context = _context_window(canonical, char_start, char_end)
        block_id = str(block_row["block_id"])
        chunk_row = conn.execute(
            """
            SELECT chunk_id FROM chunks
            WHERE book_id = ? AND char_start <= ? AND char_end >= ?
            LIMIT 1
            """,
            (resource_id, char_start, char_start),
        ).fetchone()
        scene_hits.append(
            SceneHit(
                resource_id=resource_id,
                chapter_id=chapter_id,
                block_id=block_id,
                chunk_id=str(chunk_row[0]) if chunk_row is not None else None,
                char_start=char_start,
                char_end=char_end,
                quote=quote,
                prev_context=prev_context,
                next_context=next_context,
                open_anchor=block_id,
            )
        )
    return scene_hits


def _hits_to_scene(
    conn: sqlite3.Connection,
    hits: list[Hit],
    *,
    resource_id: str,
    chapter_id: str | None,
) -> list[SceneHit]:
    canonical = _canonical_text(conn, resource_id)
    scene_hits: list[SceneHit] = []
    for hit in hits:
        row = conn.execute(
            "SELECT char_start, char_end FROM chunks WHERE chunk_id = ?",
            (hit.chunk_id,),
        ).fetchone()
        if row is None:
            continue
        char_start = int(row[0])
        char_end = int(row[1])
        quote, prev_context, next_context = _context_window(canonical, char_start, char_end)
        block_id = hit.block_ids[0] if hit.block_ids else hit.chunk_id
        scene_hits.append(
            SceneHit(
                resource_id=resource_id,
                chapter_id=chapter_id,
                block_id=block_id,
                chunk_id=hit.chunk_id,
                char_start=char_start,
                char_end=char_end,
                quote=quote,
                prev_context=prev_context,
                next_context=next_context,
                open_anchor=block_id,
            )
        )
    return scene_hits


def _sqlite_lexical(q: str, k: int, *, book_id: str, conn: sqlite3.Connection) -> list[Hit]:
    from homelib_rag.sqlite_index import search_lexical

    return search_lexical(q, k, book_id=book_id, conn=conn)


def _sqlite_vector(q: str, k: int, *, book_id: str, conn: sqlite3.Connection) -> list[Hit]:
    from homelib_rag.sqlite_index import search_vector

    return search_vector(q, k, book_id=book_id, conn=conn)


def _fuse_hits(lexical_hits: list[Hit], vector_hits: list[Hit], k: int) -> tuple[list[Hit], str]:
    from homelib_rag.hybrid import _fuse

    return _fuse(lexical_hits, vector_hits, k), "smart"


def _promote_verbatim_phrase(query: str, hits: list[Hit]) -> list[Hit]:
    """Keep exact body matches ahead of semantic/reranker approximations."""
    needle = " ".join(query.split()).casefold()
    if not needle:
        return hits
    return sorted(
        hits,
        key=lambda hit: needle not in " ".join(hit.text.split()).casefold(),
    )


def _smart_hits(
    conn: sqlite3.Connection,
    query: str,
    *,
    resource_id: str,
    chapter_id: str | None,
    k: int,
    use_rewrite: bool,
) -> tuple[list[SceneHit], str, bool]:
    search_q = rewrite_query(query) if use_rewrite else query
    lexical_hits: list[Hit] = []
    vector_hits: list[Hit] = []
    lexical_ok = False
    vector_ok = False
    try:
        lexical_hits = _sqlite_lexical(search_q, k, book_id=resource_id, conn=conn)
        lexical_ok = True
    except Exception as exc:
        logger.warning("scene lexical arm failed: %s", exc)
    try:
        vector_hits = _sqlite_vector(search_q, k, book_id=resource_id, conn=conn)
        vector_ok = True
    except Exception as exc:
        logger.warning("scene vector arm failed: %s", exc)

    degraded = False
    mode_used = "smart"
    if lexical_ok and vector_ok:
        hits, mode_used = _fuse_hits(lexical_hits, vector_hits, k)
    elif lexical_ok:
        hits = lexical_hits
        mode_used = "keyword"
        degraded = True
    elif vector_ok:
        hits = vector_hits
        mode_used = "semantic"
        degraded = True
    else:
        hits = []

    scoped = _filter_hits_to_scope(conn, hits, resource_id=resource_id, chapter_id=chapter_id)
    reranked = rerank(search_q, scoped)
    if reranked is not None:
        scoped = reranked
    scoped = _promote_verbatim_phrase(search_q, scoped)
    scenes = _hits_to_scene(conn, scoped[:k], resource_id=resource_id, chapter_id=chapter_id)
    return scenes, mode_used, degraded


def _synthesize_ask(query: str, hits: list[SceneHit]) -> str | None:
    if not hits:
        return None
    from homelib_rag.rewrite import _call_llm

    passages = "\n".join(f"[{index}] {hit.quote}" for index, hit in enumerate(hits, start=1))
    prompt = (
        "Answer the question using only the numbered passages. "
        f"Question: {query}\nPassages:\n{passages}"
    )
    return _call_llm(prompt)


def scene_search(
    conn: sqlite3.Connection,
    resource_id: str,
    query: str,
    mode: SceneMode,
    *,
    chapter_id: str | None = None,
    k: int = 5,
) -> SceneSearchResponse:
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
    searchable, rights_status = _book_rights(conn, resource_id)
    if not searchable:
        raise ResourceNotSearchableError(
            f"resource {resource_id!r} is not searchable (rights_status={rights_status})"
        )

    degraded = False
    mode_used = mode.value
    synthesis: str | None = None
    hits: list[SceneHit]

    if mode == SceneMode.EXACT:
        hits = _exact_hits(conn, resource_id=resource_id, query=query, chapter_id=chapter_id, k=k)
    elif mode == SceneMode.KEYWORD:
        lexical = _sqlite_lexical(query, k, book_id=resource_id, conn=conn)
        scoped = _filter_hits_to_scope(
            conn, lexical, resource_id=resource_id, chapter_id=chapter_id
        )
        hits = _hits_to_scene(conn, scoped[:k], resource_id=resource_id, chapter_id=chapter_id)
        mode_used = "keyword"
    elif mode == SceneMode.SEMANTIC:
        try:
            vector = _sqlite_vector(query, k, book_id=resource_id, conn=conn)
        except Exception:
            degraded = True
            mode_used = "keyword"
            vector = _sqlite_lexical(query, k, book_id=resource_id, conn=conn)
        scoped = _filter_hits_to_scope(conn, vector, resource_id=resource_id, chapter_id=chapter_id)
        hits = _hits_to_scene(conn, scoped[:k], resource_id=resource_id, chapter_id=chapter_id)
        if not degraded:
            mode_used = "semantic"
    elif mode in {SceneMode.SMART, SceneMode.ASK}:
        hits, mode_used, degraded = _smart_hits(
            conn,
            query,
            resource_id=resource_id,
            chapter_id=chapter_id,
            k=k,
            use_rewrite=mode == SceneMode.ASK,
        )
        if mode == SceneMode.ASK:
            try:
                synthesis = _synthesize_ask(query, hits)
                mode_used = "ask"
            except Exception:
                degraded = True
                mode_used = "smart"
    else:
        raise ValueError(f"unknown scene mode: {mode!r}")

    latency_ms = int((time.perf_counter() - started) * 1000)
    return SceneSearchResponse(
        request_id=request_id,
        resource_id=resource_id,
        hits=hits,
        mode_used=mode_used,
        degraded=degraded,
        latency_ms=latency_ms,
        synthesis=synthesis,
    )
