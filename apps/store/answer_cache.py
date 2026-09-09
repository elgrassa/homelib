"""Demo-only answer cache — C4b (specs/monitoring.md "Demo answer cache").

Read-through cache keyed by `sha256(normalised question | arm | model |
answer-prompt hash | k | rewrite | index_revision)`, read and written ONLY
when `APP_MODE=demo` (`apps/api/main.py`'s `_demo_cache_enabled` — never in
selfhosted mode, so a self-hosted reader always gets a live retrieve+LLM
answer).

`k`, `rewrite`, and `index_revision` belong in the key so a changed request
or corpus cannot reuse an incompatible cached answer (audit S01).

The prompt hash reuses `evals.judge.prompt_hash` (imported, never copied)
against `homelib_rag.answer`'s own `_SYSTEM_PROMPT`, the same
sha256("|".join([version, template, schema_shape])) utility the judge's own
drift detector uses (see `evals/tests/test_prompt_hash.py`) — applied here to
the answer-synthesis prompt instead of the judge prompt. A change to that
prompt's wording, version, or output shape moves every cache key, so a
stale cached answer from a retired prompt can never match again; there is no
separate manual cache-bust step.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime

from homelib_rag.answer import _SYSTEM_PROMPT as _ANSWER_SYSTEM_PROMPT
from homelib_rag.answer import AskResponse

from evals.judge import prompt_hash

__all__ = ["cache_key", "lookup", "store"]

_ANSWER_PROMPT_VERSION = "1"
# A compact description of answer()'s output shape — bumped alongside a
# change to what AskResponse/citations actually contain, same idea as
# evals.judge.JUDGE_SCHEMA_SHAPE but hand-written since answer()'s raw LLM
# output shape (_RawAnswer) is private to homelib_rag.answer.
_ANSWER_SCHEMA_SHAPE = "answer:str,citations:list"

_ANSWER_PROMPT_HASH = prompt_hash(
    _ANSWER_PROMPT_VERSION, _ANSWER_SYSTEM_PROMPT, _ANSWER_SCHEMA_SHAPE
)


def _normalize_question(question: str) -> str:
    """Whitespace-collapsed, case-folded — "Does it Jump?" and "does it
    jump?  " must hit the same cache entry."""
    return " ".join(question.strip().lower().split())


def cache_key(
    question: str,
    *,
    arm: str,
    model: str,
    k: int = 5,
    rewrite: bool = False,
    index_revision: str = "",
) -> str:
    joined = "|".join(
        [
            _normalize_question(question),
            arm,
            model,
            _ANSWER_PROMPT_HASH,
            str(k),
            "1" if rewrite else "0",
            index_revision,
        ]
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def lookup(conn: sqlite3.Connection, key: str) -> AskResponse | None:
    """`None` on a miss. Raises on a genuinely broken store (bad JSON, no
    `answer_cache` table) — the caller (`apps/api/main.py`'s
    `_maybe_cache_lookup`) is the one that decides a broken cache degrades
    to "treat as a miss" rather than a 500, matching every other sqlite
    helper's best-effort contract.
    """
    row = conn.execute("SELECT answer FROM answer_cache WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return AskResponse.model_validate_json(row[0])


def store(conn: sqlite3.Connection, key: str, response: AskResponse) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO answer_cache (key, created_at, answer) VALUES (?, ?, ?)",
        (key, datetime.now(UTC).isoformat(), response.model_dump_json()),
    )
    conn.commit()
