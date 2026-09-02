"""Tests for evals/retrieval_eval.py — the retrieval-arm bake-off.

Every test here runs with NO database, NO embedding model and NO LLM: the
`retrieve`/`rewriter` seams on `run_arm` are replaced with fakes, and the
corpus-drift check is exercised against a hand-built id set. That is the
point — the live run needs Postgres, but a suite that needed it too could
not run in CI, and the honesty invariants (arm actually used, drift
exclusion, refusal to crown a degraded winner) are exactly the parts worth
pinning.
"""

import json
from pathlib import Path

import pytest
from homelib_rag.models import Hit

from evals import metrics
from evals.ground_truth import GROUND_TRUTH_PATH, GroundTruthRow
from evals.retrieval_eval import (
    ARMS,
    DEFAULT_DATABASE_URL,
    DEFAULT_K,
    DEFAULT_QUESTION_BUDGET,
    ArmMetrics,
    BookMetrics,
    QueryOutcome,
    hit_rate_at_k,
    load_indexed_chunk_ids,
    load_questions,
    mrr_at_k,
    run_all_arms,
    run_arm,
    split_on_index,
    write_report,
)


def _hit(chunk_id: str, rank: int, book_id: str = "book-a") -> Hit:
    return Hit(
        chunk_id=chunk_id,
        book_id=book_id,
        score=1.0 / rank,
        rank=rank,
        text=f"text for {chunk_id}",
        section_path=["ch1"],
        page=rank,
    )


def _row(question: str, chunk_id: str, book_id: str = "book-a") -> GroundTruthRow:
    return GroundTruthRow(question=question, chunk_id=chunk_id, book_id=book_id)


def _fixed_retriever(rankings: dict[str, list[str]], *, arm_used: str | None = None) -> object:
    """A fake `Retriever` returning a canned ranking per question."""

    def retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str]:
        ids = rankings.get(query, [])[:k]
        return [_hit(cid, rank) for rank, cid in enumerate(ids, start=1)], arm_used or arm

    return retrieve


# ── the metric functions are reused, not reimplemented ──────────────────────


def test_metrics_are_reexported_from_evals_metrics_not_reimplemented() -> None:
    # A second copy of hit-rate/MRR living in retrieval_eval.py is exactly the
    # drift specs/evals-retrieval.md's "reimplemented from the definitions"
    # rule is meant to prevent — one hand-tested implementation, re-exported.
    assert hit_rate_at_k is metrics.hit_rate_at_k
    assert mrr_at_k is metrics.mrr_at_k


def test_default_database_url_matches_the_index_module() -> None:
    # retrieval_eval copies the DSN default rather than importing
    # homelib_rag.index (which loads sentence_transformers at import time).
    # This is the pin that stops the copy drifting from the original.
    from homelib_rag import index

    assert DEFAULT_DATABASE_URL == index._DEFAULT_DATABASE_URL


# ── scoring: hand-computed, no database ─────────────────────────────────────


def test_run_arm_hit_rate_and_mrr_hand_computed() -> None:
    # Three queries: relevant id at rank 1, at rank 4, and absent.
    # hit-rate@5 = 2/3; MRR@5 = (1/1 + 1/4 + 0) / 3.
    rows = [_row("q1", "c1"), _row("q2", "c2"), _row("q3", "c3")]
    rankings = {
        "q1": ["c1", "x", "y", "z", "w"],
        "q2": ["x", "y", "z", "c2", "w"],
        "q3": ["x", "y", "z", "w", "v"],
    }

    result = run_arm(rows, arm="lexical", retrieve=_fixed_retriever(rankings))  # type: ignore[arg-type]

    assert result.n == 3
    assert result.hit_rate_at_5 == pytest.approx(2 / 3)
    assert result.mrr_at_5 == pytest.approx((1.0 + 0.25 + 0.0) / 3)


def test_run_arm_scores_one_when_relevant_is_always_rank_one() -> None:
    rows = [_row("q1", "c1"), _row("q2", "c2")]
    rankings = {"q1": ["c1", "x"], "q2": ["c2", "y"]}

    result = run_arm(rows, arm="vector", retrieve=_fixed_retriever(rankings))  # type: ignore[arg-type]

    assert result.hit_rate_at_5 == pytest.approx(1.0)
    assert result.mrr_at_5 == pytest.approx(1.0)


