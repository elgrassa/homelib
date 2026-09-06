"""Retrieval-arm bake-off — see specs/evals-retrieval.md.

Answers, on evidence, which retrieval arm ships as the production default.
Four arms answer the same ground-truth questions through the real
`homelib_rag` path — `lexical` (Postgres FTS), `vector` (pgvector cosine),
`hybrid` (RRF fusion of both), and `hybrid_rerank` (RRF plus the
cross-encoder) — and each is scored with hit-rate@5 and MRR@5.

Deliberately LLM-free per query. Retrieval is the only thing measured, so
the default run makes zero chat-model calls and finishes over the whole
235-row ground-truth set in seconds rather than the ~50 minutes
`evals/llm_eval.py` needs. That is what makes it affordable to run the
comparison over EVERY row instead of a sample, which in turn is why the
question budget below defaults to "all rows". The one optional LLM step is
`--rewrite`, which routes each question through `homelib_rag.rewrite` first;
it is off by default precisely so the headline numbers stay LLM-free, and
the report always states which way it ran.

Two honesty invariants, both of which hide a broken measurement if dropped:

- The arm reported is the arm that ACTUALLY ran. `hybrid_search` returns the
  mode it really executed and degrades to a single arm when a backend is
  down; `rerank` returns `None` when the cross-encoder cannot load. A
  `hybrid` row silently computed over lexical-only results is not a hybrid
  measurement, so every query records its `arm_used`, every row carries a
  `degraded` count, and an arm that degraded on every query can never be
  crowned winner.
- A ground-truth row whose `chunk_id` is not in the current index (corpus
  drift) is EXCLUDED from scoring and counted separately in the report —
  never left in the denominator, where it would score as a miss it was
  never given a fair chance to hit. `n` is therefore the number of rows
  actually scored, and `skipped_missing_chunk` is reported next to it.

The database is only ever read: the sole statement this module issues is a
`SELECT chunk_id FROM chunks` used for the drift check. Another process owns
that data.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homelib_rag.models import Hit
from pydantic import BaseModel, ConfigDict

# `just eval-retrieval` runs this file as a script (`python
# evals/retrieval_eval.py`), which puts `evals/` — not the repo root — on
# sys.path, so the sibling `evals.*` imports below would not resolve. `uv`
# installs no top-level `homelib` package (pyproject sets `package = false`),
# so there is nothing else to put the root there. Prepending it here keeps
# the justfile recipe and `python -m evals.retrieval_eval` both working from
# one entry point. Mirrors evals/llm_eval.py.
if __package__ in (None, ""):  # pragma: no cover - only on the script path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.gate import Baseline, append_history, compare_to_baseline, load_baseline
from evals.ground_truth import GROUND_TRUTH_PATH, GroundTruthRow

# hit-rate@k and MRR@k are NOT reimplemented here. `evals/metrics.py` owns
# them, hand-tested against the toy cases in specs/evals-retrieval.md
# ("Named red tests"), and is re-exported so the spec's stated
# `evals/retrieval_eval.py` surface is importable from one place. Note the
# signatures are metrics.py's mapping form (query id -> ranked ids), which is
# richer than the positional-list sketch in the spec: it supports more than
# one relevant id per query and does not depend on two lists staying aligned.
from evals.metrics import hit_rate_at_k, hit_rate_book, mrr_at_k

if TYPE_CHECKING:
    import psycopg

__all__ = [
    "ARMS",
    "DEFAULT_DATABASE_URL",
    "DEFAULT_K",
    "DEFAULT_QUESTION_BUDGET",
    "REPORT_PATH",
    "ArmMetrics",
    "BookMetrics",
    "GroundTruthRow",
    "QueryOutcome",
    "hit_rate_at_k",
    "hit_rate_book",
    "load_indexed_chunk_ids",
    "load_questions",
    "mrr_at_k",
    "run_all_arms",
    "run_arm",
    "split_on_index",
    "write_report",
]

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPO_ROOT / "evals" / "results" / "retrieval.md"
BASELINE_PATH = REPO_ROOT / "evals" / "eval-baseline.json"
HISTORY_PATH = REPO_ROOT / "evals" / "history.jsonl"

#: The four arms compared, in the order specs/evals-retrieval.md §4.4 names
#: them. `hybrid_rerank` last because it is the one the committed baseline
#: floors are written against.
ARMS: tuple[str, ...] = ("lexical", "vector", "hybrid", "hybrid_rerank")

#: Retrieval depth per question. 5 matches `AskRequest.k`'s default in
#: specs/api.md, so the eval measures the arms under production conditions,
#: and it is the `k` the `hit_rate_at_5` / `mrr_at_5` metric names refer to.
#: Override with `--k`; the report always states the value actually used.
DEFAULT_K = 5

#: How many ground-truth rows to score per arm. `None` means EVERY row in
#: `evals/ground_truth.jsonl` (235 at time of writing) — the default,
#: because this eval is LLM-free and therefore cheap enough not to sample.
#: An `int` caps coverage, spreading the picks round-robin across books
#: rather than truncating to whichever books happen to come first in the
#: file. Override with `--questions`; either way the report states which.
DEFAULT_QUESTION_BUDGET: int | None = None

#: Matches `homelib_rag.index._DEFAULT_DATABASE_URL`. Repeated rather than
#: imported because importing `homelib_rag.index` pulls in
#: `sentence_transformers` at import time, which the unit tests must not pay
#: for; `test_default_database_url_matches_the_index_module` pins the two
#: together so this copy cannot drift.
DEFAULT_DATABASE_URL = "postgresql://homelib:homelib_local_dev@localhost:5432/homelib"

_CONNECT_TIMEOUT_SECONDS = 10

# A four-way comparison is the rubric point; three arms and a winner is a
# different (smaller) claim than the one this report makes.
_MIN_ARMS_FOR_A_WINNER = 4

# Only the `hybrid_rerank.*` floors are this eval's to defend. The `judge.*`
# floor belongs to evals/llm_eval.py; comparing against it here would report
# it "missing" and paint every run red for a reason that has nothing to do
# with retrieval.
_RETRIEVAL_METRIC_PREFIX = "hybrid_rerank."

# The `arm_used` recorded when retrieval raised outright. Distinct from a
# degradation to a working sibling arm: nothing was retrieved at all.
_ARM_USED_ERROR = "error"


#: `(query, k, arm) -> (hits, arm_used)`. The seam the unit tests replace so
#: they can run the whole scoring path with no database and no model
#: downloads. `arm_used` is the arm that actually produced `hits`.
Retriever = Callable[[str, int, str], tuple[list[Hit], str]]

#: `query -> rewritten query`. Only invoked when `rewrite=True`.
Rewriter = Callable[[str], str]


# ── data contracts ──────────────────────────────────────────────────────────


class QueryOutcome(BaseModel):
    """What one arm actually returned for one ground-truth question."""

    model_config = ConfigDict(extra="allow")

    query_id: str
    question: str
    chunk_id: str
    book_id: str
    arm_requested: str
    arm_used: str
    ranked_chunk_ids: list[str]
    #: Same order/length as `ranked_chunk_ids` — the book id each ranked
    #: chunk belongs to, taken straight from `Hit.book_id` (no extra lookup
    #: needed: the index already attaches a chunk's book to every `Hit`).
    #: Powers `hit_rate_book` in `_score_book`, which a chunk-exact miss can
    #: still be a book-level hit against — see `evals/metrics.py`.
    ranked_book_ids: list[str] = []
    latency_ms: int

    @property
    def degraded(self) -> bool:
        """True when the arm that ran is not the arm that was asked for."""
        return self.arm_used != self.arm_requested


class BookMetrics(BaseModel):
    """One book's slice of an arm's score."""

    model_config = ConfigDict(extra="allow")

    hit_rate_at_5: float
    mrr_at_5: float
    n: int


class ArmMetrics(BaseModel):
    """One arm's score over the ground-truth set.

    `hit_rate_at_5` / `mrr_at_5` keep the field names specs/evals-retrieval.md
    fixes, and `k` records the depth they were actually computed at, so a run
    with `--k 10` is legible rather than mislabelled. `n` counts rows SCORED;
    `rows_loaded` and `skipped_missing_chunk` account for everything that did
    not make it that far, so coverage is never silently narrowed.
    """

    model_config = ConfigDict(extra="allow")

    arm: str
    rewrite: bool
    hit_rate_at_5: float
    mrr_at_5: float
    #: Book-level hit-rate@k (see `evals/metrics.py:hit_rate_book`): a hit if
    #: ANY top-k chunk belongs to the same book as the ground-truth chunk,
    #: not necessarily the labelled chunk itself. Always >= `hit_rate_at_5`
    #: for the same run — a chunk-exact hit is also a book-level hit.
    hit_rate_book_at_5: float
    per_book: dict[str, BookMetrics]
    n: int
    k: int
    degraded: int
    arms_used: dict[str, int]
    mean_latency_ms: float
    rows_loaded: int
    skipped_missing_chunk: int
    question_budget: int | None


# ── ground truth in, drift out ──────────────────────────────────────────────


def load_questions(
    path: Path = GROUND_TRUTH_PATH, *, budget: int | None = DEFAULT_QUESTION_BUDGET
) -> list[GroundTruthRow]:
    """Ground-truth rows, spread round-robin across books, capped at `budget`.

    `budget=None` returns every row. When a cap IS given, taking the first
    `budget` lines would sample one or two books, because
    `evals/ground_truth.jsonl` is written grouped by chunk — so the picks go
    round-robin over `book_id` in file order, which covers the shelf and
    stays deterministic (no seed to drift).

    Not imported from `evals/llm_eval.py`, whose `load_questions` is the same
    idea: that module imports `homelib_rag.answer` and `evals.judge` at
    import time, and this eval exists specifically to be runnable without an
    LLM stack loaded.
    """
    by_book: dict[str, list[GroundTruthRow]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            row = GroundTruthRow.model_validate_json(stripped)
            by_book.setdefault(row.book_id, []).append(row)

    books = sorted(by_book)
    picked: list[GroundTruthRow] = []
    depth = 0
    while (budget is None or len(picked) < budget) and any(
        depth < len(by_book[book]) for book in books
    ):
        for book in books:
            if budget is not None and len(picked) >= budget:
                break
            if depth < len(by_book[book]):
                picked.append(by_book[book][depth])
        depth += 1
    return picked


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def _connect() -> psycopg.Connection[tuple[Any, ...]]:
    """Open a read-only-by-use Postgres connection. Test seam: monkeypatch this.

    Imported lazily so the unit tests — which never reach a database — do not
    require `psycopg` to be importable at module import time.
    """
    import psycopg

    return psycopg.connect(_dsn(), connect_timeout=_CONNECT_TIMEOUT_SECONDS)


def load_indexed_chunk_ids() -> set[str]:
    """Every `chunk_id` currently in the index, for the corpus-drift check."""
    sqlite_path = os.environ.get("HOMELIB_SQLITE_PATH", "").strip()
    if sqlite_path:
        from apps.store.sqlite import connect, migrate

        conn = connect(Path(sqlite_path))
        migrate(conn)
        try:
            rows = conn.execute("SELECT chunk_id FROM chunks").fetchall()
            return {str(row[0]) for row in rows}
        finally:
            conn.close()

    with _connect() as pg_conn, pg_conn.cursor() as cur:
        cur.execute("SELECT chunk_id FROM chunks")
        return {str(row[0]) for row in cur.fetchall()}


def split_on_index(
    rows: Sequence[GroundTruthRow], indexed_chunk_ids: set[str]
) -> tuple[list[GroundTruthRow], list[GroundTruthRow]]:
    """Partition `rows` into (scoreable, drifted) against the live index.

    A row whose labelled `chunk_id` is no longer in the index cannot be hit
    by any arm, so scoring it would penalise all four equally for a corpus
    change — noise dressed up as difficulty. It is returned separately and
    reported, never dropped in silence.
    """
    scoreable = [row for row in rows if row.chunk_id in indexed_chunk_ids]
    drifted = [row for row in rows if row.chunk_id not in indexed_chunk_ids]
    return scoreable, drifted


# ── retrieval ───────────────────────────────────────────────────────────────


def _default_retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str]:
    """Production retrieval for `arm`, returning the arm that actually ran.

    `homelib_rag.hybrid` and `homelib_rag.rerank` are imported lazily because
    both pull in `sentence_transformers` (via `index`/`CrossEncoder`) at
    import time; keeping that out of module import means the unit tests,
    which never retrieve, do not pay for it.
    """
    from homelib_rag.hybrid import hybrid_search

    if arm == "lexical":
        return hybrid_search(query, k, mode="lexical")
    if arm == "vector":
        return hybrid_search(query, k, mode="vector")

    # Both remaining arms start from RRF. `mode_used` is what `hybrid_search`
    # really ran: "lexical" or "vector" when one backend was down.
    hits, mode_used = hybrid_search(query, k, mode="hybrid")
    if arm == "hybrid":
        return hits, mode_used

    from homelib_rag.rerank import rerank

    if not hits:
        # Nothing to rerank. The fusion still ran, so the mode is honest.
        return hits, mode_used
    reranked = rerank(query, hits)
    if reranked is None:
        # Cross-encoder unavailable: the caller keeps the pre-rerank ranking,
        # exactly as production does — and the row is labelled with what that
        # ranking actually is, not with the arm that was requested.
        return hits, mode_used
    return reranked, f"{mode_used}_rerank"


def _retrieve_one(
    row: GroundTruthRow,
    query: str,
    *,
    arm: str,
    k: int,
    query_id: str,
    retrieve: Retriever,
) -> QueryOutcome:
    """Run one query through one arm, recording what actually happened.

    A retrieval exception is recorded as an empty ranking with
    `arm_used="error"` rather than aborting the run: one dead query must not
    discard the other 234, and an arm whose backend is down should show up as
    a fully degraded row in the report, not as a crash with no evidence.
    """
    started = time.monotonic()
    try:
        hits, arm_used = retrieve(query, k, arm)
    except Exception as exc:
        logger.warning("retrieval failed for arm %r on %r: %s", arm, row.question, exc)
        hits, arm_used = [], _ARM_USED_ERROR

    return QueryOutcome(
        query_id=query_id,
        question=row.question,
        chunk_id=row.chunk_id,
        book_id=row.book_id,
        arm_requested=arm,
        arm_used=arm_used,
        ranked_chunk_ids=[hit.chunk_id for hit in hits],
        ranked_book_ids=[hit.book_id for hit in hits],
        latency_ms=int((time.monotonic() - started) * 1000),
    )


# ── scoring ─────────────────────────────────────────────────────────────────


def _score(outcomes: Sequence[QueryOutcome], k: int) -> tuple[float, float]:
    """hit-rate@k and MRR@k over `outcomes`, via `evals.metrics`.

    Both mappings are keyed by `query_id` (the row's index in the loaded
    ground truth) rather than by question text, so two rows that happen to
    share a question cannot collapse into one scored query. Propagates
    `evals.metrics`' `ValueError` on empty input — an arm scored over zero
    rows is a bug, not a 0.0.
    """
    results = {outcome.query_id: outcome.ranked_chunk_ids for outcome in outcomes}
    relevant = {outcome.query_id: [outcome.chunk_id] for outcome in outcomes}
    return hit_rate_at_k(results, relevant, k), mrr_at_k(results, relevant, k)


def _score_book(outcomes: Sequence[QueryOutcome], k: int) -> float:
    """Book-level hit-rate@k over `outcomes` — see `evals.metrics.hit_rate_book`.

    Keyed by `query_id`, same as `_score`, for the same reason: two rows
    that happen to share a question must not collapse into one query.
    """
    book_results = {outcome.query_id: outcome.ranked_book_ids for outcome in outcomes}
    relevant_books = {outcome.query_id: [outcome.book_id] for outcome in outcomes}
    return hit_rate_book(book_results, relevant_books, k)


def _per_book(outcomes: Sequence[QueryOutcome], k: int) -> dict[str, BookMetrics]:
    """Break the same outcomes down by book, using the same two metrics."""
    by_book: dict[str, list[QueryOutcome]] = {}
    for outcome in outcomes:
        by_book.setdefault(outcome.book_id, []).append(outcome)

    breakdown: dict[str, BookMetrics] = {}
    for book, book_outcomes in sorted(by_book.items()):
        hit_rate, mrr = _score(book_outcomes, k)
        breakdown[book] = BookMetrics(hit_rate_at_5=hit_rate, mrr_at_5=mrr, n=len(book_outcomes))
    return breakdown


def run_arm(
    rows: list[GroundTruthRow],
    *,
    arm: str,
    k: int = DEFAULT_K,
    rewrite: bool = False,
    retrieve: Retriever | None = None,
    rewriter: Rewriter | None = None,
    rows_loaded: int | None = None,
    skipped_missing_chunk: int = 0,
    question_budget: int | None = DEFAULT_QUESTION_BUDGET,
) -> ArmMetrics:
    """Score one arm over `rows`.

    `rewrite=True` routes every question through `homelib_rag.rewrite` first,
    which is ONE LLM CALL PER QUERY — the only way this eval touches a chat
    model, off by default, and stated in the report either way.

    `rows_loaded` / `skipped_missing_chunk` / `question_budget` are the
    coverage accounting `write_report` prints; they are carried on the row so
    a persisted `ArmMetrics` stays self-describing rather than depending on
    whoever happened to print it.
    """
    if arm not in ARMS:
        raise KeyError(f"unknown arm {arm!r}; known: {list(ARMS)}")

    retrieve_fn = retrieve if retrieve is not None else _default_retrieve
    rewrite_fn = rewriter if rewriter is not None else _default_rewriter

    outcomes: list[QueryOutcome] = []
    for index, row in enumerate(rows):
        # `rewrite_query` is fail-closed (returns the original query on any
        # failure), so no guard is needed here beyond not calling it at all
        # when the flag is off — which is what keeps the default run LLM-free.
        query = rewrite_fn(row.question) if rewrite else row.question
        outcomes.append(
            _retrieve_one(row, query, arm=arm, k=k, query_id=str(index), retrieve=retrieve_fn)
        )

    hit_rate, mrr = _score(outcomes, k)
    hit_rate_book_score = _score_book(outcomes, k)

    arms_used: dict[str, int] = {}
    for outcome in outcomes:
        arms_used[outcome.arm_used] = arms_used.get(outcome.arm_used, 0) + 1

    return ArmMetrics(
        arm=arm,
        rewrite=rewrite,
        hit_rate_at_5=hit_rate,
        mrr_at_5=mrr,
        hit_rate_book_at_5=hit_rate_book_score,
        per_book=_per_book(outcomes, k),
        n=len(outcomes),
        k=k,
        degraded=sum(1 for outcome in outcomes if outcome.degraded),
        arms_used=dict(sorted(arms_used.items())),
        mean_latency_ms=sum(o.latency_ms for o in outcomes) / len(outcomes),
        rows_loaded=rows_loaded if rows_loaded is not None else len(rows),
        skipped_missing_chunk=skipped_missing_chunk,
        question_budget=question_budget,
    )


def _default_rewriter(query: str) -> str:
    """Production query rewrite. Imported lazily — see `_default_retrieve`."""
    from homelib_rag.rewrite import rewrite_query

    return rewrite_query(query)


def run_all_arms(
    rows: list[GroundTruthRow],
    *,
    arms: Sequence[str] = ARMS,
    k: int = DEFAULT_K,
    rewrite: bool = False,
    retrieve: Retriever | None = None,
    rewriter: Rewriter | None = None,
    rows_loaded: int | None = None,
    skipped_missing_chunk: int = 0,
    question_budget: int | None = DEFAULT_QUESTION_BUDGET,
) -> list[ArmMetrics]:
    """Score every arm in `arms` over the same `rows`, in `ARMS` order."""
    return [
        run_arm(
            rows,
            arm=arm,
            k=k,
            rewrite=rewrite,
            retrieve=retrieve,
            rewriter=rewriter,
            rows_loaded=rows_loaded,
            skipped_missing_chunk=skipped_missing_chunk,
            question_budget=question_budget,
        )
        for arm in arms
    ]


# ── report ──────────────────────────────────────────────────────────────────


def _winner(results: Sequence[ArmMetrics]) -> ArmMetrics | None:
    """The winning arm, or `None` when the comparison is not sound.

    Refuses in three cases, each of which would otherwise be published as a
    finished result: fewer than four arms; any arm that scored zero rows; or
    any arm that degraded on EVERY query — a row labelled `hybrid` but
    measured entirely on lexical results is a different arm wearing the
    wrong name, and crowning one of its neighbours hides that.
    """
    if len(results) < _MIN_ARMS_FOR_A_WINNER:
        return None
    if any(result.n == 0 for result in results):
        return None
    if any(result.degraded == result.n for result in results):
        return None
    # hit-rate first because it is the metric the production default is
    # argued on; MRR breaks ties, rewarding the arm that puts the hit higher.
    return max(results, key=lambda result: (result.hit_rate_at_5, result.mrr_at_5))


def _coverage_lines(results: Sequence[ArmMetrics]) -> list[str]:
    """The header stating exactly what was and was not covered.

    Every arm is scored over the same rows, so the first row's accounting
    describes the whole run.
    """
    head = results[0]
    budget = "all rows" if head.question_budget is None else str(head.question_budget)
    return [
        f"Ground truth: `evals/ground_truth.jsonl` — {head.rows_loaded} row(s) loaded, "
        f"{head.n} scored, {head.skipped_missing_chunk} skipped because the labelled "
        "`chunk_id` is not in the current index (corpus drift; excluded rather than "
        "counted as a miss).",
        f"Coverage: k={head.k}, question budget = {budget} (`--questions`), "
        f"query rewrite = {'on' if head.rewrite else 'off'} (`--rewrite`).",
        f"Arms compared: {', '.join(f'`{result.arm}`' for result in results)}.",
    ]


def write_report(results: list[ArmMetrics], path: Path) -> None:
    """Write the markdown arm comparison, marking a winner only if there is one.

    Raises `ValueError` on empty `results`: a report with no arms in it is a
    broken run, and writing an empty table would present it as a finding.
    """
    if not results:
        raise ValueError("refusing to write a report with no arms — an empty run is a bug")

    lines = [
        "# Retrieval arm eval",
        "",
        f"Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        *_coverage_lines(results),
        "",
        "| arm | rewrite | n | hit-rate@5 | hit@k (book) | MRR@5 | degraded | mean latency (ms) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    winner = _winner(results)
    for result in results:
        mark = " **(winner)**" if winner is not None and result.arm == winner.arm else ""
        lines.append(
            f"| `{result.arm}`{mark} | {'on' if result.rewrite else 'off'} | {result.n} | "
            f"{result.hit_rate_at_5:.3f} | {result.hit_rate_book_at_5:.3f} | "
            f"{result.mrr_at_5:.3f} | {result.degraded} | "
            f"{result.mean_latency_ms:.0f} |"
        )
    lines.append("")

    if winner is not None:
        lines.append(
            f"**Winner: `{winner.arm}`** — highest hit-rate@5 "
            f"({winner.hit_rate_at_5:.3f}), MRR@5 ({winner.mrr_at_5:.3f}) breaking ties."
        )
        if winner.degraded:
            lines.append("")
            lines.append(
                f"Caveat: `{winner.arm}` degraded on {winner.degraded} of {winner.n} "
                "queries — see the arm-actually-used table below before citing this row."
            )
    else:
        lines.extend(_no_winner_lines(results))

    lines.extend(_degradation_section(results))
    lines.extend(_per_book_section(results))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _no_winner_lines(results: Sequence[ArmMetrics]) -> list[str]:
    """Say which of `_winner`'s three refusals fired, rather than just declining."""
    lines = ["**No winner marked.**"]
    if len(results) < _MIN_ARMS_FOR_A_WINNER:
        lines += [
            "",
            f"Only {len(results)} arm(s) scored; this comparison needs at least "
            f"{_MIN_ARMS_FOR_A_WINNER} (lexical, vector, hybrid, hybrid_rerank).",
        ]
    empty = [result.arm for result in results if result.n == 0]
    if empty:
        lines += [
            "",
            "Arm(s) that scored zero rows: "
            + ", ".join(f"`{arm}`" for arm in empty)
            + ". A missing arm is a build failure, not a narrower comparison "
            "presented as complete.",
        ]
    fully_degraded = [result.arm for result in results if result.n and result.degraded == result.n]
    if fully_degraded:
        lines += [
            "",
            "Arm(s) that degraded on every query: "
            + ", ".join(f"`{arm}`" for arm in fully_degraded)
            + ". Those rows measure whatever the fallback path returned, not the "
            "arm they are named after, so no winner can be read off this table.",
        ]
    return lines


