"""Online judge on live traffic — core logic behind `scripts/judge_recent.py`.

C6 (specs/monitoring.md "Online judge"): score real `/v1/ask` traffic with
the same LLM-as-judge used for offline eval (`evals.judge`, imported here —
never copied), so Observatory's `judged_relevance` chart reflects genuine
production answers, not only the eval fixtures.

Only rows with a matching `answer_log` entry can be judged at all —
`answer_log` exists only when the API ran with `HOMELIB_LOG_ANSWERS=1`
(default off; see specs/monitoring.md's privacy note), so a deployment that
never opted in simply has nothing here to score. `judge_recent_rows` is
idempotent: it selects only `query_log` rows with `relevance IS NULL`, so a
row that has already been judged is never re-judged, and a row the judge
failed to parse (excluded, not marked) is naturally retried on the next run.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from homelib_rag.answer import LLMUnreachableError, OpenAICompatibleClient, default_llm_client

from evals.judge import JudgeParseError, judge

__all__ = ["JudgedRow", "judge_recent_rows"]

_JUDGE_VARIANT = "live"


@dataclass(frozen=True, slots=True)
class JudgedRow:
    """One row this run actually scored and wrote back."""

    request_id: str
    relevance: int
    judge_model: str


def _unjudged_rows(conn: sqlite3.Connection, n: int) -> list[tuple[str, str, str]]:
    rows = conn.execute(
        "SELECT ql.request_id, al.question, al.answer "
        "FROM query_log ql JOIN answer_log al ON al.request_id = ql.request_id "
        "WHERE ql.relevance IS NULL "
        "ORDER BY ql.ts DESC LIMIT ?",
        (n,),
    ).fetchall()
    return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]


def judge_recent_rows(
    conn: sqlite3.Connection,
    *,
    n: int = 50,
    client: OpenAICompatibleClient | None = None,
) -> list[JudgedRow]:
    """Judge up to `n` of the most recent unjudged, answer-logged rows.

    `client` is a test seam (a scripted `OpenAICompatibleClient`, same
    protocol `evals.judge.judge` already takes); production callers
    (`scripts/judge_recent.py`) leave it unset and get the real
    `default_llm_client()`.

    A row the judge cannot parse, or whose endpoint is unreachable, is
    skipped rather than marked — `relevance` stays NULL so the row is picked
    up again on the next run instead of being silently written off.
    """
    judge_client = client if client is not None else default_llm_client()
    judged: list[JudgedRow] = []
    for request_id, question, answer in _unjudged_rows(conn, n):
        try:
            score = judge(question, answer, [], client=judge_client, variant=_JUDGE_VARIANT)
        except (JudgeParseError, LLMUnreachableError):
            continue
        conn.execute(
            "UPDATE query_log SET relevance = ?, judge_model = ? WHERE request_id = ?",
            (str(score.relevance), score.judge_model, request_id),
        )
        judged.append(
            JudgedRow(
                request_id=request_id,
                relevance=score.relevance,
                judge_model=score.judge_model,
            )
        )
    conn.commit()
    return judged