def test_run_arm_respects_k_and_ignores_hits_beyond_it() -> None:
    # The relevant id sits at rank 6; at k=5 it must not count as a hit.
    rows = [_row("q1", "c1")]
    rankings = {"q1": ["a", "b", "c", "d", "e", "c1"]}
    retriever = _fixed_retriever(rankings)

    at_five = run_arm(rows, arm="lexical", k=5, retrieve=retriever)  # type: ignore[arg-type]
    at_ten = run_arm(rows, arm="lexical", k=10, retrieve=retriever)  # type: ignore[arg-type]

    assert at_five.hit_rate_at_5 == pytest.approx(0.0)
    assert at_five.k == 5
    assert at_ten.hit_rate_at_5 == pytest.approx(1.0)
    assert at_ten.mrr_at_5 == pytest.approx(1 / 6)
    assert at_ten.k == 10


def test_run_arm_rejects_an_unknown_arm() -> None:
    with pytest.raises(KeyError, match="unknown arm"):
        run_arm([_row("q1", "c1")], arm="bm25", retrieve=_fixed_retriever({}))  # type: ignore[arg-type]


def test_run_arm_raises_on_zero_rows_rather_than_scoring_zero() -> None:
    # specs/evals-retrieval.md: an eval run over zero data is a bug, not a 0.0.
    with pytest.raises(ValueError, match="empty"):
        run_arm([], arm="lexical", retrieve=_fixed_retriever({}))  # type: ignore[arg-type]


def test_per_book_breakdown_sums_to_overall_n() -> None:
    rows = [
        _row("q1", "c1", "book-a"),
        _row("q2", "c2", "book-a"),
        _row("q3", "c3", "book-b"),
        _row("q4", "c4", "book-c"),
    ]
    rankings = {"q1": ["c1"], "q2": ["x"], "q3": ["c3"], "q4": ["x", "c4"]}

    result = run_arm(rows, arm="hybrid", retrieve=_fixed_retriever(rankings))  # type: ignore[arg-type]

    assert sum(book.n for book in result.per_book.values()) == result.n
    assert set(result.per_book) == {"book-a", "book-b", "book-c"}
    assert result.per_book["book-a"].hit_rate_at_5 == pytest.approx(0.5)
    assert result.per_book["book-c"].mrr_at_5 == pytest.approx(0.5)


def test_two_rows_sharing_a_question_are_scored_separately() -> None:
    # Keying the metric mappings by question text would collapse these into
    # one query and quietly halve the denominator.
    rows = [_row("same question?", "c1"), _row("same question?", "c2")]
    rankings = {"same question?": ["c1", "x"]}

    result = run_arm(rows, arm="lexical", retrieve=_fixed_retriever(rankings))  # type: ignore[arg-type]

    assert result.n == 2
    assert result.hit_rate_at_5 == pytest.approx(0.5)


# ── invariant: the arm reported is the arm that actually ran ────────────────


def test_degraded_hybrid_is_reported_as_the_arm_that_actually_ran() -> None:
    # hybrid_search degrades to lexical when the vector backend is down. A
    # "hybrid" row measured on lexical results is not a hybrid measurement.
    rows = [_row("q1", "c1"), _row("q2", "c2")]
    rankings = {"q1": ["c1"], "q2": ["c2"]}

    result = run_arm(
        rows,
        arm="hybrid",
        retrieve=_fixed_retriever(rankings, arm_used="lexical"),  # type: ignore[arg-type]
    )

    assert result.arm == "hybrid"
    assert result.degraded == 2
    assert result.arms_used == {"lexical": 2}


def test_partial_degradation_is_counted_not_rounded_away() -> None:
    def retrieve(query: str, k: int, arm: str) -> tuple[list[Hit], str]:
        # Only the second question loses the cross-encoder.
        used = "hybrid" if query == "q1" else "hybrid_rerank"
        return [_hit("c1", 1)], used

    rows = [_row("q1", "c1"), _row("q2", "c1")]
    result = run_arm(rows, arm="hybrid_rerank", retrieve=retrieve)

    assert result.degraded == 1
    assert result.arms_used == {"hybrid": 1, "hybrid_rerank": 1}


