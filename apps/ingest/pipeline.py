"""dlt ingestion pipeline — see specs/ingestion.md (public interface) and
specs/indexing.md (owns the Postgres schema this pipeline loads into; the
DDL lives in `docker/initdb/01-schema.sql`).

Loads `data/corpus_snapshot.jsonl.gz` (18 `BookDoc`s, one JSON object per
line — see `apps/ingest/build_snapshot.py`) and `data/catalog.jsonl` into the
`books`/`blocks`/`chunks`/`chunk_embeddings`/`catalog` tables, computing
chunk embeddings at load time with `sentence-transformers/all-MiniLM-L6-v2`
(384-dim, pinned — the `EMBED_MODEL` env var overrides the model name).

## Why this is ELT (dlt owns a staging schema; a separate transform loads
## the canonical tables), not dlt writing `public` directly

Two properties of the canonical schema (specs/indexing.md, `docker/initdb/
01-schema.sql`) make it unsafe to point dlt at directly:

1. **dlt cannot represent the canonical column types.** `chunks.tsv` is
   `GENERATED ALWAYS AS (to_tsvector('english', text)) STORED` — a value
   Postgres computes, dlt must never write. `chunk_embeddings.embedding` is
   pgvector's `vector(384)`, and `books.authors`/`blocks.section_path`/
   `chunks.block_ids`/`catalog.{authors,subjects}` are native `text[]` —
   dlt's own type system (`dlt.common.data_types.typing.TDataType`) has no
   array or vector member at all.
2. **A schema-evolving loader must not own a schema it can silently
   corrupt.** If dlt is pointed at `public` and ever decides a column needs
   "migrating" (a data-type hint drifts, a fresh table gets created from
   scratch), it would do so using its own type system from point 1 — turning
   `vector(384)` into something dlt invented, or dropping `tsv` outright,
   with no error. (An earlier version of this file fought that constraint
   with a custom `TypeMapper` forcing dlt to emit `text[]`/`vector(n)` DDL.
   It worked, but it meant *dlt's* schema-evolution machinery was silently
   trusted never to re-decide those types later — a correctness property
   nobody could see by reading `docker/initdb/01-schema.sql`.)

So dlt is given a dataset it fully owns instead: `STAGING_DATASET`
(`homelib_staging`), with dlt-native column types (`authors`/`section_path`/
`block_ids`/`subjects`/`embedding` all hinted `data_type="json"`, landing as
plain `jsonb`). Every resource still uses `write_disposition="merge"` with a
real `primary_key` — genuine dlt merge semantics, just against a schema dlt
is allowed to manage. After `pipeline.run()` returns, `_sync_staging_to_public`
moves the staged rows into `public` with one explicit, hand-written,
idempotent (`INSERT ... ON CONFLICT ... DO UPDATE`) statement per table, run
in FK order inside a single transaction — casting `jsonb` arrays to `text[]`
and the staged embedding to `vector(384)` at that boundary, and never
mentioning `tsv` (Postgres computes it from `text` on insert). **Do not
"simplify" this back into dlt writing `public` directly** — that reopens
both problems above.

A related dlt behavior worth knowing, not a bug: a `pipeline.run()` that
fails mid-load leaves a "pending" package in dlt's local working directory
that a later `run()` retries *before* extracting anything new. `_run_with_
retry` calls `pipeline.abort_packages()` before every attempt (a no-op when
nothing is pending) so a stale failure from a previous process — or from an
earlier attempt in the same retry loop — can never silently block a fresh
run.
"""

import gzip
import json
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

import dlt
import psycopg
from dlt.common.pipeline import LoadInfo
from dlt.extract import DltResource
from dlt.pipeline.exceptions import PipelineStepFailed
from homelib_core.chunk import chunk_book
from homelib_core.models import BookDoc, CatalogEntry
from pydantic import ValidationError
from sentence_transformers import SentenceTransformer