def _degradation_section(results: Sequence[ArmMetrics]) -> list[str]:
    """Per-arm counts of the arm that ACTUALLY produced each query's ranking."""
    lines = [
        "",
        "## Arm actually used",
        "",
        "`hybrid_search` returns the mode it really ran and falls back to a single "
        "arm when a backend is down; `rerank` returns `None` when the cross-encoder "
        "cannot load. These are the arms that actually produced the rankings scored "
        "above — `error` means retrieval raised and nothing was returned.",
        "",
        "| arm requested | arm actually used (queries) |",
        "| --- | --- |",
    ]
    for result in results:
        used = ", ".join(f"`{arm}`: {count}" for arm, count in result.arms_used.items())
        lines.append(f"| `{result.arm}` | {used or '—'} |")
    return lines


def _per_book_section(results: Sequence[ArmMetrics]) -> list[str]:
    """One table per arm, so a single dominant book cannot carry a headline."""
    lines = ["", "## Per-book breakdown", ""]
    for result in results:
        lines += [
            f"### `{result.arm}`",
            "",
            "| book | n | hit-rate@5 | MRR@5 |",
            "| --- | ---: | ---: | ---: |",
        ]
        for book, book_metrics in result.per_book.items():
            lines.append(
                f"| `{book}` | {book_metrics.n} | {book_metrics.hit_rate_at_5:.3f} | "
                f"{book_metrics.mrr_at_5:.3f} |"
            )
        lines.append("")
    return lines


