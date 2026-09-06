"""Behavioural tests for `apps.store.judge_ops` — C6's online judge.

Same scripted-client pattern `evals/tests/test_judge.py` uses for
`evals.judge.judge` itself: a fake `OpenAICompatibleClient` that replays
canned JSON bodies, so nothing here reaches a live LLM.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from homelib_rag.answer import ChatMessage, LLMResponse, LLMUsage

from apps.store.judge_ops import judge_recent_rows
from apps.store.sqlite import connect, migrate


class _ScriptedJudgeClient:
    """Replays one canned judge-score body per call, in order."""

    model = "fake/judge"

    def __init__(self, bodies: list[str]) -> None:
        self._bodies = list(bodies)
        self.calls: list[list[ChatMessage]] = []

    def chat(
        self,
        messages: Any,
        *,
        tools: Any = None,
        response_format: Any = None,
        max_tokens: int = 400,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        body = self._bodies[min(len(self.calls) - 1, len(self._bodies) - 1)]
        return LLMResponse(content=body, usage=LLMUsage(prompt_tokens=1, completion_tokens=1))


def _judge_body(relevance: int) -> str:
    return json.dumps(
        {
            "faithfulness": 4,
            "relevance": relevance,
            "citation_quality": 3,
            "suggested_score": 4,
            "verdict": "ok",
        }
    )


def _db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "judge.sqlite")
    migrate(conn)
    return conn


def _insert_row(
    conn: sqlite3.Connection,
    *,
    request_id: str,
    question: str = "does it jump?",
    answer: str = "Yes, it jumps.",
    relevance: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO query_log ("
        "request_id, ts, latency_ms, arm, k, rerank, rewrite, model, "
        "tokens_prompt, tokens_completion, query_sha256_prefix, degraded, relevance"
        ") VALUES (?, datetime('now'), 100, 'hybrid', 5, 0, 0, 'm', 10, 5, ?, 0, ?)",
        (request_id, "a" * 16, relevance),
    )
    conn.execute(
        "INSERT INTO answer_log (request_id, question, answer, created_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (request_id, question, answer),
    )
    conn.commit()


def test_judge_recent_fills_only_unjudged_rows(tmp_path: Path) -> None:
    """Two answer-logged rows, one already judged: `judge_recent_rows` scores
    only the unjudged one, writes `relevance`/`judge_model` back for it, and
    leaves the already-judged row's fields untouched."""
    conn = _db(tmp_path)
    _insert_row(conn, request_id="already-judged", relevance="5")
    _insert_row(conn, request_id="needs-judging", relevance=None)
    fake_client = _ScriptedJudgeClient([_judge_body(relevance=4)])

    judged = judge_recent_rows(conn, n=50, client=fake_client)

    assert [row.request_id for row in judged] == ["needs-judging"]
    assert judged[0].relevance == 4
    assert judged[0].judge_model == "fake/judge"
    # Exactly one LLM call was made — the already-judged row was never sent.
    assert len(fake_client.calls) == 1

    updated = conn.execute(
        "SELECT relevance, judge_model FROM query_log WHERE request_id = 'needs-judging'"
    ).fetchone()
    assert tuple(updated) == ("4", "fake/judge")

    untouched = conn.execute(
        "SELECT relevance, judge_model FROM query_log WHERE request_id = 'already-judged'"
    ).fetchone()
    assert tuple(untouched) == ("5", None)


def test_judge_recent_rows_is_idempotent_across_two_runs(tmp_path: Path) -> None:
    """A second run over the same store re-scores nothing: the first run's
    write already took the row out of the `relevance IS NULL` selection."""
    conn = _db(tmp_path)
    _insert_row(conn, request_id="r1", relevance=None)
    fake_client = _ScriptedJudgeClient([_judge_body(relevance=3)])

    first = judge_recent_rows(conn, n=50, client=fake_client)
    second = judge_recent_rows(conn, n=50, client=fake_client)

    assert len(first) == 1
    assert second == []
    assert len(fake_client.calls) == 1


def test_judge_recent_rows_respects_n(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    for i in range(3):
        _insert_row(conn, request_id=f"r{i}", relevance=None)
    fake_client = _ScriptedJudgeClient([_judge_body(relevance=5)])

    judged = judge_recent_rows(conn, n=2, client=fake_client)

    assert len(judged) == 2
