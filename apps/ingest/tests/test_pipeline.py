"""Tests for apps/ingest/pipeline.py — see specs/ingestion.md named red tests.

Unit tests below (`Test*` free functions without `@pytest.mark.integration`)
exercise pure helpers and the dlt resources in isolation — no Postgres, no
downloaded model, no network. They are what `uv run pytest` runs by default.

The tests that need a live Postgres (and, for the embeddings ones, the real
`sentence-transformers/all-MiniLM-L6-v2` model) are marked
`@pytest.mark.integration` and self-skip via the `live_database_url` fixture
below when `DATABASE_URL` is not reachable, so the default `uv run pytest`
run still passes with no database running.
"""

import gzip
import json
import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from homelib_core.models import Block, BookDoc, Provenance
from psycopg import sql

from apps.ingest.pipeline import (
    DEFAULT_DATABASE_URL,
    STAGING_DATASET,
    _sync_staging_to_public,
    blocks_resource,
    books_resource,
    catalog_resource,
    chunk_embeddings_resource,
    chunks_resource,
    run_pipeline,
)

# NEVER the application's own database. These tests drop dlt's staging schemas
# and reload `public` wholesale, so pointing them at `homelib` means running
# the suite silently wipes and rebuilds whatever the operator had seeded —
# which is exactly what happened here, and left `public` empty while the data
# sat in a stale staging schema.
#
# The name is unique per process for the reason established twice already in
# this repo: two runs on one host (a push and its PR, or a developer alongside
# CI) otherwise DROP and CREATE the same database and delete each other's
# mid-test.
_ADMIN_DSN = DEFAULT_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
_TEST_DB_NAME = f"homelib_test_ingest_{os.environ.get('GITHUB_RUN_ID', 'local')}_{os.getpid()}"
TEST_DATABASE_URL = DEFAULT_DATABASE_URL.rsplit("/", 1)[0] + "/" + _TEST_DB_NAME

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docker" / "initdb" / "01-schema.sql"

_CANONICAL_TABLES = ("books", "blocks", "chunks", "chunk_embeddings", "catalog")


def _book(book_id: str, text: str = "Hello world. This is a test sentence.") -> BookDoc:
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


def _write_snapshot(path: Path, docs: list[BookDoc], *, extra_malformed_line: str = "") -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for doc in docs:
            fh.write(json.dumps(doc.model_dump(mode="json")) + "\n")
        if extra_malformed_line:
            fh.write(extra_malformed_line + "\n")


@pytest.fixture(scope="session")
def _throwaway_database() -> Iterator[str]:
    """Create a throwaway database for this process, and drop it afterwards.

    Skips (rather than fails) when no Postgres server is reachable, so a plain
    `uv run pytest` still passes with nothing running, per specs/ingestion.md.
    Note that a skip reads as green in pytest's summary line — an earlier CI
    run reported "1 skipped" purely because Docker had restarted, so treat
    "0 skipped" as part of what a real verification shows.
    """
    try:
        admin = psycopg.connect(_ADMIN_DSN, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"no reachable Postgres server for integration tests: {exc}")

    with admin, admin.cursor() as cur:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(_TEST_DB_NAME)))
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(_TEST_DB_NAME)))

    with psycopg.connect(TEST_DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(_SCHEMA_PATH.read_text())
        conn.commit()

    try:
        yield TEST_DATABASE_URL
    finally:
        with (
            psycopg.connect(_ADMIN_DSN, autocommit=True) as teardown,
            teardown.cursor() as cur,
        ):
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(_TEST_DB_NAME)
                )
            )


@pytest.fixture
def live_database_url(_throwaway_database: str) -> str:
    """This process's throwaway database — never the application's."""
    return _throwaway_database


def _drop_staging_schemas(database_url: str) -> None:
    """Drop dlt's staging dataset (and the `_staging` merge dataset dlt makes
    alongside it), so each test starts from a state matching a fresh clone —
    a stale schema left by an earlier failed dlt run must never leak into
    another test's assertions.
    """
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {STAGING_DATASET} CASCADE")
        conn.execute(f"DROP SCHEMA IF EXISTS {STAGING_DATASET}_staging CASCADE")


def _table_counts(database_url: str) -> dict[str, int]:
    """Row counts for every canonical table."""
    with psycopg.connect(database_url) as conn:
        return {
            table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # type: ignore[index]
            for table in _CANONICAL_TABLES
        }