# ── gate ────────────────────────────────────────────────────────────────────


def _gate_metrics(results: Sequence[ArmMetrics]) -> dict[str, float]:
    """The gate-facing metrics: the `hybrid_rerank` arm's two scores.

    Empty when that arm did not soundly run — zero scored rows, or every
    query degraded away from the cross-encoder. Publishing a number the arm
    did not actually earn would let the gate ratify a broken pipeline; an
    empty dict makes the gate report both floors missing, which is a
    regression by `evals.gate`'s own rule.
    """
    by_arm = {result.arm: result for result in results}
    rerank_arm = by_arm.get("hybrid_rerank")
    if rerank_arm is None or rerank_arm.n == 0 or rerank_arm.degraded == rerank_arm.n:
        return {}
    return {
        "hybrid_rerank.hit_rate_at_5": rerank_arm.hit_rate_at_5,
        "hybrid_rerank.mrr_at_5": rerank_arm.mrr_at_5,
    }


def _run_retrieval_gate(results: Sequence[ArmMetrics]) -> int:
    """Compare this run's retrieval metrics to the committed baseline; record history."""
    full = load_baseline(BASELINE_PATH)
    scoped_keys = [key for key in full.metrics if key.startswith(_RETRIEVAL_METRIC_PREFIX)]
    scoped = Baseline(
        metrics={key: full.metrics[key] for key in scoped_keys},
        specs={key: full.specs[key] for key in scoped_keys},
        notes={key: full.notes[key] for key in scoped_keys},
    )

    current = _gate_metrics(results)
    regressions = compare_to_baseline(current, scoped)
    append_history(
        current, HISTORY_PATH, regressions=[regression.key for regression in regressions]
    )
    for regression in regressions:
        print(
            f"REGRESSION {regression.key}: baseline {regression.baseline} -> "
            f"current {regression.current} (delta {regression.delta}, "
            f"margin {regression.margin})"
        )
    return 1 if regressions else 0


