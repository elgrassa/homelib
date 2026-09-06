"""FastAPI service — the single contract every consumer talks through.

See specs/api.md for the endpoint table. The UI has NO database access; if
something is not on this surface, the UI cannot do it. FastAPI auto-generates
OpenAPI at `/openapi.json` and Swagger UI at `/docs`.

Every endpoint that touches the LLM, Postgres, or an external pipeline does
so through the `Deps` dataclass returned by `get_deps` (a FastAPI dependency),
never by calling a hardcoded implementation directly. Production wiring lives
in the `_default_*` functions below; `apps/api/tests/test_api.py` overrides
`get_deps` with fakes so the whole suite runs with no database, no model
download, and no LLM (`uv run pytest` default).
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlparse

import httpx
import psycopg
from fastapi import Depends, FastAPI, HTTPException
from homelib_core.chunk import chunk_book
from homelib_core.models import Block, BookDoc, CatalogEntry, Chunk, ExtractionResult
from homelib_core.normalize import parse_file
from homelib_rag import agent as agent_module
from homelib_rag import answer as answer_module
from homelib_rag import roadmap as roadmap_module
from homelib_rag.answer import LLMUnreachableError, OpenAICompatibleClient
from homelib_rag.hybrid import hybrid_search
from homelib_rag.models import Hit
from homelib_rag.rerank import rerank
from homelib_rag.rewrite import rewrite_query
from homelib_rag.roadmap import RoadmapParseError
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from apps.api.schemas import (
    AskRequest,
    AskResponse,
    BookSummary,
    FeedbackRequest,
    Health,
    IngestRequest,
    IngestResponse,
    LLMHealth,
    OkResponse,
    RoadmapRequest,
    RoadmapResponse,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["app"]

logger = logging.getLogger(__name__)

app = FastAPI(
    title="homelib",
    description=(
        "Personal library: ingest any book format, ask it questions with "
        "block-level citations, get a reading roadmap."
    ),
    version="0.1.0",
)

_DEFAULT_DATABASE_URL = "postgresql://homelib:homelib_local_dev@localhost:5432/homelib"
_DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_ARM_ENV = "HOMELIB_DEFAULT_ARM"
# arm=None on /v1/ask means "use the production winner" — the arm chosen on
# evidence in docs/adrs/ADR-001-retrieval-arm.md (specs/api.md). Overridable
# via HOMELIB_DEFAULT_ARM so that ADR can change the winner without a code
# edit here; this constant is the fallback, not the policy.
_FALLBACK_DEFAULT_ARM = "hybrid_rerank"


# ── Small shared helpers ────────────────────────────────────────────────────


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)


def _connect() -> psycopg.Connection[tuple[Any, ...]]:
    """Open a new Postgres connection. Test seam: overridden via `Deps`
    entirely in tests (every DB-touching field of `Deps` is faked), so this
    is only ever called from production code paths."""
    return psycopg.connect(_dsn())


def _query_sha256_prefix(query: str) -> str:
    """First 16 hex chars of `sha256(query)` — see specs/monitoring.md.

    Written unconditionally to `query_log`; `apps/api` never persists
    plaintext queries (there is no opt-in field on `AskRequest` per
    specs/api.md), so `query_log.query_plaintext` is always left NULL.
    """
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def _price_per_1k(env_var: str) -> float:
    """A `LLM_PRICE_PER_1K_*` env var as a float, defaulting to 0.0.

    0 is the correct default, not a placeholder: a local Ollama run has no
    per-token price, and query_log.cost_usd (specs/monitoring.md) must read
    as "unpriced", not as a fabricated cost. Same read-env-at-call-time
    pattern as `_dsn()` above — no settings object, matching every other
    `LLM_*` var in this module and in `homelib_rag.answer`.
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return 0.0
    return float(raw)


def _compute_cost_usd(tokens_prompt: int, tokens_completion: int) -> float:
    """USD estimate for one `/v1/ask` call from `LLM_PRICE_PER_1K_*` env vars.

    Both default to 0 (see `_price_per_1k`), so this is 0.0 for every caller
    that has not configured a price — the common case, since the compose
    default is a local Ollama model with no per-token cost.
    """
    prompt_price = _price_per_1k("LLM_PRICE_PER_1K_PROMPT")
    completion_price = _price_per_1k("LLM_PRICE_PER_1K_COMPLETION")
    return (tokens_prompt / 1000) * prompt_price + (tokens_completion / 1000) * completion_price


