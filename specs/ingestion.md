# spec: ingestion — `apps/ingest/pipeline.py` (dlt)

**Implemented by:** WP-09 (v1 dlt → Postgres). **v2 target:** WP03 dlt → SQLite
(ADR-004). Idempotency contract unchanged. Compose Postgres stays until a
later WP drops it; this spec must not be read as “delete Postgres now”.

**Consumed by:** `homelib_rag.index` (reads `chunks`/`chunk_embeddings` from
the configured store), `apps/api` `POST /v1/ingest` (selfhosted; demo → 403).

## Purpose

Load the corpora (specs/corpus.md) into the configured store as three related
resources — books, blocks, chunks — computing chunk embeddings at load time,
using **dlt** (the rubric-named ingestion tool) so re-running the pipeline is a
safe, idempotent operation rather than a truncate-and-reload script. v1
destination is Postgres; v2 destination is SQLite (`dlt[sqlalchemy]`).

## Public interface

```python
def run_pipeline(snapshot: Path = Path("data/corpus_snapshot.jsonl.gz")) -> LoadInfo: ...
    # dlt.pipeline(...).run(source, ...) -> dlt's own LoadInfo; re-exported as-is

@dlt.source
def homelib_source(snapshot: Path) -> Iterable[DltResource]: ...

@dlt.resource(name="books", write_disposition="merge", primary_key="book_id")
def books_resource(snapshot: Path) -> Iterator[dict]: ...

@dlt.resource(name="blocks", write_disposition="merge", primary_key="block_id")
def blocks_resource(snapshot: Path) -> Iterator[dict]: ...

@dlt.resource(name="chunks", write_disposition="merge", primary_key="chunk_id")
def chunks_resource(snapshot: Path) -> Iterator[dict]: ...
    # yields chunk dict + embedding: list[float] (384-dim, all-MiniLM-L6-v2),
    # written to a separate chunk_embeddings row keyed by chunk_id

def embed_texts(texts: Sequence[str]) -> list[list[float]]: ...
    # lazy singleton SentenceTransformer("all-MiniLM-L6-v2"); batched
```

## Data contracts (field-level)

Postgres tables (created by `docker/initdb/*.sql`, per plan §4.5/§6.1 — this
spec only asserts what the pipeline writes into them):

```
books             book_id PK, title, authors (text[]), language, source_url,
                  license_note

blocks            block_id PK, book_id FK, ordinal, section_path (text[]),
                  text, char_start, char_end, provenance (jsonb)

chunks            chunk_id PK, book_id FK, block_ids (text[]), section_path
                  (text[]), text, char_start, char_end,
                  text_search (tsvector, GENERATED from text, GIN-indexed)

chunk_embeddings  chunk_id PK/FK -> chunks.chunk_id, embedding vector(384)
```

Row source: every field maps 1:1 from `BookDoc`/`Block`/`Chunk`
(specs/core-models.md) via `model_dump()`; `chunk_book()` (specs/chunking.md)
produces the `Chunk`s from each `BookDoc` at pipeline run time — chunks are
**not** precomputed into the snapshot, so a chunking-parameter change only
requires re-running the pipeline, not re-fetching the corpus.

Embedding model: `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions —
pinned because it is the exact model the course teaches (plan §5), and
because it is small enough to embed in the `api`/`ingest` Docker image.

## Error / degradation behavior

- **Idempotent re-run is the binding contract, not a nice-to-have.** All
  three resources use `write_disposition="merge"` on their natural primary
  key (`book_id`/`block_id`/`chunk_id` — all stable per invariant 3 of
  specs/core-models.md). A second `run_pipeline()` call against an unchanged
  snapshot inserts/updates 0 net new rows; row counts before and after must
  be equal.
- A `BookDoc` whose `book_id` already exists with a different
  `extraction_sha256` (the book was re-parsed after a format-handler fix) is
  treated as an update: its blocks/chunks are replaced by merge-key, not
  duplicated alongside the old ones.
- `chunks_resource` calls `embed_texts` in batches; if the embedding model
  fails to load (missing weights, OOM), the pipeline raises and the dlt load
  reports a failed job — `chunks` never lands rows with a null/zero
  embedding standing in for a real one, since a silently-wrong embedding is
  worse than a stopped pipeline for a component the rubric grades on
  retrieval quality.
- A malformed line in `corpus_snapshot.jsonl.gz` (fails `BookDoc.from_jsonl`)
  is logged with its line number and skipped; the pipeline continues with
  the remaining books rather than aborting the whole load, matching the
  per-book resilience of `fetch_corpus.py`.

## Named red tests (write before the code)

- `test_pipeline_idempotent_rerun_adds_zero_rows` — run twice against a
  fixture snapshot on a test Postgres (compose test profile), assert
  `count(*)` on `books`/`blocks`/`chunks`/`chunk_embeddings` is identical
  after run 2.
- `test_chunk_embeddings_are_384_dim` — every row in `chunk_embeddings` has
  `len(embedding) == 384`.
- `test_updated_book_replaces_not_duplicates` — re-run with a fixture book
  whose `extraction_sha256` changed; old blocks for that `book_id` are gone,
  new ones present, no duplicate `chunk_id`s.
- `test_malformed_snapshot_line_skipped_not_fatal` — one corrupt JSONL line
  among valid ones; pipeline completes, valid books load, the bad line is
  reported in the `LoadInfo`/log, not raised.

## Verify

```
uv run python apps/ingest/pipeline.py
docker compose exec postgres psql -U homelib -c "select count(*) from chunks; select count(*) from chunk_embeddings;"
uv run python apps/ingest/pipeline.py
docker compose exec postgres psql -U homelib -c "select count(*) from chunks; select count(*) from chunk_embeddings;"   # unchanged
uv run pytest apps/ingest/tests/test_pipeline.py -v
```

## SQLite seed CLI (2026-09-05)

`python -m apps.ingest.sqlite_pipeline` — `apps/ingest/sqlite_pipeline.py::main`.
Every argument defaults from the environment so the compose `ingest` one-shot
needs no argv: `--db` ← `HOMELIB_SQLITE_PATH`, `--snapshot`/`--catalog` ←
`SNAPSHOT`/`CATALOG` (shared with the Postgres pipeline), `--manifest` ←
`MANIFEST`, else `manifest.yaml` beside the snapshot (the image has no `/app/data`;
`data/` is mounted at `/data`). Prints one JSON line of row counts and **exits 1
when the seed produced 0 books or 0 chunks** — an empty-but-migrated SQLite file
is exactly the failure this closes (`/health` reports it as `degraded`).

Invoked by `just seed-sqlite` and by `scripts/cold_clone_drill.sh` as a **second
compose one-shot** after the Postgres seed (locked: the image `CMD` stays
Postgres-only; no `&&` double-embed in one process).

Named tests: `test_cli_main_seeds_db_and_reports_counts`,
`test_cli_main_exits_nonzero_on_empty_seed` (apps/ingest/tests/test_sqlite_ingest.py);
`test_health_is_degraded_when_store_has_zero_books` (apps/api/tests/test_api.py);
`test_compose_ingest_can_write_sqlite_seed`, `test_drill_asserts_seed_counts_via_health`
(tests/test_repo_hygiene.py).