# ── entry point ─────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare the lexical/vector/hybrid/hybrid_rerank retrieval arms."
    )
    parser.add_argument(
        "--questions",
        type=int,
        default=DEFAULT_QUESTION_BUDGET,
        help="cap on ground-truth rows scored per arm (default: every row)",
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_K, help="retrieval depth (default: %(default)s)"
    )
    parser.add_argument(
        "--arm",
        action="append",
        choices=list(ARMS),
        help="restrict to one arm; repeatable (default: all four)",
    )
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="rewrite each question with an LLM first — one model call per query, "
        "so the run is no longer LLM-free (default: off)",
    )
    parser.add_argument(
        "--report", type=Path, default=REPORT_PATH, help="report path (default: %(default)s)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(argv)
    started = time.monotonic()

    arms = args.arm if args.arm else list(ARMS)
    rows = load_questions(budget=args.questions)
    if not rows:
        print(f"✗ no ground-truth rows loaded from {GROUND_TRUTH_PATH}; no report written")
        return 1

    try:
        indexed = load_indexed_chunk_ids()
    except Exception as exc:
        # No drift check means no way to tell a real miss from a chunk that
        # was never in the index. Refusing to write beats publishing a table
        # of unearned zeroes.
        print(f"✗ could not read the index for the corpus-drift check: {exc}")
        print(f"  no live run, no report written to {args.report}")
        return 1

    scoreable, drifted = split_on_index(rows, indexed)
    print(
        f"{len(rows)} ground-truth row(s); {len(scoreable)} scoreable, "
        f"{len(drifted)} skipped as corpus drift; {len(arms)} arm(s), k={args.k}"
    )
    if not scoreable:
        print(
            f"✗ the index holds none of the {len(rows)} labelled chunk ids "
            f"({len(indexed)} chunk(s) indexed). Every arm would score 0.000 for a "
            "reason that has nothing to do with retrieval quality, so no report was "
            f"written to {args.report}. Ingest the corpus and re-run."
        )
        return 1

    results = run_all_arms(
        scoreable,
        arms=arms,
        k=args.k,
        rewrite=args.rewrite,
        rows_loaded=len(rows),
        skipped_missing_chunk=len(drifted),
        question_budget=args.questions,
    )
    write_report(results, args.report)
    print(f"wrote {args.report} in {time.monotonic() - started:.1f}s")
    print(json.dumps([result.model_dump(exclude={"per_book"}) for result in results], indent=2))

    if _winner(results) is None:
        print("✗ no winner: fewer than four arms, an arm scored nothing, or an arm fully degraded")
        return 1
    return _run_retrieval_gate(results)


if __name__ == "__main__":
    raise SystemExit(main())
