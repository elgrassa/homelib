"""SQLite dispatch on homelib_rag.index when HOMELIB_SQLITE_PATH is set."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest
from homelib_rag import agent as agent_module
from homelib_rag import answer as answer_module
from homelib_rag import index as index_module
from homelib_rag.answer import LLMResponse, LLMUsage
from homelib_rag.models import Hit

from apps.store.sqlite import bump_index_revision, connect, migrate, rebuild_chunks_fts


@pytest.fixture
def sqlite_dispatch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    db_path = tmp_path / "dispatch.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-d", "Dispatch", "[]", "public_domain"),
    )
    text = "Dispatch test chunk about leadership and focus."
    conn.execute(
        """
        INSERT INTO blocks (
            block_id, book_id, ordinal, section_path, text, char_start, char_end, format
        ) VALUES ('bd-0', 'book-d', 0, '["Ch1"]', ?, 0, ?, 'txt')
        """,
        (text, len(text)),
    )
    conn.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('cd-0', 'book-d', '["bd-0"]', '["Ch1"]', ?, 0, ?)
        """,
        (text, len(text)),
    )
    vector = np.zeros(384, dtype=np.float32)
    vector[0] = 1.0
    conn.execute(
        """
        INSERT INTO chunk_embeddings (chunk_id, embedding, model, dim)
        VALUES ('cd-0', ?, 'test-model', 384)
        """,
        (json.dumps(vector.tolist()),),
    )
    rebuild_chunks_fts(conn)
    bump_index_revision(conn)
    conn.commit()

    def _fake_embed(_q: str) -> list[float]:
        return vector.tolist()

    monkeypatch.setattr("homelib_rag.sqlite_index._embed_query", lambda q: vector)
    monkeypatch.setattr(index_module, "_embed_query", _fake_embed)
    yield conn
    conn.close()


def test_index_search_lexical_dispatches_to_sqlite(sqlite_dispatch_db: sqlite3.Connection) -> None:
    hits = index_module.search_lexical("leadership focus", 5)
    assert hits
    assert hits[0].chunk_id == "cd-0"


def test_index_search_vector_dispatches_to_sqlite(sqlite_dispatch_db: sqlite3.Connection) -> None:
    hits = index_module.search_vector("leadership focus", 5)
    assert hits
    assert hits[0].chunk_id == "cd-0"


# ── H1: answer() and agent.search_catalog() must dispatch to SQLite too ─────
#
# Retrieval already dispatched on HOMELIB_SQLITE_PATH, but the synthesis step
# looked book titles up in Postgres and the catalog tool queried Postgres, so
# on a SQLite-only host (Streamlit Cloud demo) every ask came back degraded
# with "failed to load book metadata". These pin the SQLite branch end to end
# with a scripted LLM — no Postgres, no network, no monkeypatch of the seam.


class _ScriptedClient:
    model = "fake-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)

    def chat(
        self,
        messages: object,
        *,
        tools: object = None,
        response_format: object = None,
        max_tokens: int = 400,
    ) -> LLMResponse:
        return self._responses.pop(0)


def test_answer_book_metadata_dispatches_to_sqlite(
    sqlite_dispatch_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    meta = answer_module._book_metadata(["book-d", "missing"])
    assert meta == {"book-d": ("Dispatch", [])}


def test_answer_book_metadata_decodes_authors_json(
    sqlite_dispatch_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sqlite_dispatch_db.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-a", "Authored", json.dumps(["Ada Lovelace", "Charles Babbage"]), "public_domain"),
    )
    sqlite_dispatch_db.commit()
    meta = answer_module._book_metadata(["book-a"])
    assert meta["book-a"] == ("Authored", ["Ada Lovelace", "Charles Babbage"])


def test_answer_end_to_end_not_degraded_on_sqlite_only_host(
    sqlite_dispatch_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reviewer-visible symptom: with only SQLite reachable, a grounded
    answer must come back cited and non-degraded, with the title filled in
    server-side from the SQLite books table."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    hit = Hit(
        chunk_id="cd-0",
        book_id="book-d",
        score=1.0,
        rank=1,
        text="Dispatch test chunk about leadership and focus.",
        section_path=["Ch1"],
        page=None,
    )
    client = _ScriptedClient(
        [
            LLMResponse(
                content=json.dumps(
                    {
                        "answer": "It is about leadership.",
                        "citations": [{"passage": 1, "quote": "leadership and focus"}],
                    }
                ),
                usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
            )
        ]
    )
    result = answer_module.answer("what is it about?", [hit], client=client, arm_used="hybrid")
    assert result.degraded is False
    assert result.citations[0].chunk_id == "cd-0"
    assert result.citations[0].book_title == "Dispatch"


def test_agent_search_catalog_uses_sqlite_when_path_set(
    sqlite_dispatch_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`agent.search_catalog` is bound in three places (API deps, the roadmap
    wrapper, the tool table); dispatching inside it covers all three."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sqlite_dispatch_db.execute(
        """
        INSERT INTO catalog (ol_key, title, authors, subjects, first_publish_year, description)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "/works/OL1W",
            "Leading Teams",
            json.dumps(["Grace Hopper"]),
            json.dumps(["Leadership", "Management"]),
            1990,
            None,
        ),
    )
    sqlite_dispatch_db.commit()

    by_title = agent_module.search_catalog("leading")
    assert [e.ol_key for e in by_title] == ["/works/OL1W"]
    assert by_title[0].authors == ["Grace Hopper"]
    assert by_title[0].subjects == ["Leadership", "Management"]

    by_subject = agent_module.search_catalog("anything", subjects=["management"])
    assert [e.ol_key for e in by_subject] == ["/works/OL1W"]

    assert agent_module.search_catalog("nomatch") == []