def _infer_provider(base_url: str) -> str:
    """Best-effort human-readable provider name for `/health`, from the
    configured `LLM_BASE_URL` — never the key, never anything secret."""
    host = urlparse(base_url).hostname or ""
    if "openai.com" in host:
        return "openai"
    if "anthropic.com" in host:
        return "anthropic"
    if "groq.com" in host:
        return "groq"
    if host in ("localhost", "127.0.0.1", "ollama", "") or "11434" in base_url:
        return "ollama"
    return host


class QueryLogRow(BaseModel):
    request_id: str
    latency_ms: int
    arm: str
    k: int
    rerank: bool
    rewrite: bool
    model: str
    tokens_prompt: int
    tokens_completion: int
    query_sha256_prefix: str
    degraded: bool
    cost_usd: float = 0.0


# ── Dependency bundle ────────────────────────────────────────────────────────


@dataclass
class Deps:
    """Everything an endpoint needs, injected via `Depends(get_deps)`.

    Every field that touches a network/DB is a plain callable (or, for
    `llm_client`, an `OpenAICompatibleClient`) so `apps/api/tests/test_api.py`
    can override individual pieces with scripted fakes via
    `app.dependency_overrides[get_deps]`.
    """

    llm_client: OpenAICompatibleClient
    llm_provider: str
    llm_reachable: Callable[[], bool]
    db_reachable: Callable[[], bool]
    counts: Callable[[], tuple[int, int]]
    retrieve: Callable[[str, int, str], tuple[list[Hit], str, bool]]
    rewrite_query: Callable[[str], str]
    catalog_search: Callable[[str, list[str] | None], list[CatalogEntry]]
    list_books: Callable[[], list[BookSummary]]
    get_block: Callable[[str], Block]
    get_book_block: Callable[[str, int], Block]
    log_query: Callable[[QueryLogRow], None]
    record_feedback: Callable[[str, str, str | None], bool]
    ingest: Callable[[IngestRequest], IngestResponse]


def _resolve_arm(requested: str | None) -> str:
    if requested is not None:
        return requested
    return os.environ.get(_DEFAULT_ARM_ENV, _FALLBACK_DEFAULT_ARM)


def _default_retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str, bool]:
    """Production `Deps.retrieve`: `hybrid_search` (+ optional rerank).

    Returns `(hits, arm_used, degraded)`. `degraded` is True when the
    requested backend could not be honored in full — either `hybrid_search`
    itself fell back to a single working arm (specs/hybrid.md), or every arm
    raised and there is nothing left to serve (`hits=[]`). Reranker
    unavailability is never `degraded`: specs/rerank.md is explicit that a
    rerank failure must never fail (or flag) a request, only silently keep
    the existing ranking.
    """
    use_rerank = arm == "hybrid_rerank"
    search_mode: Literal["hybrid", "lexical", "vector"]
    if use_rerank or arm == "hybrid":
        search_mode = "hybrid"
    elif arm == "lexical":
        search_mode = "lexical"
    elif arm == "vector":
        search_mode = "vector"
    else:
        raise ValueError(f"unknown arm: {arm!r}")

    try:
        hits, mode_used = hybrid_search(query, k, mode=search_mode)
    except Exception as exc:
        logger.warning("retrieval failed entirely for arm=%r: %s", arm, exc)
        return [], search_mode, True

    degraded = mode_used != search_mode
    if use_rerank and not degraded and hits:
        reranked = rerank(query, hits)
        if reranked is not None:
            return reranked, "hybrid_rerank", False
    return hits, mode_used, degraded


def _default_llm_reachable(base_url: str, timeout: float = 2.0) -> bool:
    try:
        httpx.get(f"{base_url.rstrip('/')}/models", timeout=timeout)
    except Exception:
        return False
    return True


def _default_db_reachable() -> bool:
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        return False
    return True


def _default_counts() -> tuple[int, int]:
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM books")
            books_row = cur.fetchone()
            cur.execute("SELECT count(*) FROM chunks")
            chunks_row = cur.fetchone()
    except Exception:
        return (0, 0)
    return (
        int(books_row[0]) if books_row else 0,
        int(chunks_row[0]) if chunks_row else 0,
    )


