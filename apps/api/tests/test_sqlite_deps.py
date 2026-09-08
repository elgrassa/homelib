"""Direct unit tests for `apps.api.sqlite_deps.sqlite_get_book_block`.

Companion to the route-level coverage in `test_v2_routes.py`: these hit the
SQLite helper directly (no `TestClient`, no FastAPI wiring) against a
temporary, migrated store.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.api import sqlite_deps
from apps.store.sqlite import connect, migrate


def _seed_book_blocks(db: Path, book_id: str, texts: list[str]) -> None:
    """Migrate `db` (idempotent) and insert `book_id` with one block per text,
    dense ordinals starting at 0 — the same low-level pattern used by
    `packages/homelib-rag/tests/test_sqlite_index.py`."""
    conn = connect(db)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        (book_id, book_id, "[]", "public_domain"),
    )
    offset = 0
    for ordinal, text in enumerate(texts):
        conn.execute(
            """
            INSERT INTO blocks (
                block_id, book_id, ordinal, section_path, text, char_start, char_end, format
            ) VALUES (?, ?, ?, '["Ch1"]', ?, ?, ?, 'txt')
            """,
            (f"{book_id}-b{ordinal}", book_id, ordinal, text, offset, offset + len(text)),
        )
        offset += len(text)
    conn.commit()
    conn.close()


@pytest.fixture()
def sqlite_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "blocks.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db))
    return db


def test_sqlite_get_book_block_returns_block_at_ordinal(sqlite_env: Path) -> None:
    _seed_book_blocks(sqlite_env, "book-a", ["First page.", "Second page."])

    block = sqlite_deps.sqlite_get_book_block("book-a", 1)

    assert block.book_id == "book-a"
    assert block.ordinal == 1
    assert block.text == "Second page."
    assert block.block_id == "book-a-b1"


def test_sqlite_get_book_block_raises_keyerror_when_missing(sqlite_env: Path) -> None:
    """Unknown book, and ordinal past the last block, both miss.

    The function's own docstring/callers call this a "KeyError" case, but the
    implementation raises `LookupError` directly (`apps/api/main.py` catches
    exactly `LookupError` at this seam and re-raises as `KeyError` for the
    route layer) — assert the type it actually raises.
    """
    _seed_book_blocks(sqlite_env, "book-a", ["Only page."])

    with pytest.raises(LookupError):
        sqlite_deps.sqlite_get_book_block("no-such-book", 0)

    with pytest.raises(LookupError):
        sqlite_deps.sqlite_get_book_block("book-a", 5)


def test_sqlite_get_book_block_ignores_other_books_same_ordinal(sqlite_env: Path) -> None:
    _seed_book_blocks(sqlite_env, "book-a", ["A at ordinal zero."])
    _seed_book_blocks(sqlite_env, "book-b", ["B at ordinal zero."])

    block = sqlite_deps.sqlite_get_book_block("book-b", 0)

    assert block.book_id == "book-b"
    assert block.text == "B at ordinal zero."


def test_open_store_migrates_each_path_only_once(
    sqlite_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: migrate-on-every-open held SQLite locks under Ask and made
    `/health` wait for the whole LLM call (client timeouts / UI hang)."""
    calls: list[Path] = []
    real_migrate = migrate

    def _counting_migrate(conn: object, target_version: int | None = None) -> None:
        calls.append(sqlite_env)
        real_migrate(conn, target_version)  # type: ignore[arg-type]

    sqlite_deps.reset_migration_cache_for_tests()
    monkeypatch.setattr(sqlite_deps, "migrate", _counting_migrate)

    with sqlite_deps.open_store() as conn:
        conn.execute("SELECT 1")
    with sqlite_deps.open_store() as conn:
        conn.execute("SELECT 1")
    with sqlite_deps.open_store() as conn:
        conn.execute("SELECT 1")

    assert len(calls) == 1


def test_sqlite_health_snapshot_returns_reachable_and_counts(sqlite_env: Path) -> None:
    _seed_book_blocks(sqlite_env, "book-a", ["page"])
    sqlite_deps.reset_migration_cache_for_tests()

    ok, books, chunks = sqlite_deps.sqlite_health_snapshot()

    assert ok is True
    assert books == 1
    assert chunks == 0