def _reset_corpus_tables(database_url: str) -> None:
    """Empty the canonical tables and drop dlt's staging schemas."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE chunk_embeddings, chunks, blocks, books, catalog CASCADE")
    _drop_staging_schemas(database_url)


@pytest.fixture(scope="session")
def seeded_corpus(_throwaway_database: str) -> Iterator[str]:
    """The full corpus, loaded ONCE for the whole session.

    Every integration test below used to call `run_pipeline()` itself, and
    each call embeds all 9,168 chunks. Seven tests therefore paid for seven
    full embedding passes — about 14 minutes, which was enough on its own to
    blow through CI's job timeout twice.

    Sharing one load is not a shortcut: these tests assert on the STATE a load
    produces, and they assert different things about it, so one load answers
    all of them. The two idempotency tests deliberately run a second pass on
    top; that is safe for the tests that follow precisely because being
    idempotent means the second pass changes nothing — if it ever does, the
    idempotency test fails first and says so directly.
    """
    _reset_corpus_tables(_throwaway_database)
    run_pipeline(database_url=_throwaway_database)
    yield _throwaway_database
    _reset_corpus_tables(_throwaway_database)


@pytest.fixture
def clean_corpus_tables(live_database_url: str) -> Iterator[str]:
    """An EMPTY canonical schema, for tests that need to observe a load
    happening rather than its result. Function-scoped and expensive — prefer
    `seeded_corpus` unless the test genuinely needs to start from empty.
    """
    _reset_corpus_tables(live_database_url)
    yield live_database_url
    _reset_corpus_tables(live_database_url)


# ── unit tests: pure helpers, no DB, no model, no network ──────────────────


def test_books_resource_yields_one_row_per_book(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.jsonl.gz"
    _write_snapshot(snapshot, [_book("book-a"), _book("book-b")])

    rows = list(books_resource(snapshot))

    assert {r["book_id"] for r in rows} == {"book-a", "book-b"}
    assert all(r["authors"] == ["Author One"] for r in rows)


def test_blocks_resource_uses_doc_book_id_not_block_book_id(tmp_path: Path) -> None:
    """Guards the exact snapshot data-quality quirk this pipeline works
    around: `build_snapshot.py` bakes a stale, filename-derived `book_id`
    into each `Block` (e.g. "franklin-autobiography-clean") that does not
    match the manifest's real `BookDoc.book_id` ("franklin-autobiography").
    `blocks.book_id` must use the parent doc's id or the FK to `books` would
    never resolve.
    """
    doc = _book("real-book-id")
    doc.blocks[0].book_id = "stale-slug-book-id"
    snapshot = tmp_path / "snapshot.jsonl.gz"
    _write_snapshot(snapshot, [doc])

    rows = list(blocks_resource(snapshot))

    assert len(rows) == 1
    assert rows[0]["book_id"] == "real-book-id"
    assert rows[0]["section_path"] == ["Chapter One"]


def test_chunks_resource_chunks_align_with_source_book(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.jsonl.gz"
    _write_snapshot(snapshot, [_book("book-a")])

    rows = list(chunks_resource(snapshot))

    assert len(rows) >= 1
    assert all(r["book_id"] == "book-a" for r in rows)
    assert all(isinstance(r["block_ids"], list) and r["block_ids"] for r in rows)


def test_iter_books_skips_malformed_line_and_continues(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.jsonl.gz"
    _write_snapshot(snapshot, [_book("book-a")], extra_malformed_line="{not valid json")

    rows = list(books_resource(snapshot))

    assert [r["book_id"] for r in rows] == ["book-a"]


def test_catalog_resource_skips_provenance_header_and_malformed_line(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.jsonl"
    good = {
        "ol_key": "/works/OL1W",
        "title": "T",
        "authors": ["A"],
        "subjects": ["s"],
        "first_publish_year": 2020,
        "description": None,
        "provenance_note": "n",
    }
    catalog.write_text(
        json.dumps({"_provenance": "fetched today"})
        + "\n"
        + json.dumps(good)
        + "\n"
        + "{not valid json\n"
    )

    rows = list(catalog_resource(catalog))

    assert len(rows) == 1
    assert rows[0]["ol_key"] == "/works/OL1W"
    assert rows[0]["authors"] == ["A"]


# ── named red tests: live Postgres required ─────────────────────────────


@pytest.mark.integration
def test_chunks_and_embeddings_counts_match(seeded_corpus: str) -> None:
    """Every loaded chunk has exactly one embedding row."""
    with psycopg.connect(seeded_corpus) as conn:
        chunk_count = conn.execute("SELECT count(*) FROM chunks").fetchone()
        embedding_count = conn.execute("SELECT count(*) FROM chunk_embeddings").fetchone()
        unmatched = conn.execute(
            "SELECT count(*) FROM chunks c "
            "LEFT JOIN chunk_embeddings e ON e.chunk_id = c.chunk_id "
            "WHERE e.chunk_id IS NULL"
        ).fetchone()

    assert chunk_count is not None
    assert embedding_count is not None
    assert unmatched is not None
    assert chunk_count[0] > 0
    assert chunk_count[0] == embedding_count[0]
    assert unmatched[0] == 0


@pytest.mark.integration
def test_chunk_embeddings_chunk_id_always_has_matching_chunk(seeded_corpus: str) -> None:
    """Regression test for the exact defect this pipeline's design guards
    against: dlt has no knowledge of `chunk_embeddings.chunk_id`'s FK to
    `chunks.chunk_id`, so a naive single dlt load into `public` can commit
    `chunk_embeddings` rows whose `chunk_id` never lands in `chunks` at all.
    Every `chunk_embeddings` row must reference a real `chunks` row — checked
    with an explicit anti-join, independent of `test_chunks_and_embeddings_
    counts_match`'s row-count comparison, which a coincidental count match
    would not catch.
    """
    with psycopg.connect(seeded_corpus) as conn:
        orphans = conn.execute(
            "SELECT e.chunk_id FROM chunk_embeddings e "
            "LEFT JOIN chunks c ON c.chunk_id = e.chunk_id "
            "WHERE c.chunk_id IS NULL LIMIT 5"
        ).fetchall()

    assert orphans == []


@pytest.mark.integration
def test_ingest_does_not_reshape_canonical_schema(seeded_corpus: str) -> None:
    """dlt must never own or reshape `public`: this pins the invariant that
    makes the ELT split (dlt -> `homelib_staging`, then an explicit transform
    -> `public`) safe. `chunks.tsv` is a `GENERATED ALWAYS` column dlt never
    writes to and must stay populated; `chunk_embeddings.embedding` must stay
    a real pgvector `vector(384)`, not whatever type dlt would have invented
    for it (dlt's own type system has no vector type at all).
    """
    with psycopg.connect(seeded_corpus) as conn:
        tsv_column = conn.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='chunks' AND column_name='tsv'"
        ).fetchone()
        null_tsv_count = conn.execute("SELECT count(*) FROM chunks WHERE tsv IS NULL").fetchone()
        tsv_matches_text = conn.execute(
            "SELECT count(*) FROM chunks WHERE tsv <> to_tsvector('english', text)"
        ).fetchone()

        embedding_udt = conn.execute(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='chunk_embeddings' "
            "AND column_name='embedding'"
        ).fetchone()
        vector_dims = conn.execute(
            "SELECT DISTINCT vector_dims(embedding) FROM chunk_embeddings"
        ).fetchall()

        authors_udt = conn.execute(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='books' AND column_name='authors'"
        ).fetchone()

    assert tsv_column == ("tsvector",)
    assert null_tsv_count == (0,)
    assert tsv_matches_text == (0,)
    assert embedding_udt == ("vector",)
    assert vector_dims == [(384,)]
    assert authors_udt == ("_text",)  # native text[], not jsonb


@pytest.mark.integration
def test_second_run_adds_no_duplicates(seeded_corpus: str) -> None:
    """Idempotency proof: load again over an existing load, counts identical.

    Builds on the session's load rather than doing its own first pass — the
    claim is "a second run changes nothing", and the session fixture already
    provides the first run. That halves the embedding work for this test.
    """
    first_counts = _table_counts(seeded_corpus)
    assert first_counts["books"] > 0

    run_pipeline(database_url=seeded_corpus)

    assert _table_counts(seeded_corpus) == first_counts


@pytest.mark.integration
def test_sync_staging_to_public_alone_is_idempotent(seeded_corpus: str) -> None:
    """The ELT transform is idempotent on its own, independent of dlt's merge.

    Re-running it against the same already-staged rows must not duplicate
    anything in `public`. Deliberately calls the transform rather than the
    whole pipeline: dlt's merge disposition would mask a non-idempotent
    transform by never presenting it with a duplicate in the first place.
    Staging is already populated by the session's load, so this costs no
    embedding work at all.
    """
    first_counts = _table_counts(seeded_corpus)
    assert first_counts["chunks"] > 0

    _sync_staging_to_public(seeded_corpus)

    assert _table_counts(seeded_corpus) == first_counts


@pytest.mark.integration
def test_embeddings_are_384_dim(seeded_corpus: str) -> None:
    with psycopg.connect(seeded_corpus) as conn:
        dims = conn.execute(
            "SELECT DISTINCT vector_dims(embedding) FROM chunk_embeddings"
        ).fetchall()

    assert dims == [(384,)]


@pytest.mark.integration
def test_chunk_embeddings_resource_batches_not_one_at_a_time(
    live_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`embed_texts` is called in batches, never once per chunk.

    Doesn't touch Postgres itself, but gates on `live_database_url` anyway:
    it needs the real embedding model, and that fixture is this suite's
    proxy for "a real dev/verify environment, safe to hit the model" — it
    keeps this test from trying to download the model in CI, where neither
    Postgres nor network access is guaranteed.
    """
    del live_database_url
    import apps.ingest.pipeline as pipeline_mod

    snapshot = tmp_path / "snapshot.jsonl.gz"
    _write_snapshot(snapshot, [_book("book-a", text="One. Two. Three. Four. Five.")])

    calls: list[int] = []
    real_embed_texts = pipeline_mod.embed_texts

    def _tracking_embed_texts(texts: list[str]) -> list[list[float]]:
        calls.append(len(texts))
        return real_embed_texts(texts)

    monkeypatch.setattr(pipeline_mod, "embed_texts", _tracking_embed_texts)

    rows = list(chunk_embeddings_resource(snapshot))

    assert len(rows) >= 1
    # one batched call for this tiny fixture, not len(rows) individual calls
    assert len(calls) == 1
    assert calls[0] == len(rows)
    assert all(isinstance(r["embedding"], list) for r in rows)
