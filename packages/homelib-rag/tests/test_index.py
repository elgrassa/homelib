"""Red tests for `homelib_rag.index` — see specs/indexing.md.

Unit tests (the default `uv run pytest` run) stub `_connect` and
`_embed_query` directly with fake, in-memory objects — nothing here touches a
live Postgres or downloads an embedding model.

Integration tests (`@pytest.mark.integration`) create and drop their OWN
throwaway database on the same Postgres server the project's `homelib`
database lives on, and never touch `homelib` itself — another agent may be
concurrently loading that database. The throwaway name is unique per process
(see `_TEST_DB_NAME`); a constant name was not enough. The session fixture
that creates it skips the whole integration suite (rather than failing) if no
Postgres server is reachable at all, so a plain `uv run pytest` — which does
not filter by marker — still passes in an environment with no database, e.g.
CI (see `.forgejo/workflows/ci.yml`, which runs no Postgres service).
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import psycopg
import pytest
from homelib_rag import index as index_module
from homelib_rag.index import search_lexical, search_vector
from psycopg import sql


@pytest.fixture(autouse=True)
def _restore_embedder_singleton() -> Iterator[None]:
    """Undo whatever a test left in the lazy embedder singleton.

    The unit tests above the integration block install `_FakeModel`s via
    `_load_embedder()` and never reset; the session-scoped Postgres seeding
    then called `.encode` on a fake and every integration test errored
    (CI runs 74-76 on PR #14; reproducible serially on v2). Restoring the
    previous value, rather than clearing, keeps the real model cached across
    the integration tests.
    """
    before = index_module._embedder
    yield
    with index_module._embed_lock:
        index_module._embedder = before


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = _REPO_ROOT / "docker" / "initdb" / "01-schema.sql"
_ADMIN_DSN = "postgresql://homelib:homelib_local_dev@localhost:5432/postgres"
# The throwaway database name must be unique per test PROCESS, not constant.
# Two test runs against the same Postgres both DROP and CREATE this name, so
# whichever drops second deletes the other's database out from under it —
# mid-test, with connections already open. That is not hypothetical: CI run
# 12259 failed with `database "homelib_test_index" does not exist` on six
# tests while the identical push run passed, because a push and its
# pull_request fire two runs of the same commit on the same host.
#
# The pid separates processes on one host; the CI run id is folded in so two
# runners sharing one Postgres server stay disjoint too.
_TEST_DB_NAME = f"homelib_test_index_{os.environ.get('GITHUB_RUN_ID', 'local')}_{os.getpid()}"
_TEST_DSN = f"postgresql://homelib:homelib_local_dev@localhost:5432/{_TEST_DB_NAME}"


# ── fakes for unit tests: no Postgres, no embedding model ──────────────────


class _FakeCursor:
    """Records every `execute()` call; replays one queued `fetchall()` result
    per call, in the order `index.py` is expected to issue them (main query
    first, then one `blocks` lookup per hit for `_first_page`).
    """

    def __init__(self, responses: Sequence[list[tuple[Any, ...]]]) -> None:
        self._responses = list(responses)
        self.queries: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> None:
        self.queries.append((query, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._responses.pop(0)

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _row(
    chunk_id: str,
    score: float,
    *,
    book_id: str = "book-1",
    section_path: list[str] | None = None,
    text: str = "some chunk text",
    block_ids: list[str] | None = None,
) -> tuple[Any, ...]:
    return (
        chunk_id,
        book_id,
        section_path if section_path is not None else ["Chapter 1"],
        text,
        block_ids if block_ids is not None else [],
        score,
    )


def _connect_returning(
    monkeypatch: pytest.MonkeyPatch, responses: Sequence[list[tuple[Any, ...]]]
) -> _FakeCursor:
    cursor = _FakeCursor(responses)
    monkeypatch.setattr(index_module, "_connect", lambda: _FakeConnection(cursor))
    return cursor


def _connect_never_called(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail() -> _FakeConnection:
        raise AssertionError("_connect must not be called")

    monkeypatch.setattr(index_module, "_connect", _fail)


# ── validation (both arms) ──────────────────────────────────────────────────


def test_search_lexical_empty_query_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _connect_never_called(monkeypatch)

    with pytest.raises(ValueError, match="empty"):
        search_lexical("   ", 5)


@pytest.mark.parametrize("k", [0, -1, -100])
def test_search_lexical_non_positive_k_raises(monkeypatch: pytest.MonkeyPatch, k: int) -> None:
    _connect_never_called(monkeypatch)

    with pytest.raises(ValueError):
        search_lexical("a valid query", k)


def test_search_vector_empty_query_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _connect_never_called(monkeypatch)
    monkeypatch.setattr(
        index_module,
        "_embed_query",
        lambda q: (_ for _ in ()).throw(AssertionError("_embed_query must not be called")),
    )

    with pytest.raises(ValueError, match="empty"):
        search_vector("", 5)


@pytest.mark.parametrize("k", [0, -1, -100])
def test_search_vector_non_positive_k_raises(monkeypatch: pytest.MonkeyPatch, k: int) -> None:
    _connect_never_called(monkeypatch)
    monkeypatch.setattr(
        index_module,
        "_embed_query",
        lambda q: (_ for _ in ()).throw(AssertionError("_embed_query must not be called")),
    )

    with pytest.raises(ValueError):
        search_vector("a valid query", k)


# ── search_lexical: query shape, mapping, ranking ───────────────────────────


def test_search_lexical_query_is_parameterized_not_interpolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = _connect_returning(monkeypatch, [[]])

    search_lexical("compound interest", 7)

    query, params = cursor.queries[0]
    assert "%s" in query
    assert "compound interest" not in query  # never string-interpolated into the SQL text
    assert params == ("compound interest", "compound interest", 7)


def test_search_lexical_maps_rows_to_hits_dense_rank_and_score_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_row("c1", 0.9), _row("c2", 0.5), _row("c3", 0.1)]
    _connect_returning(monkeypatch, [rows])

    hits = search_lexical("q", 3)

    assert [h.chunk_id for h in hits] == ["c1", "c2", "c3"]
    assert [h.rank for h in hits] == [1, 2, 3]
    assert [h.score for h in hits] == [0.9, 0.5, 0.1]
    assert all(h.page is None for h in hits)  # empty block_ids in the fixture rows


def test_search_lexical_page_uses_first_block_with_page_in_block_ids_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_row = _row("c1", 0.9, block_ids=["b1", "b2", "b3"])
    blocks_lookup = [("b1", None), ("b2", 42), ("b3", 99)]
    cursor = _connect_returning(monkeypatch, [[main_row], blocks_lookup])

    hits = search_lexical("q", 1)

    assert hits[0].page == 42  # first block IN block_ids ORDER that has a page, not lowest value
    blocks_query, blocks_params = cursor.queries[1]
    assert "blocks" in blocks_query
    assert blocks_params == (["b1", "b2", "b3"],)


def test_search_lexical_page_none_when_no_block_has_page(monkeypatch: pytest.MonkeyPatch) -> None:
    main_row = _row("c1", 0.9, block_ids=["b1", "b2"])
    blocks_lookup = [("b1", None), ("b2", None)]
    _connect_returning(monkeypatch, [[main_row], blocks_lookup])

    hits = search_lexical("q", 1)

    assert hits[0].page is None


def test_search_lexical_page_none_when_block_ids_empty_skips_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_row = _row("c1", 0.9, block_ids=[])
    cursor = _connect_returning(monkeypatch, [[main_row]])

    hits = search_lexical("q", 1)

    assert hits[0].page is None
    assert len(cursor.queries) == 1  # no blocks lookup issued for an empty block_ids list


def test_search_lexical_propagates_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail() -> _FakeConnection:
        raise psycopg.OperationalError("simulated connection failure")

    monkeypatch.setattr(index_module, "_connect", _fail)

    with pytest.raises(psycopg.OperationalError):
        search_lexical("q", 5)


# ── search_vector: embedding seam, query shape, mapping, ranking ───────────


def test_search_vector_embeds_query_and_uses_parameterized_cast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(index_module, "_embed_query", lambda q: [0.1, 0.2, 0.3])
    cursor = _connect_returning(monkeypatch, [[]])

    search_vector("compound interest", 4)

    query, params = cursor.queries[0]
    assert "::vector" in query
    assert "%s" in query
    vector_literal, vector_literal_again, k = params
    assert vector_literal == vector_literal_again == "[0.1,0.2,0.3]"
    assert k == 4


def test_search_vector_maps_rows_to_hits_dense_rank_and_score_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(index_module, "_embed_query", lambda q: [0.1, 0.2, 0.3])
    rows = [_row("v1", 0.95), _row("v2", 0.6), _row("v3", 0.2)]
    _connect_returning(monkeypatch, [rows])

    hits = search_vector("q", 3)

    assert [h.chunk_id for h in hits] == ["v1", "v2", "v3"]
    assert [h.rank for h in hits] == [1, 2, 3]
    assert [h.score for h in hits] == [0.95, 0.6, 0.2]


def test_search_vector_propagates_embedder_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _connect_never_called(monkeypatch)

    def _fail(q: str) -> list[float]:
        raise RuntimeError("simulated embedding-model load failure")

    monkeypatch.setattr(index_module, "_embed_query", _fail)

    with pytest.raises(RuntimeError, match="simulated embedding"):
        search_vector("q", 5)


def test_search_vector_propagates_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_module, "_embed_query", lambda q: [0.1, 0.2])

    def _fail() -> _FakeConnection:
        raise psycopg.OperationalError("simulated connection failure")

    monkeypatch.setattr(index_module, "_connect", _fail)

    with pytest.raises(psycopg.OperationalError):
        search_vector("q", 5)


def test_dsn_reads_database_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://custom/db")
    assert index_module._dsn() == "postgresql://custom/db"


def test_load_embedder_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeModel:
        def encode(self, q: str) -> list[float]:
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(index_module, "SentenceTransformer", lambda _name: _FakeModel())
    index_module._reset_embedder_for_tests()

    first = index_module._load_embedder()
    second = index_module._load_embedder()

    assert first is second


def test_embed_query_returns_float_list(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeModel:
        def encode(self, q: str) -> list[float]:
            return [0.5, 0.25]

    monkeypatch.setattr(index_module, "SentenceTransformer", lambda _name: _FakeModel())
    index_module._reset_embedder_for_tests()

    assert index_module._embed_query("hello") == [0.5, 0.25]


def test_reset_embedder_for_tests_clears_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeModel:
        pass

    created: list[_FakeModel] = []

    def _factory(_name: str) -> _FakeModel:
        model = _FakeModel()
        created.append(model)
        return model

    monkeypatch.setattr(index_module, "SentenceTransformer", _factory)
    index_module._reset_embedder_for_tests()
    index_module._load_embedder()
    index_module._reset_embedder_for_tests()
    index_module._load_embedder()

    assert len(created) == 2
    index_module._reset_embedder_for_tests()


def test_unit_fakes_do_not_leak_into_the_embedder_singleton() -> None:
    """Runs right after the three tests that install fakes; red without the
    autouse restore fixture, because the last fake had no `encode` at all."""
    leaked = index_module._embedder
    assert leaked is None or hasattr(leaked, "encode"), type(leaked).__name__


# ── integration tests: real Postgres, real embedding model ─────────────────

_FIXTURE_BOOK_ID = "book-fixture"

_FIXTURE_CHUNKS: list[dict[str, Any]] = [
    {
        "chunk_id": "chunk-lex-exact",
        "block_id": "block-lex-exact",
        "text": "The reciprocal rank fusion algorithm combines two rankings into one.",
        "page": 10,
        "format": "txt",
    },
    {
        "chunk_id": "chunk-lex-scattered",
        "block_id": "block-lex-scattered",
        "text": (
            "Fusion cuisine is trendy right now. Reciprocal favors are common in "
            "politics. The military rank structure is strict. This algorithm "
            "textbook is quite old."
        ),
        "page": 11,
        "format": "txt",
    },
    {
        "chunk_id": "chunk-vec-semantic",
        "block_id": "block-vec-semantic",
        "text": (
            "Pollinating insects gather flower nectar and convert it into a "
            "sweet, viscous substance stored inside a hive."
        ),
        "page": None,
        "format": "epub",
    },
    {
        "chunk_id": "chunk-vec-distractor",
        "block_id": "block-vec-distractor",
        "text": "Quarterly tax filings require careful bookkeeping and prompt submission.",
        "page": 20,
        "format": "txt",
    },
    {
        "chunk_id": "chunk-epub-only",
        "block_id": "block-epub-only",
        "text": "The lantern flickered against damp stone walls in the abandoned corridor.",
        "page": None,
        "format": "epub",
    },
    {
        "chunk_id": "chunk-extra-mountain",
        "block_id": "block-extra-mountain",
        "text": "Mountain climbers checked their oxygen tanks before the final ascent.",
        "page": 30,
        "format": "txt",
    },
    {
        "chunk_id": "chunk-extra-market",
        "block_id": "block-extra-market",
        "text": "The stock market rallied sharply after the central bank announcement.",
        "page": 31,
        "format": "txt",
    },
]


def _seed(dsn: str) -> None:
    """Seed the fixture book/blocks/chunks/embeddings using the SAME embedder
    `search_vector` uses at query time, so vector similarity is meaningful.
    """
    index_module._reset_embedder_for_tests()
    model = index_module._load_embedder()  # test setup, same-package seam
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO books (book_id, title, authors, language, source_url, license_note) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (_FIXTURE_BOOK_ID, "Fixture Book", ["Fixture Author"], "en", "", ""),
        )
        for ordinal, spec in enumerate(_FIXTURE_CHUNKS):
            cur.execute(
                "INSERT INTO blocks (block_id, book_id, ordinal, section_path, text, "
                "char_start, char_end, format, page, spine_index, anchor) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    spec["block_id"],
                    _FIXTURE_BOOK_ID,
                    ordinal,
                    ["Chapter 1"],
                    spec["text"],
                    0,
                    len(spec["text"]),
                    spec["format"],
                    spec["page"],
                    None,
                    None,
                ),
            )
            cur.execute(
                "INSERT INTO chunks (chunk_id, book_id, block_ids, section_path, text, "
                "char_start, char_end) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    spec["chunk_id"],
                    _FIXTURE_BOOK_ID,
                    [spec["block_id"]],
                    ["Chapter 1"],
                    spec["text"],
                    0,
                    len(spec["text"]),
                ),
            )
            embedding = [float(x) for x in model.encode(spec["text"])]
            vector_literal = index_module._vector_literal(embedding)
            cur.execute(
                "INSERT INTO chunk_embeddings (chunk_id, embedding) VALUES (%s, %s::vector)",
                (spec["chunk_id"], vector_literal),
            )
        conn.commit()


def test_throwaway_database_name_is_unique_per_process() -> None:
    """A constant name lets two concurrent runs delete each other's database.

    Guards the exact regression behind CI run 12259: a push and its
    pull_request run the same commit on the same host, both dropped and
    recreated a fixed `homelib_test_index`, and six tests failed with
    `database ... does not exist` while the identical push run passed.
    """
    assert _TEST_DB_NAME != "homelib_test_index", "throwaway db name is constant again"
    assert str(os.getpid()) in _TEST_DB_NAME
    assert _TEST_DSN.endswith(_TEST_DB_NAME)


@pytest.fixture(scope="session")
def _test_db_dsn() -> Iterator[str]:
    try:
        admin_conn = psycopg.connect(_ADMIN_DSN, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"no reachable Postgres server for integration tests: {exc}")

    with admin_conn, admin_conn.cursor() as cur:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(_TEST_DB_NAME)))
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(_TEST_DB_NAME)))

    schema_sql = _SCHEMA_PATH.read_text()
    with psycopg.connect(_TEST_DSN) as conn, conn.cursor() as cur:
        cur.execute(schema_sql)
        conn.commit()

    _seed(_TEST_DSN)

    try:
        yield _TEST_DSN
    finally:
        with (
            psycopg.connect(_ADMIN_DSN, autocommit=True) as teardown_conn,
            teardown_conn.cursor() as cur,
        ):
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(_TEST_DB_NAME)
                )
            )


@pytest.fixture
def _seeded_db(_test_db_dsn: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Point `index.py`'s `_connect()` at the throwaway test database for one test."""
    monkeypatch.setenv("DATABASE_URL", _test_db_dsn)
    return _test_db_dsn


@pytest.mark.integration
def test_search_lexical_ranks_exact_phrase_above_scattered_terms(_seeded_db: str) -> None:
    hits = search_lexical("reciprocal rank fusion algorithm", 10)

    ids = [h.chunk_id for h in hits]
    assert "chunk-lex-exact" in ids
    assert "chunk-lex-scattered" in ids
    assert ids.index("chunk-lex-exact") < ids.index("chunk-lex-scattered")


@pytest.mark.integration
def test_search_vector_finds_semantic_match_without_shared_terms(_seeded_db: str) -> None:
    query = "how do bees make honey"

    vector_hits = search_vector(query, 5)
    lexical_hits = search_lexical(query, 5)

    assert "chunk-vec-semantic" in [h.chunk_id for h in vector_hits]
    assert "chunk-vec-semantic" not in [h.chunk_id for h in lexical_hits]


@pytest.mark.integration
def test_hits_are_rank_ordered_and_capped_at_k_lexical(_seeded_db: str) -> None:
    uncapped = search_lexical("reciprocal rank fusion algorithm", 10)
    assert len(uncapped) >= 2
    assert [h.rank for h in uncapped] == list(range(1, len(uncapped) + 1))
    scores = [h.score for h in uncapped]
    assert scores == sorted(scores, reverse=True)

    capped = search_lexical("reciprocal rank fusion algorithm", 1)
    assert len(capped) == 1
    assert capped[0].rank == 1
    assert capped[0].chunk_id == uncapped[0].chunk_id


@pytest.mark.integration
def test_hits_are_rank_ordered_and_capped_at_k_vector(_seeded_db: str) -> None:
    uncapped = search_vector("honey bees pollination", 10)
    assert len(uncapped) >= 2
    assert [h.rank for h in uncapped] == list(range(1, len(uncapped) + 1))
    scores = [h.score for h in uncapped]
    assert scores == sorted(scores, reverse=True)

    capped = search_vector("honey bees pollination", 1)
    assert len(capped) == 1
    assert capped[0].rank == 1
    assert capped[0].chunk_id == uncapped[0].chunk_id


@pytest.mark.integration
def test_page_is_none_for_epub_only_chunk(_seeded_db: str) -> None:
    hits = search_lexical("lantern flickered corridor", 5)

    assert hits
    assert hits[0].chunk_id == "chunk-epub-only"
    assert hits[0].page is None


@pytest.mark.integration
def test_page_is_present_for_non_epub_chunk(_seeded_db: str) -> None:
    hits = search_lexical("reciprocal rank fusion algorithm", 5)

    hit = next(h for h in hits if h.chunk_id == "chunk-lex-exact")
    assert hit.page == 10