def test_retrieval_exception_is_recorded_as_an_error_row_not_a_crash() -> None:
    def exploding(query: str, k: int, arm: str) -> tuple[list[Hit], str]:
        if query == "q2":
            raise RuntimeError("backend down")
        return [_hit("c1", 1)], arm

    rows = [_row("q1", "c1"), _row("q2", "c2")]
    result = run_arm(rows, arm="lexical", retrieve=exploding)

    assert result.n == 2
    assert result.arms_used == {"error": 1, "lexical": 1}
    assert result.degraded == 1
    assert result.hit_rate_at_5 == pytest.approx(0.5)


def test_query_outcome_degraded_is_derived_from_the_arm_actually_used() -> None:
    same = QueryOutcome(
        query_id="0",
        question="q",
        chunk_id="c",
        book_id="b",
        arm_requested="hybrid",
        arm_used="hybrid",
        ranked_chunk_ids=[],
        latency_ms=1,
    )
    other = same.model_copy(update={"arm_used": "lexical"})

    assert same.degraded is False
    assert other.degraded is True


# ── invariant: corpus drift is excluded, never scored as a miss ─────────────


def test_drifted_rows_are_split_out_not_scored_as_misses() -> None:
    rows = [_row("q1", "c1"), _row("q2", "gone"), _row("q3", "c3")]

    scoreable, drifted = split_on_index(rows, {"c1", "c3"})

    assert [row.chunk_id for row in scoreable] == ["c1", "c3"]
    assert [row.chunk_id for row in drifted] == ["gone"]

    rankings = {"q1": ["c1"], "q3": ["c3"]}
    result = run_arm(
        scoreable,
        arm="lexical",
        retrieve=_fixed_retriever(rankings),  # type: ignore[arg-type]
        rows_loaded=len(rows),
        skipped_missing_chunk=len(drifted),
    )

    # Scored 2 of 3 at 1.0 — NOT 3 rows at 2/3, which is what leaving the
    # drifted row in the denominator would have produced.
    assert result.n == 2
    assert result.hit_rate_at_5 == pytest.approx(1.0)
    assert result.rows_loaded == 3
    assert result.skipped_missing_chunk == 1


def test_ground_truth_row_chunk_id_exists_in_fixture_index() -> None:
    # The drift check's positive case: every committed ground-truth row is
    # scoreable against an index that contains its chunk id.
    rows = load_questions(GROUND_TRUTH_PATH)
    fixture_index = {row.chunk_id for row in rows}

    scoreable, drifted = split_on_index(rows, fixture_index)

    assert drifted == []
    assert len(scoreable) == len(rows)
    assert all(row.chunk_id for row in rows)


# ── invariant: no LLM in the default measurement path ───────────────────────


def test_default_run_never_calls_the_rewriter() -> None:
    calls: list[str] = []

    def spy(query: str) -> str:
        calls.append(query)
        return query

    run_arm(
        [_row("q1", "c1")],
        arm="lexical",
        retrieve=_fixed_retriever({"q1": ["c1"]}),  # type: ignore[arg-type]
        rewriter=spy,
    )

    assert calls == []


def test_rewrite_flag_routes_the_question_through_the_rewriter() -> None:
    calls: list[str] = []

    def spy(query: str) -> str:
        calls.append(query)
        return "rewritten"

    result = run_arm(
        [_row("q1", "c1")],
        arm="lexical",
        rewrite=True,
        retrieve=_fixed_retriever({"rewritten": ["c1"]}),  # type: ignore[arg-type]
        rewriter=spy,
    )

    assert calls == ["q1"]
    assert result.rewrite is True
    assert result.hit_rate_at_5 == pytest.approx(1.0)


# ── all four arms ───────────────────────────────────────────────────────────


def test_run_all_arms_covers_the_four_named_arms() -> None:
    assert ARMS == ("lexical", "vector", "hybrid", "hybrid_rerank")

    rows = [_row("q1", "c1")]
    results = run_all_arms(rows, retrieve=_fixed_retriever({"q1": ["c1"]}))  # type: ignore[arg-type]

    assert [result.arm for result in results] == list(ARMS)
    assert all(result.n == 1 for result in results)


# ── report ──────────────────────────────────────────────────────────────────