def _default_list_books() -> list[BookSummary]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT b.book_id, b.title, b.authors,
                   (SELECT count(*) FROM blocks bl WHERE bl.book_id = b.book_id),
                   (SELECT count(*) FROM chunks c WHERE c.book_id = b.book_id),
                   COALESCE(
                       (SELECT bl2.format FROM blocks bl2 WHERE bl2.book_id = b.book_id
                        ORDER BY bl2.ordinal LIMIT 1),
                       ''
                   )
            FROM books b
            ORDER BY b.title
            """
        )
        rows = cur.fetchall()
    return [
        BookSummary(
            book_id=row[0],
            title=row[1],
            authors=list(row[2]),
            blocks=row[3],
            chunks=row[4],
            format=row[5],
        )
        for row in rows
    ]


def _default_log_query(row: QueryLogRow) -> None:
    """Best-effort `query_log` write — never raises (specs/monitoring.md:
    "monitoring must not become a new way for the API to 500")."""
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_log
                    (request_id, latency_ms, arm, k, rerank, rewrite, model,
                     tokens_prompt, tokens_completion, query_sha256_prefix, degraded,
                     cost_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (request_id) DO NOTHING
                """,
                (
                    row.request_id,
                    row.latency_ms,
                    row.arm,
                    row.k,
                    row.rerank,
                    row.rewrite,
                    row.model,
                    row.tokens_prompt,
                    row.tokens_completion,
                    row.query_sha256_prefix,
                    row.degraded,
                    row.cost_usd,
                ),
            )
    except Exception:
        logger.warning(
            "log_query: failed to write query_log row for request_id=%s",
            row.request_id,
            exc_info=True,
        )


def _default_record_feedback(request_id: str, feedback: str, comment: str | None) -> bool:
    """Returns False for an unknown `request_id` — `apps/api` turns that into
    a 404 (specs/api.md). `comment` has no column on `query_log`
    (specs/indexing.md's schema) so it is accepted but not persisted."""
    del comment
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE query_log SET feedback = %s WHERE request_id = %s RETURNING request_id",
            (feedback, request_id),
        )
        row = cur.fetchone()
    return row is not None


# ── Single-book ingest (the `{path: str}` variant of /v1/ingest) ───────────

_embed_lock = threading.Lock()
_embedder: SentenceTransformer | None = None


def _load_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        with _embed_lock:
            if _embedder is None:
                model_name = os.environ.get("EMBED_MODEL", _DEFAULT_EMBED_MODEL)
                _embedder = SentenceTransformer(model_name)
    return _embedder