# dlt's extract/normalize steps default to a process (multiprocessing) pool,
# and its load step defaults to a 20-thread pool. Pooled workers proved
# unreliable in this sandboxed environment — intermittent `LoadPackageNotFound`
# / package-schema-hash-mismatch failures on the local pipeline working
# directory that are far rarer under single-worker execution (reproduced and
# confirmed repeatedly while verifying this pipeline). There is no throughput
# reason to keep pooling for a one-shot batch load this small (18 books,
# ~9.2k chunks, 5 tables) anyway. `setdefault` so a caller can still override
# for a larger corpus.
os.environ.setdefault("NORMALIZE__WORKERS", "1")
os.environ.setdefault("EXTRACT__WORKERS", "1")
os.environ.setdefault("LOAD__WORKERS", "1")

__all__ = [
    "STAGING_DATASET",
    "blocks_resource",
    "books_resource",
    "catalog_resource",
    "chunk_embeddings_resource",
    "chunks_resource",
    "embed_texts",
    "homelib_source",
    "main",
    "run_pipeline",
]

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "data" / "corpus_snapshot.jsonl.gz"
CATALOG_PATH = REPO_ROOT / "data" / "catalog.jsonl"


def _run_scope() -> str:
    """A token unique to this process, for namespacing shared-host resources.

    The CI run id separates two runners; the pid separates two processes on
    one host, including a developer's local run racing a CI job. Both halves
    have been needed in this repo.
    """
    return f"{os.environ.get('GITHUB_RUN_ID', 'local')}_{os.getpid()}"


DEFAULT_DATABASE_URL = "postgresql://homelib:homelib_local_dev@localhost:5432/homelib"
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384

# The Postgres schema dlt owns end to end (creates, evolves, merges into).
# Never `public` — see the module docstring.
STAGING_DATASET = "homelib_staging"

# How many chunk texts to hand to `embed_texts` per call — batched, never
# one-at-a-time, per specs/ingestion.md ("chunks_resource calls embed_texts
# in batches").
_CHUNK_EMBED_BATCH = 256

# See `_run_with_retry`: bounded retries past a transient local-storage race
# in dlt's package working directory, plus a short delay to let whatever
# filesystem hiccup caused it settle before trying again.
_RUN_RETRY_ATTEMPTS = 3
_RUN_RETRY_DELAY_SECONDS = 1.0


# dlt's default for a list-of-scalars value is a nested child table. These
# fields are single JSON arrays instead — plain, un-nested rows are what the
# `_sync_staging_to_public` transform below expects to find one-per-entity in
# `homelib_staging`. Declared as `dict[str, Any]` (not inferred inline) so
# mypy matches dlt's `columns` overload rather than a narrower literal type.
#
# `_json_column()` returns a FRESH dict on every call — dlt applies its own
# hints onto whatever dict object a column maps to, so two columns sharing
# one dict *instance* corrupt each other's hints (reproduced: "chunks" and
# "catalog" both hint two columns, and reusing one shared literal dict for
# both silently dropped the "json" hint from the second, so the second
# column loaded as a nested child table instead of a jsonb column).
def _json_column() -> dict[str, Any]:
    return {"data_type": "json"}


_BOOKS_COLUMNS: dict[str, Any] = {"authors": _json_column()}
# `page`/`spine_index` are nullable ints that are `None` for every block in
# this corpus (txt-only source books carry no PDF page or EPUB spine data) —
# dlt infers a column's type from the first non-null value it sees, so an
# all-null column across an entire load is never materialized at all unless
# explicitly hinted (dlt's own warning at runtime suggests exactly this).
# `_sync_staging_to_public` unconditionally selects these columns, so they
# must always exist in staging even when every value this run is null.
_BLOCKS_COLUMNS: dict[str, Any] = {
    "section_path": _json_column(),
    "page": {"data_type": "bigint"},
    "spine_index": {"data_type": "bigint"},
}
_CHUNKS_COLUMNS: dict[str, Any] = {"block_ids": _json_column(), "section_path": _json_column()}
_CHUNK_EMBEDDINGS_COLUMNS: dict[str, Any] = {"embedding": _json_column()}
# `description` is `None` for every catalog entry in this dataset — same
# reasoning as `page`/`spine_index` above.
_CATALOG_COLUMNS: dict[str, Any] = {
    "authors": _json_column(),
    "subjects": _json_column(),
    "description": {"data_type": "text"},
}