def _arm_metrics(
    arm: str,
    hit_rate: float,
    mrr: float,
    *,
    n: int = 10,
    degraded: int = 0,
    arms_used: dict[str, int] | None = None,
) -> ArmMetrics:
    return ArmMetrics(
        arm=arm,
        rewrite=False,
        hit_rate_at_5=hit_rate,
        mrr_at_5=mrr,
        per_book={"book-a": BookMetrics(hit_rate_at_5=hit_rate, mrr_at_5=mrr, n=n)},
        n=n,
        k=DEFAULT_K,
        degraded=degraded,
        arms_used=arms_used or {arm: n},
        mean_latency_ms=12.0,
        rows_loaded=n + 2,
        skipped_missing_chunk=2,
        question_budget=None,
    )


def _four_arms() -> list[ArmMetrics]:
    return [
        _arm_metrics("lexical", 0.50, 0.30),
        _arm_metrics("vector", 0.60, 0.40),
        _arm_metrics("hybrid", 0.70, 0.50),
        _arm_metrics("hybrid_rerank", 0.80, 0.65),
    ]


def test_report_marks_the_best_arm_as_winner(tmp_path: Path) -> None:
    path = tmp_path / "retrieval.md"
    write_report(_four_arms(), path)
    text = path.read_text(encoding="utf-8")

    assert "**Winner: `hybrid_rerank`**" in text
    assert "| `hybrid_rerank` **(winner)** |" in text
    for arm in ARMS:
        assert f"`{arm}`" in text
    assert "hit-rate@5" in text
    assert "MRR@5" in text


def test_report_states_every_coverage_bound(tmp_path: Path) -> None:
    # specs: nothing that bounds coverage may be silently applied.
    path = tmp_path / "retrieval.md"
    write_report(_four_arms(), path)
    text = path.read_text(encoding="utf-8")

    assert "12 row(s) loaded, 10 scored, 2 skipped" in text
    assert "k=5" in text
    assert "question budget = all rows" in text
    assert "query rewrite = off" in text


def test_report_states_a_numeric_question_budget_when_capped(tmp_path: Path) -> None:
    results = _four_arms()
    for result in results:
        result.question_budget = 40
    path = tmp_path / "retrieval.md"
    write_report(results, path)

    assert "question budget = 40" in path.read_text(encoding="utf-8")


def test_report_refuses_a_winner_when_an_arm_fully_degraded(tmp_path: Path) -> None:
    results = _four_arms()
    results[2] = _arm_metrics("hybrid", 0.70, 0.50, degraded=10, arms_used={"lexical": 10})
    path = tmp_path / "retrieval.md"
    write_report(results, path)
    text = path.read_text(encoding="utf-8")

    assert "**No winner marked.**" in text
    assert "degraded on every query" in text
    assert "**Winner:" not in text


def test_report_refuses_a_winner_when_an_arm_scored_nothing(tmp_path: Path) -> None:
    results = _four_arms()
    results[1] = _arm_metrics("vector", 0.0, 0.0, n=0, arms_used={})
    path = tmp_path / "retrieval.md"
    write_report(results, path)
    text = path.read_text(encoding="utf-8")

    assert "**No winner marked.**" in text
    assert "scored zero rows" in text


def test_report_refuses_a_winner_with_fewer_than_four_arms(tmp_path: Path) -> None:
    path = tmp_path / "retrieval.md"
    write_report(_four_arms()[:3], path)
    text = path.read_text(encoding="utf-8")

    assert "**No winner marked.**" in text
    assert "needs at least 4" in text


def test_report_caveats_a_winner_that_partially_degraded(tmp_path: Path) -> None:
    results = _four_arms()
    results[3] = _arm_metrics(
        "hybrid_rerank", 0.80, 0.65, degraded=3, arms_used={"hybrid": 3, "hybrid_rerank": 7}
    )
    path = tmp_path / "retrieval.md"
    write_report(results, path)
    text = path.read_text(encoding="utf-8")

    assert "**Winner: `hybrid_rerank`**" in text
    assert "degraded on 3 of 10 queries" in text


def test_report_lists_the_arm_actually_used_per_arm(tmp_path: Path) -> None:
    results = _four_arms()
    results[2] = _arm_metrics(
        "hybrid", 0.70, 0.50, degraded=4, arms_used={"hybrid": 6, "lexical": 4}
    )
    path = tmp_path / "retrieval.md"
    write_report(results, path)
    text = path.read_text(encoding="utf-8")

    assert "## Arm actually used" in text
    assert "`hybrid`: 6, `lexical`: 4" in text