def _embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors: NDArray[Any] = _load_embedder().encode(
        list(texts), batch_size=64, show_progress_bar=False
    )
    return [[float(x) for x in row] for row in vectors]


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _insert_book_doc(doc: BookDoc, chunks: list[Chunk]) -> None:
    """Upsert one `BookDoc` and its `Chunk`s into books/blocks/chunks/
    chunk_embeddings, mirroring the row shape `apps/ingest/pipeline.py`
    loads for the whole-corpus path (specs/indexing.md's schema)."""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO books (book_id, title, authors, language, source_url, license_note)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (book_id) DO UPDATE SET
                title = EXCLUDED.title, authors = EXCLUDED.authors,
                language = EXCLUDED.language, source_url = EXCLUDED.source_url,
                license_note = EXCLUDED.license_note
            """,
            (doc.book_id, doc.title, doc.authors, doc.language, doc.source_url, doc.license_note),
        )
        for block in doc.blocks:
            cur.execute(
                """
                INSERT INTO blocks
                    (block_id, book_id, ordinal, section_path, text, char_start, char_end,
                     format, page, spine_index, anchor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (block_id) DO UPDATE SET
                    ordinal = EXCLUDED.ordinal, section_path = EXCLUDED.section_path,
                    text = EXCLUDED.text, char_start = EXCLUDED.char_start,
                    char_end = EXCLUDED.char_end, format = EXCLUDED.format,
                    page = EXCLUDED.page, spine_index = EXCLUDED.spine_index,
                    anchor = EXCLUDED.anchor
                """,
                (
                    block.block_id,
                    block.book_id,
                    block.ordinal,
                    block.section_path,
                    block.text,
                    block.char_start,
                    block.char_end,
                    block.provenance.format,
                    block.provenance.page,
                    block.provenance.spine_index,
                    block.provenance.anchor,
                ),
            )
        embeddings = _embed_texts([c.text for c in chunks])
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            cur.execute(
                """
                INSERT INTO chunks (chunk_id, book_id, block_ids, section_path, text,
                                     char_start, char_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    block_ids = EXCLUDED.block_ids, section_path = EXCLUDED.section_path,
                    text = EXCLUDED.text, char_start = EXCLUDED.char_start,
                    char_end = EXCLUDED.char_end
                """,
                (
                    chunk.chunk_id,
                    chunk.book_id,
                    chunk.block_ids,
                    chunk.section_path,
                    chunk.text,
                    chunk.char_start,
                    chunk.char_end,
                ),
            )
            cur.execute(
                """
                INSERT INTO chunk_embeddings (chunk_id, embedding)
                VALUES (%s, %s::vector)
                ON CONFLICT (chunk_id) DO UPDATE SET embedding = EXCLUDED.embedding
                """,
                (chunk.chunk_id, _vector_literal(embedding)),
            )


def _ingest_path(path: str) -> IngestResponse:
    doc, extraction = parse_file(Path(path))
    chunks = chunk_book(doc)
    _insert_book_doc(doc, chunks)
    return IngestResponse(
        book_id=doc.book_id, blocks=len(doc.blocks), chunks=len(chunks), extraction=extraction
    )


def _ingest_snapshot() -> IngestResponse:
    """The `{source: "snapshot"}` variant: delegate to the whole-corpus dlt
    pipeline (`apps/ingest/pipeline.py`, WP-09 — not modified here). Lazily
    imported: that module pulls in `dlt` and is mid-development elsewhere in
    this repo, so importing it only when this branch actually runs keeps a
    transient issue there from breaking `apps/api` import at all.

    `IngestResponse.book_id` names one book, but a snapshot load ingests the
    whole 18-book corpus at once — there is no single book to report, so
    `book_id` is the sentinel `"__snapshot__"` and `blocks`/`chunks` are the
    corpus-wide totals after the load.
    """
    from apps.ingest.pipeline import run_pipeline

    info = run_pipeline()
    _books, chunks = _default_counts()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM blocks")
        row = cur.fetchone()
    blocks = int(row[0]) if row else 0
    return IngestResponse(
        book_id="__snapshot__",
        blocks=blocks,
        chunks=chunks,
        extraction=ExtractionResult(
            method="mixed",
            extractor_name="dlt.homelib_source",
            extractor_version="1.0",
            extraction_sha256="",
            ocr_engine=None,
            warnings=[str(info)[:500]] if info is not None else [],
        ),
    )


def _default_ingest(req: IngestRequest) -> IngestResponse:
    if req.source == "snapshot":
        return _ingest_snapshot()
    assert req.path is not None  # enforced by IngestRequest's model_validator
    return _ingest_path(req.path)


# ── Deps singleton ───────────────────────────────────────────────────────────

_deps_lock = threading.Lock()
_deps_singleton: Deps | None = None


def _build_default_deps() -> Deps:
    from apps.api import sqlite_deps

    client = answer_module.default_llm_client()
    use_sqlite = sqlite_deps.sqlite_path() is not None

    def _get_block(block_id: str) -> Block:
        if use_sqlite:
            try:
                return sqlite_deps.sqlite_get_block(block_id)
            except LookupError as exc:
                raise KeyError(block_id) from exc
        return agent_module.get_block(block_id)

    def _get_book_block(book_id: str, ordinal: int) -> Block:
        if use_sqlite:
            try:
                return sqlite_deps.sqlite_get_book_block(book_id, ordinal)
            except LookupError as exc:
                raise KeyError(f"{book_id}@{ordinal}") from exc
        return agent_module.get_book_block(book_id, ordinal)

    return Deps(
        llm_client=client,
        llm_provider=_infer_provider(client.base_url),
        llm_reachable=lambda: _default_llm_reachable(client.base_url),
        db_reachable=sqlite_deps.sqlite_db_reachable if use_sqlite else _default_db_reachable,
        counts=sqlite_deps.sqlite_counts if use_sqlite else _default_counts,
        retrieve=_default_retrieve,
        rewrite_query=rewrite_query,
        catalog_search=agent_module.search_catalog,
        list_books=sqlite_deps.sqlite_list_books if use_sqlite else _default_list_books,
        get_block=_get_block,
        get_book_block=_get_book_block,
        log_query=sqlite_deps.sqlite_log_query if use_sqlite else _default_log_query,
        record_feedback=(
            sqlite_deps.sqlite_record_feedback if use_sqlite else _default_record_feedback
        ),
        ingest=_default_ingest,
    )


def get_deps() -> Deps:
    """FastAPI dependency. `apps/api/tests/test_api.py` overrides this
    wholesale via `app.dependency_overrides[get_deps] = lambda: fake_deps`
    so every test builds its own `Deps` with exactly the fakes it needs —
    no live DB, no model download, no LLM, per this repo's testing policy.
    """
    global _deps_singleton
    if _deps_singleton is None:
        with _deps_lock:
            if _deps_singleton is None:
                _deps_singleton = _build_default_deps()
    return _deps_singleton


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health", response_model=Health)
def get_health(deps: Deps = Depends(get_deps)) -> Health:
    db_ok = deps.db_reachable()
    llm_ok = deps.llm_reachable()
    books, chunks = deps.counts() if db_ok else (0, 0)
    # An empty store is reachable, migrated and useless: SQLite creates the
    # file on first connect, so a cold clone that never ran the seed would
    # otherwise report "ok" with 0 books. HTTP stays 200 (the compose
    # healthcheck is liveness, not seeded-ness); the JSON says degraded.
    seeded = books > 0
    return Health(
        status="ok" if (db_ok and llm_ok and seeded) else "degraded",
        db=db_ok,
        llm=LLMHealth(provider=deps.llm_provider, model=deps.llm_client.model, reachable=llm_ok),
        books=books,
        chunks=chunks,
    )


@app.post("/v1/ask", response_model=AskResponse)
def post_ask(req: AskRequest, deps: Deps = Depends(get_deps)) -> AskResponse:
    start = time.monotonic()

    query_for_retrieval = req.query
    rewrite_used = False
    if req.rewrite:
        rewritten = deps.rewrite_query(req.query)
        rewrite_used = rewritten != req.query
        query_for_retrieval = rewritten

    resolved_arm = _resolve_arm(req.arm)
    hits, arm_used, retrieval_degraded = deps.retrieve(query_for_retrieval, req.k, resolved_arm)

    result = answer_module.answer(req.query, hits, client=deps.llm_client, arm_used=arm_used)
    if retrieval_degraded and not result.degraded:
        result = result.model_copy(update={"degraded": True})

    total_latency_ms = int((time.monotonic() - start) * 1000)
    result = result.model_copy(update={"latency_ms": total_latency_ms})

    deps.log_query(
        QueryLogRow(
            request_id=result.request_id,
            latency_ms=total_latency_ms,
            arm=arm_used,
            k=req.k,
            rerank=arm_used == "hybrid_rerank",
            rewrite=rewrite_used,
            model=deps.llm_client.model,
            tokens_prompt=result.tokens.prompt,
            tokens_completion=result.tokens.completion,
            query_sha256_prefix=_query_sha256_prefix(req.query),
            degraded=result.degraded,
            cost_usd=_compute_cost_usd(result.tokens.prompt, result.tokens.completion),
        )
    )
    return result


@app.post("/v1/roadmap", response_model=RoadmapResponse)
def post_roadmap(req: RoadmapRequest, deps: Deps = Depends(get_deps)) -> RoadmapResponse:
    try:
        return roadmap_module.build_roadmap(
            req.interests,
            req.level,
            req.goal,
            req.max_steps,
            client=deps.llm_client,
            catalog=deps.catalog_search,
        )
    except RoadmapParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMUnreachableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/ingest", response_model=IngestResponse)
def post_ingest(req: IngestRequest, deps: Deps = Depends(get_deps)) -> IngestResponse:
    try:
        return deps.ingest(req)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ingest failed: {exc}") from exc


@app.post("/v1/feedback", response_model=OkResponse)
def post_feedback(req: FeedbackRequest, deps: Deps = Depends(get_deps)) -> OkResponse:
    ok = deps.record_feedback(req.request_id, req.feedback, req.comment)
    if not ok:
        raise HTTPException(status_code=404, detail=f"unknown request_id: {req.request_id!r}")
    return OkResponse()


@app.get("/v1/books", response_model=list[BookSummary])
def get_books(deps: Deps = Depends(get_deps)) -> list[BookSummary]:
    return deps.list_books()


@app.get("/v1/blocks/{block_id}", response_model=Block)
def get_block_endpoint(block_id: str, deps: Deps = Depends(get_deps)) -> Block:
    try:
        return deps.get_block(block_id)
    except (KeyError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/books/{book_id}/blocks", response_model=Block)
def get_book_block_endpoint(
    book_id: str,
    ordinal: int = 0,
    deps: Deps = Depends(get_deps),
) -> Block:
    """Projection page: one block of ``book_id`` at dense ``ordinal`` (default 0)."""
    if ordinal < 0:
        raise HTTPException(status_code=422, detail="ordinal must be >= 0")
    try:
        return deps.get_book_block(book_id, ordinal)
    except (KeyError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# v2 product surface (mentor / scene / Coffee Table / Observatory)
from apps.api.v2_routes import router as v2_router  # noqa: E402

app.include_router(v2_router)