def _iter_books(snapshot: Path) -> Iterator[BookDoc]:
    """Yield every valid `BookDoc` from `snapshot`.

    A malformed line (bad JSON or a value that fails `BookDoc` validation) is
    logged with its 1-based line number and skipped — the pipeline continues
    with the remaining books rather than aborting the whole load, per
    specs/ingestion.md.
    """
    with gzip.open(snapshot, "rt", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                doc = BookDoc.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning("skipping malformed snapshot line %d: %s", line_no, exc)
                continue
            yield doc


_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy singleton `SentenceTransformer`, loaded once per process.

    Respects the `EMBED_MODEL` env var (read on first call only — the model
    is a genuine singleton, per specs/ingestion.md's public interface).
    """
    global _model
    if _model is None:
        model_name = os.environ.get("EMBED_MODEL", DEFAULT_EMBED_MODEL)
        _model = SentenceTransformer(model_name)
    return _model


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Embed `texts` in one batched call. Never call this once per chunk."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(list(texts), batch_size=64, show_progress_bar=False)
    return [[float(x) for x in row] for row in vectors]


def _embed_batch(ids: Sequence[str], texts: Sequence[str]) -> Iterator[dict[str, Any]]:
    vectors = embed_texts(texts)
    for chunk_id, vector in zip(ids, vectors, strict=True):
        yield {"chunk_id": chunk_id, "embedding": vector}


@dlt.resource(
    name="books",
    write_disposition="merge",
    primary_key="book_id",
    columns=_BOOKS_COLUMNS,
)
def books_resource(snapshot: Path) -> Iterator[dict[str, Any]]:
    for doc in _iter_books(snapshot):
        yield {
            "book_id": doc.book_id,
            "title": doc.title,
            "authors": list(doc.authors),
            "language": doc.language,
            "source_url": doc.source_url,
            "license_note": doc.license_note,
        }


@dlt.resource(
    name="blocks",
    write_disposition="merge",
    primary_key="block_id",
    columns=_BLOCKS_COLUMNS,
)
def blocks_resource(snapshot: Path) -> Iterator[dict[str, Any]]:
    for doc in _iter_books(snapshot):
        # `block.book_id` is not trustworthy: `build_snapshot.py` derives each
        # block's book_id from the intermediate file's slug (e.g.
        # "franklin-autobiography-clean") before the manifest's real book_id
        # ("franklin-autobiography") is applied at the BookDoc level only —
        # so blocks always use the parent doc's book_id for FK correctness.
        for block in doc.blocks:
            yield {
                "block_id": block.block_id,
                "book_id": doc.book_id,
                "ordinal": block.ordinal,
                "section_path": list(block.section_path),
                "text": block.text,
                "char_start": block.char_start,
                "char_end": block.char_end,
                "format": block.provenance.format,
                "page": block.provenance.page,
                "spine_index": block.provenance.spine_index,
                "anchor": block.provenance.anchor,
            }


@dlt.resource(
    name="chunks",
    write_disposition="merge",
    primary_key="chunk_id",
    columns=_CHUNKS_COLUMNS,
)
def chunks_resource(snapshot: Path) -> Iterator[dict[str, Any]]:
    for doc in _iter_books(snapshot):
        for chunk in chunk_book(doc):
            yield {
                "chunk_id": chunk.chunk_id,
                "book_id": chunk.book_id,
                "block_ids": list(chunk.block_ids),
                "section_path": list(chunk.section_path),
                "text": chunk.text,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
            }


@dlt.resource(
    name="chunk_embeddings",
    write_disposition="merge",
    primary_key="chunk_id",
    columns=_CHUNK_EMBEDDINGS_COLUMNS,
)
def chunk_embeddings_resource(snapshot: Path) -> Iterator[dict[str, Any]]:
    ids: list[str] = []
    texts: list[str] = []
    for doc in _iter_books(snapshot):
        for chunk in chunk_book(doc):
            ids.append(chunk.chunk_id)
            texts.append(chunk.text)
            if len(ids) >= _CHUNK_EMBED_BATCH:
                yield from _embed_batch(ids, texts)
                ids, texts = [], []
    if ids:
        yield from _embed_batch(ids, texts)


@dlt.resource(
    name="catalog",
    write_disposition="merge",
    primary_key="ol_key",
    columns=_CATALOG_COLUMNS,
)
def catalog_resource(catalog: Path) -> Iterator[dict[str, Any]]:
    with catalog.open(encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("skipping malformed catalog line %d: %s", line_no, exc)
                continue
            if "_provenance" in data:
                continue
            try:
                entry = CatalogEntry.model_validate(data)
            except ValidationError as exc:
                logger.warning("skipping malformed catalog entry on line %d: %s", line_no, exc)
                continue
            yield {
                "ol_key": entry.ol_key,
                "title": entry.title,
                "authors": list(entry.authors),
                "subjects": list(entry.subjects),
                "first_publish_year": entry.first_publish_year,
                "description": entry.description,
                "provenance_note": entry.provenance_note,
            }


@dlt.source
def homelib_source(
    snapshot: Path = SNAPSHOT_PATH, catalog: Path = CATALOG_PATH
) -> Iterable[DltResource]:
    return [
        books_resource(snapshot),
        blocks_resource(snapshot),
        chunks_resource(snapshot),
        chunk_embeddings_resource(snapshot),
        catalog_resource(catalog),
    ]


def _make_pipeline(database_url: str) -> dlt.Pipeline:
    return dlt.pipeline(
        pipeline_name="homelib_ingest",
        destination=dlt.destinations.postgres(credentials=database_url),
        dataset_name=STAGING_DATASET,
        # dlt defaults its local package working directory to `~/.dlt/
        # pipelines/<name>`. In this pipeline's sandboxed verification
        # environment, `$HOME` sits behind a slower/virtualized filesystem
        # layer that intermittently loses a file dlt itself just wrote a
        # moment earlier (`os.replace` onto a just-created package path) —
        # reproduced repeatedly as `FileNotFoundError`/`LoadPackageNotFound`
        # under back-to-back `pipeline.run()` calls, and reproducibly absent
        # once the working directory moves under the system temp dir instead.
        # A one-shot batch pipeline has no reason to want durable local state
        # anyway (dlt's own docs call this exact shape out: "CI runners
        # without persistent volumes" is a supported, expected deployment).
        # Per-process working directory. dlt keeps its load packages here, and
        # a constant path is shared state: two runs on one host (a push and its
        # PR, or a developer alongside CI) delete each other's packages
        # mid-load. Observed as `NormalizeJobFailed: Package with load_id=...
        # could not be found` on run 12269 — not a dlt bug, two processes in
        # one directory. Costs nothing here because this pipeline reloads the
        # whole snapshot every time and gets its idempotency from
        # merge + primary_key, not from dlt's incremental state.
        pipelines_dir=str(Path(tempfile.gettempdir()) / f"homelib_dlt_{_run_scope()}"),
    )


# One `(insert_columns, select_expr, update_set)` transform per canonical
# table, applied in this exact order — books/blocks/chunks/catalog have no
# ordering dependency on each other, but chunk_embeddings.chunk_id has a
# non-deferrable FK to chunks.chunk_id and MUST run after chunks. Each
# `jsonb`-typed list column staged by dlt is expanded back into a native
# Postgres array with `jsonb_array_elements_text`; `chunk_embeddings.embedding`
# additionally casts through `float4[]` into `vector(384)`. `chunks.tsv` is
# never mentioned — it is `GENERATED ALWAYS`, Postgres computes it from `text`.
_SYNC_STATEMENTS: tuple[tuple[str, str, str], ...] = (
    (
        "books",
        """
        INSERT INTO public.books (book_id, title, authors, language, source_url, license_note)
        SELECT book_id, title, ARRAY(SELECT jsonb_array_elements_text(authors)),
               language, source_url, license_note
        FROM {staging}.books
        """,
        """
        ON CONFLICT (book_id) DO UPDATE SET
            title = EXCLUDED.title, authors = EXCLUDED.authors, language = EXCLUDED.language,
            source_url = EXCLUDED.source_url, license_note = EXCLUDED.license_note
        """,
    ),
    (
        "blocks",
        """
        INSERT INTO public.blocks (block_id, book_id, ordinal, section_path, text,
            char_start, char_end, format, page, spine_index, anchor)
        SELECT block_id, book_id, ordinal, ARRAY(SELECT jsonb_array_elements_text(section_path)),
               text, char_start, char_end, format, page, spine_index, anchor
        FROM {staging}.blocks
        """,
        """
        ON CONFLICT (block_id) DO UPDATE SET
            book_id = EXCLUDED.book_id, ordinal = EXCLUDED.ordinal,
            section_path = EXCLUDED.section_path, text = EXCLUDED.text,
            char_start = EXCLUDED.char_start, char_end = EXCLUDED.char_end,
            format = EXCLUDED.format, page = EXCLUDED.page,
            spine_index = EXCLUDED.spine_index, anchor = EXCLUDED.anchor
        """,
    ),
    (
        "chunks",
        """
        INSERT INTO public.chunks (chunk_id, book_id, block_ids, section_path, text,
            char_start, char_end)
        SELECT chunk_id, book_id, ARRAY(SELECT jsonb_array_elements_text(block_ids)),
               ARRAY(SELECT jsonb_array_elements_text(section_path)),
               text, char_start, char_end
        FROM {staging}.chunks
        """,
        """
        ON CONFLICT (chunk_id) DO UPDATE SET
            book_id = EXCLUDED.book_id, block_ids = EXCLUDED.block_ids,
            section_path = EXCLUDED.section_path, text = EXCLUDED.text,
            char_start = EXCLUDED.char_start, char_end = EXCLUDED.char_end
        """,
    ),
    (
        "chunk_embeddings",
        """
        INSERT INTO public.chunk_embeddings (chunk_id, embedding)
        SELECT chunk_id,
               (ARRAY(SELECT jsonb_array_elements_text(embedding))::float4[])::vector(384)
        FROM {staging}.chunk_embeddings
        """,
        "ON CONFLICT (chunk_id) DO UPDATE SET embedding = EXCLUDED.embedding",
    ),
    (
        "catalog",
        """
        INSERT INTO public.catalog (ol_key, title, authors, subjects, first_publish_year,
            description, provenance_note)
        SELECT ol_key, title, ARRAY(SELECT jsonb_array_elements_text(authors)),
               ARRAY(SELECT jsonb_array_elements_text(subjects)),
               first_publish_year, description, provenance_note
        FROM {staging}.catalog
        """,
        """
        ON CONFLICT (ol_key) DO UPDATE SET
            title = EXCLUDED.title, authors = EXCLUDED.authors, subjects = EXCLUDED.subjects,
            first_publish_year = EXCLUDED.first_publish_year,
            description = EXCLUDED.description, provenance_note = EXCLUDED.provenance_note
        """,
    ),
)


def _sync_staging_to_public(database_url: str, *, staging_dataset: str = STAGING_DATASET) -> None:
    """Move dlt's staged rows into the canonical `public` tables.

    One `INSERT ... SELECT ... ON CONFLICT ... DO UPDATE` per table, in FK
    order, inside a single transaction — idempotent on its own (a second call
    with unchanged staged data upserts identical rows, adding nothing), and
    independent of dlt's own merge. See the module docstring for why this
    step exists instead of pointing dlt at `public` directly.
    """
    with psycopg.connect(database_url) as conn, conn.transaction():
        for table_name, select_sql, upsert_sql in _SYNC_STATEMENTS:
            sql = select_sql.format(staging=staging_dataset) + upsert_sql
            conn.execute(sql)
            logger.info(
                "synced %s: %s",
                table_name,
                conn.execute(
                    f"SELECT count(*) FROM public.{table_name}"  # noqa: S608 - table_name is our own literal tuple, never user input
                ).fetchone(),
            )


def _ensure_ivfflat_index(database_url: str) -> None:
    """Build the pgvector cosine index AFTER data is loaded.

    ivfflat centroids are computed from whatever rows exist at CREATE INDEX
    time; building it against an empty `chunk_embeddings` table (its state
    before this pipeline ever runs — see `docker/initdb/01-schema.sql`, which
    deliberately omits this index for the same reason) produces an index
    that silently degrades recall for every query after, rather than failing
    loudly. Running it here, once real embeddings exist, is what
    specs/indexing.md's `ix_chunk_embeddings_cosine` calls for.
    """
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_chunk_embeddings_cosine "
            "ON chunk_embeddings USING ivfflat (embedding vector_cosine_ops)"
        )


def run_pipeline(
    snapshot: Path = SNAPSHOT_PATH,
    catalog: Path = CATALOG_PATH,
    *,
    database_url: str | None = None,
) -> LoadInfo:
    """Load books/blocks/chunks/chunk_embeddings/catalog into dlt's staging
    schema, then sync staging into the canonical `public` tables.

    Idempotent: every dlt resource uses `write_disposition="merge"` on its
    natural primary key (staging never accumulates duplicates), and
    `_sync_staging_to_public`'s `ON CONFLICT ... DO UPDATE` upserts rather
    than duplicates on the public side too. See the module docstring for why
    this is ELT (dlt owns staging; a separate step loads `public`) rather
    than dlt writing `public` directly.
    """
    resolved_database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    pipeline = _make_pipeline(resolved_database_url)
    try:
        info = _run_with_retry(pipeline, snapshot, catalog)
        _sync_staging_to_public(resolved_database_url)
        _ensure_ivfflat_index(resolved_database_url)
    finally:
        # The per-run working dir is scratch (see _make_pipeline); left in
        # place it never goes away (13 dirs / ~1GB found on 2026-09-04).
        shutil.rmtree(pipeline.pipelines_dir, ignore_errors=True)
    return info


def _run_with_retry(
    pipeline: dlt.Pipeline,
    snapshot: Path,
    catalog: Path,
    *,
    source: Iterable[DltResource] | None = None,
) -> LoadInfo:
    """`pipeline.run()`, retrying past a specific class of transient local
    filesystem race observed in some sandboxed environments: dlt's own local
    package storage under `~/.dlt/pipelines/<name>` occasionally raises
    `FileNotFoundError` for a file/directory another step just created a
    moment earlier (`os.replace` onto a just-made package path, or opening a
    normalize job file dlt itself just wrote) — reproduced repeatedly while
    verifying this pipeline, unrelated to worker-pool count. dlt already
    treats a failed run as retryable at the package level ("you can still
    rerun the load package to retry this job"); `abort_packages()` between
    attempts discards the broken half-finished package so the retry starts
    clean rather than tripping over it again.
    """
    last_error: Exception | None = None
    load_source = source if source is not None else homelib_source(snapshot, catalog)
    for attempt in range(1, _RUN_RETRY_ATTEMPTS + 1):
        pipeline.abort_packages()
        try:
            return pipeline.run(load_source)
        except FileNotFoundError as exc:
            last_error = exc
            logger.warning(
                "pipeline.run() attempt %d/%d hit a transient local-storage race: %s",
                attempt,
                _RUN_RETRY_ATTEMPTS,
                exc,
            )
        except PipelineStepFailed as exc:
            if not isinstance(exc.__cause__, FileNotFoundError):
                raise
            last_error = exc
            logger.warning(
                "pipeline.run() attempt %d/%d hit a transient local-storage race: %s",
                attempt,
                _RUN_RETRY_ATTEMPTS,
                exc,
            )
        time.sleep(_RUN_RETRY_DELAY_SECONDS)
    assert last_error is not None  # loop always sets it before falling through
    raise last_error


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    snapshot = Path(os.environ.get("SNAPSHOT", str(SNAPSHOT_PATH)))
    catalog = Path(os.environ.get("CATALOG", str(CATALOG_PATH)))
    info = run_pipeline(snapshot=snapshot, catalog=catalog)
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