def test_report_includes_a_per_book_breakdown(tmp_path: Path) -> None:
    path = tmp_path / "retrieval.md"
    write_report(_four_arms(), path)
    text = path.read_text(encoding="utf-8")

    assert "## Per-book breakdown" in text
    assert "| `book-a` | 10 |" in text


def test_write_report_refuses_an_empty_result_set(tmp_path: Path) -> None:
    path = tmp_path / "retrieval.md"
    with pytest.raises(ValueError, match="no arms"):
        write_report([], path)
    assert not path.exists()


# ── ground-truth loading and the question budget ────────────────────────────


def test_load_questions_default_budget_takes_every_row(tmp_path: Path) -> None:
    assert DEFAULT_QUESTION_BUDGET is None

    path = tmp_path / "gt.jsonl"
    rows = [_row(f"q{i}", f"c{i}", f"book-{i % 3}") for i in range(9)]
    path.write_text(
        "\n".join(json.dumps(row.model_dump()) for row in rows) + "\n", encoding="utf-8"
    )

    assert len(load_questions(path)) == 9


def test_load_questions_budget_spreads_across_books_instead_of_truncating(
    tmp_path: Path,
) -> None:
    # File order is grouped by book; a naive head -n 3 would take book-a only.
    path = tmp_path / "gt.jsonl"
    rows = [
        *[_row(f"a{i}", f"ca{i}", "book-a") for i in range(5)],
        *[_row(f"b{i}", f"cb{i}", "book-b") for i in range(5)],
        *[_row(f"c{i}", f"cc{i}", "book-c") for i in range(5)],
    ]
    path.write_text(
        "\n".join(json.dumps(row.model_dump()) for row in rows) + "\n", encoding="utf-8"
    )

    picked = load_questions(path, budget=3)

    assert len(picked) == 3
    assert {row.book_id for row in picked} == {"book-a", "book-b", "book-c"}


def test_load_questions_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "gt.jsonl"
    row = _row("q1", "c1")
    path.write_text(f"\n{json.dumps(row.model_dump())}\n\n", encoding="utf-8")

    assert len(load_questions(path)) == 1


def test_committed_ground_truth_loads_and_covers_many_books() -> None:
    rows = load_questions(GROUND_TRUTH_PATH)

    assert len(rows) >= 150  # specs/evals-retrieval.md targets 150-250 pairs
    assert len({row.book_id for row in rows}) >= 10


# ── pydantic contract ───────────────────────────────────────────────────────


def test_models_allow_extra_fields() -> None:
    # Every model in this harness is extra="allow" so an older report/history
    # record gains fields without failing validation on the way back in.
    extended = ArmMetrics.model_validate(
        {**_arm_metrics("lexical", 0.5, 0.3).model_dump(), "future_field": 1}
    )
    assert extended.future_field == 1  # type: ignore[attr-defined]

    outcome = QueryOutcome.model_validate(
        {
            "query_id": "0",
            "question": "q",
            "chunk_id": "c",
            "book_id": "b",
            "arm_requested": "lexical",
            "arm_used": "lexical",
            "ranked_chunk_ids": [],
            "latency_ms": 0,
            "future_field": "x",
        }
    )
    assert outcome.future_field == "x"  # type: ignore[attr-defined]

    book = BookMetrics.model_validate(
        {"hit_rate_at_5": 1.0, "mrr_at_5": 1.0, "n": 1, "future_field": True}
    )
    assert book.future_field is True  # type: ignore[attr-defined]


def test_load_indexed_chunk_ids_reads_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.store.sqlite import connect, migrate

    db_path = tmp_path / "eval.sqlite"
    monkeypatch.setenv("HOMELIB_SQLITE_PATH", str(db_path))
    conn = connect(db_path)
    migrate(conn)
    conn.execute(
        "INSERT INTO books (book_id, title, authors, rights_status) VALUES (?, ?, ?, ?)",
        ("book-e", "Eval", "[]", "public_domain"),
    )
    conn.execute(
        """
        INSERT INTO chunks (
            chunk_id, book_id, block_ids, section_path, text, char_start, char_end
        ) VALUES ('ce-1', 'book-e', '[]', '[]', 'text', 0, 4)
        """
    )
    conn.commit()
    conn.close()

    assert load_indexed_chunk_ids() == {"ce-1"}
