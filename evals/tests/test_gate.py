"""Tests for evals/gate.py — the eval regression gate (specs/eval-gate.md)."""

import json
import math
from pathlib import Path

import pytest

from evals.gate import (
    Baseline,
    MetricSpec,
    Regression,
    append_history,
    compare_to_baseline,
    load_baseline,
    run_gate,
)

REAL_BASELINE_PATH = Path(__file__).resolve().parent.parent / "eval-baseline.json"


def _make_baseline(
    key: str,
    value: float,
    *,
    direction: str = "higher_is_better",
    margin: float = 0.03,
) -> Baseline:
    return Baseline(
        metrics={key: value},
        specs={key: MetricSpec(key=key, direction=direction, margin=margin)},  # type: ignore[arg-type]
        notes={key: f"test note for {key}"},
    )


def test_gate_flags_regression_beyond_margin() -> None:
    # baseline 0.78, current 0.70, margin 0.03, higher_is_better ->
    # exactly one Regression, delta == 0.70 - 0.78 == -0.08.
    baseline = _make_baseline("hit_rate_at_5", 0.78, margin=0.03)
    current = {"hit_rate_at_5": 0.70}

    regressions = compare_to_baseline(current, baseline)

    assert len(regressions) == 1
    regression = regressions[0]
    assert isinstance(regression, Regression)
    assert regression.key == "hit_rate_at_5"
    assert regression.baseline == pytest.approx(0.78)
    assert regression.current == pytest.approx(0.70)
    assert regression.delta == pytest.approx(-0.08)


def test_gate_allows_movement_within_margin() -> None:
    # baseline 0.78, current 0.76, margin 0.03 -> within margin, no regression.
    baseline = _make_baseline("hit_rate_at_5", 0.78, margin=0.03)
    current = {"hit_rate_at_5": 0.76}

    assert compare_to_baseline(current, baseline) == []


def test_gate_allows_any_improvement_in_the_right_direction() -> None:
    baseline = _make_baseline("hit_rate_at_5", 0.78, margin=0.03)
    current = {"hit_rate_at_5": 0.99}  # big improvement, never a regression

    assert compare_to_baseline(current, baseline) == []


def test_lower_is_better_direction_flips_comparison() -> None:
    # A lower_is_better metric that INCREASES beyond margin is flagged; the
    # same-magnitude increase on a higher_is_better metric is not, since an
    # increase is the *good* direction there.
    lower_is_better_baseline = _make_baseline(
        "latency_p50_ms", 100.0, direction="lower_is_better", margin=5.0
    )
    higher_is_better_baseline = _make_baseline(
        "hit_rate_at_5", 100.0, direction="higher_is_better", margin=5.0
    )
    current = {"latency_p50_ms": 110.0, "hit_rate_at_5": 110.0}

    lower_regressions = compare_to_baseline(current, lower_is_better_baseline)
    higher_regressions = compare_to_baseline(current, higher_is_better_baseline)

    assert len(lower_regressions) == 1
    assert lower_regressions[0].delta == pytest.approx(10.0)
    assert higher_regressions == []


def test_gate_treats_missing_metric_as_regression() -> None:
    baseline = _make_baseline("hit_rate_at_5", 0.78, margin=0.03)
    current: dict[str, float] = {}  # metric silently stopped being computed

    regressions = compare_to_baseline(current, baseline)

    assert len(regressions) == 1
    regression = regressions[0]
    assert regression.key == "hit_rate_at_5"
    assert regression.baseline == pytest.approx(0.78)
    assert math.isnan(regression.current)
    assert math.isnan(regression.delta)


def test_compare_to_baseline_does_not_mutate_inputs() -> None:
    baseline = _make_baseline("hit_rate_at_5", 0.78, margin=0.03)
    current = {"hit_rate_at_5": 0.70}
    current_copy = dict(current)
    baseline_copy = baseline.model_copy(deep=True)

    compare_to_baseline(current, baseline)

    assert current == current_copy
    assert baseline == baseline_copy


def test_history_is_append_only(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"

    append_history({"hit_rate_at_5": 0.70}, history_path)
    append_history({"hit_rate_at_5": 0.71}, history_path)
    append_history({"hit_rate_at_5": 0.72}, history_path)

    lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3

    records = [json.loads(line) for line in lines]
    assert [record["metrics"]["hit_rate_at_5"] for record in records] == [0.70, 0.71, 0.72]
    for record in records:
        assert "ts" in record
        assert "git_sha" in record
        assert record["regressions"] == []


def test_history_records_regressions_when_given(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"

    append_history({"hit_rate_at_5": 0.70}, history_path, regressions=["hit_rate_at_5"])

    record = json.loads(history_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["regressions"] == ["hit_rate_at_5"]


def test_every_baseline_metric_has_a_note() -> None:
    data = json.loads(REAL_BASELINE_PATH.read_text(encoding="utf-8"))
    baseline = Baseline.model_validate(data)

    assert baseline.metrics, "evals/eval-baseline.json must not be empty"
    for key in baseline.metrics:
        assert baseline.notes.get(key, "").strip(), f"metric {key!r} has no non-empty note"
        assert key in baseline.specs, f"metric {key!r} has no MetricSpec"


def test_baseline_rejects_metric_without_note() -> None:
    with pytest.raises(ValueError, match="no non-empty note"):
        Baseline(
            metrics={"m": 1.0},
            specs={"m": MetricSpec(key="m", direction="higher_is_better", margin=0.1)},  # type: ignore[arg-type]
            notes={},
        )


def test_baseline_rejects_metric_without_spec() -> None:
    with pytest.raises(ValueError, match="no MetricSpec"):
        Baseline(metrics={"m": 1.0}, specs={}, notes={"m": "why this floor"})


def test_load_baseline_loads_the_real_committed_file() -> None:
    baseline = load_baseline(REAL_BASELINE_PATH)
    assert isinstance(baseline, Baseline)
    assert baseline.metrics


def _write_baseline(path: Path, baseline: Baseline) -> None:
    path.write_text(baseline.model_dump_json(), encoding="utf-8")


def test_run_gate_exits_zero_and_records_history_on_a_healthy_run(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    history_path = tmp_path / "history.jsonl"
    _write_baseline(baseline_path, _make_baseline("hit_rate_at_5", 0.78, margin=0.03))

    exit_code = run_gate({"hit_rate_at_5": 0.79}, baseline_path, history_path)

    assert exit_code == 0
    records = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["regressions"] == []
    assert records[0]["metrics"] == {"hit_rate_at_5": 0.79}


def test_run_gate_exits_nonzero_and_still_records_history_on_regression(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Red drill (specs/eval-gate.md): a run that regresses beyond margin must
    # fail the gate AND still append to history, with the regression printed.
    baseline_path = tmp_path / "baseline.json"
    history_path = tmp_path / "history.jsonl"
    _write_baseline(baseline_path, _make_baseline("hit_rate_at_5", 0.78, margin=0.03))

    exit_code = run_gate({"hit_rate_at_5": 0.50}, baseline_path, history_path)

    assert exit_code == 1
    records = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["regressions"] == ["hit_rate_at_5"]

    printed = capsys.readouterr().out
    assert "REGRESSION hit_rate_at_5" in printed


def test_run_gate_missing_metric_is_reported_as_missing_not_worse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline_path = tmp_path / "baseline.json"
    history_path = tmp_path / "history.jsonl"
    _write_baseline(baseline_path, _make_baseline("hit_rate_at_5", 0.78, margin=0.03))

    exit_code = run_gate({}, baseline_path, history_path)

    assert exit_code == 1
    printed = capsys.readouterr().out
    assert "MISSING" in printed
    assert "hit_rate_at_5" in printed


# ── committed report loaders (E01 / E02) ─────────────────────────────────────

# Provenance: column layout copied from evals/results/retrieval.md (2026-09-06).
# The old justfile regex treated `n` (235) as hit-rate and book-hit (0.906) as MRR.
_RETRIEVAL_WINNER_TABLE = """\
# Retrieval arm eval

| arm | rewrite | n | hit-rate@5 | hit@k (book) | MRR@5 | degraded | mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `lexical` | off | 235 | 0.064 | 0.077 | 0.055 | 0 | 67 |
| `hybrid_rerank` **(winner)** | off | 235 | 0.638 | 0.906 | 0.572 | 0 | 149 |
"""

_LLM_EVAL_TABLE = """\
# LLM prompt-variant eval

| variant | n | faithfulness | relevance | citation_quality | suggested_score | ungrounded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `cited_first` | 10 | 3.00 | 3.70 | 3.00 | 2.80 | 0/10 |
| `production` | 10 | 2.60 | 2.90 | 2.30 | 2.40 | 1/10 |
| `stepwise` | 10 | 3.40 | 3.80 | 2.70 | 3.00 | 0/10 |

**Winner: `stepwise`** — highest mean suggested_score (3.00).
"""


def test_committed_retrieval_report_uses_passage_hit_rate_not_question_count(
    tmp_path: Path,
) -> None:
    from evals.gate import load_committed_retrieval_metrics

    path = tmp_path / "retrieval.md"
    path.write_text(_RETRIEVAL_WINNER_TABLE, encoding="utf-8")

    metrics = load_committed_retrieval_metrics(path)

    assert metrics["hybrid_rerank.hit_rate_at_5"] == pytest.approx(0.638)
    assert metrics["hybrid_rerank.mrr_at_5"] == pytest.approx(0.572)
    assert metrics["hybrid_rerank.hit_rate_at_5"] != pytest.approx(235.0)
    assert metrics["hybrid_rerank.mrr_at_5"] != pytest.approx(0.906)


def test_retrieval_rate_outside_unit_interval_is_rejected(tmp_path: Path) -> None:
    from evals.gate import load_committed_retrieval_metrics

    # Same corpus-shaped table, but hit-rate column wrongly holds question count.
    bad = """\
| arm | rewrite | n | hit-rate@5 | hit@k (book) | MRR@5 | degraded | mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `hybrid_rerank` **(winner)** | off | 235 | 235 | 0.906 | 0.572 | 0 | 149 |
"""
    path = tmp_path / "retrieval.md"
    path.write_text(bad, encoding="utf-8")

    with pytest.raises(ValueError, match="outside"):
        load_committed_retrieval_metrics(path)


def test_eval_gate_fails_when_committed_hit_rate_regresses(tmp_path: Path) -> None:
    from evals.gate import load_committed_retrieval_metrics, run_gate

    report = tmp_path / "retrieval.md"
    report.write_text(
        """\
| arm | rewrite | n | hit-rate@5 | hit@k (book) | MRR@5 | degraded | mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `hybrid_rerank` **(winner)** | off | 235 | 0.500 | 0.906 | 0.400 | 0 | 149 |
""",
        encoding="utf-8",
    )
    baseline_path = tmp_path / "baseline.json"
    history_path = tmp_path / "history.jsonl"
    baseline = Baseline(
        metrics={
            "hybrid_rerank.hit_rate_at_5": 0.6383,
            "hybrid_rerank.mrr_at_5": 0.5718,
        },
        specs={
            "hybrid_rerank.hit_rate_at_5": MetricSpec(
                key="hybrid_rerank.hit_rate_at_5",
                direction="higher_is_better",
                margin=0.01,
            ),
            "hybrid_rerank.mrr_at_5": MetricSpec(
                key="hybrid_rerank.mrr_at_5",
                direction="higher_is_better",
                margin=0.01,
            ),
        },
        notes={
            "hybrid_rerank.hit_rate_at_5": "test floor",
            "hybrid_rerank.mrr_at_5": "test floor",
        },
    )
    _write_baseline(baseline_path, baseline)

    current = load_committed_retrieval_metrics(report)
    assert run_gate(current, baseline_path, history_path) == 1


def test_committed_judge_report_reads_production_faithfulness_not_winner(
    tmp_path: Path,
) -> None:
    from evals.gate import load_committed_judge_metrics

    path = tmp_path / "llm_eval.md"
    path.write_text(_LLM_EVAL_TABLE, encoding="utf-8")

    metrics = load_committed_judge_metrics(path)

    assert metrics["judge.mean_faithfulness"] == pytest.approx(2.60)
    assert metrics["judge.mean_faithfulness"] != pytest.approx(3.40)
    assert metrics["judge.mean_faithfulness"] != pytest.approx(1.9)
    assert set(metrics) == {"judge.mean_faithfulness"}


def test_committed_judge_below_floor_fails_gate(tmp_path: Path) -> None:
    from evals.gate import load_committed_judge_metrics, run_gate

    path = tmp_path / "llm_eval.md"
    path.write_text(
        """\
| variant | n | faithfulness | relevance | citation_quality | suggested_score | ungrounded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `production` | 10 | 1.00 | 2.90 | 2.30 | 2.40 | 1/10 |
| `stepwise` | 10 | 3.40 | 3.80 | 2.70 | 3.00 | 0/10 |
""",
        encoding="utf-8",
    )
    baseline_path = tmp_path / "baseline.json"
    history_path = tmp_path / "history.jsonl"
    _write_baseline(
        baseline_path,
        _make_baseline("judge.mean_faithfulness", 1.9, margin=0.4),
    )

    current = load_committed_judge_metrics(path)
    assert current["judge.mean_faithfulness"] == pytest.approx(1.0)
    assert run_gate(current, baseline_path, history_path) == 1


def test_parse_markdown_table_rejects_missing_and_empty_tables() -> None:
    from evals.gate import _parse_markdown_table

    with pytest.raises(ValueError, match="missing"):
        _parse_markdown_table("no pipes here")
    with pytest.raises(ValueError, match="no data rows"):
        _parse_markdown_table("| arm |\n| --- |\n")


def test_column_index_reports_missing_names() -> None:
    from evals.gate import _column_index

    with pytest.raises(ValueError, match="missing required column"):
        _column_index(["arm", "n"], "hit-rate@5")


def test_retrieval_falls_back_to_hybrid_rerank_without_winner_label(
    tmp_path: Path,
) -> None:
    from evals.gate import load_committed_retrieval_metrics

    path = tmp_path / "retrieval.md"
    path.write_text(
        """\
| arm | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| short |
| `lexical` | 10 | 0.1 | 0.1 |
| `hybrid_rerank` | 10 | 0.55 | 0.44 |
""",
        encoding="utf-8",
    )
    metrics = load_committed_retrieval_metrics(path)
    assert metrics["hybrid_rerank.hit_rate_at_5"] == pytest.approx(0.55)
    assert metrics["hybrid_rerank.mrr_at_5"] == pytest.approx(0.44)


def test_retrieval_missing_hybrid_rerank_row_fails(tmp_path: Path) -> None:
    from evals.gate import load_committed_retrieval_metrics

    path = tmp_path / "retrieval.md"
    path.write_text(
        """\
| arm | hit-rate@5 | MRR@5 |
| --- | ---: | ---: |
| `lexical` | 0.1 | 0.1 |
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hybrid_rerank"):
        load_committed_retrieval_metrics(path)


def test_judge_missing_production_row_fails(tmp_path: Path) -> None:
    from evals.gate import load_committed_judge_metrics

    path = tmp_path / "llm_eval.md"
    path.write_text(
        """\
| variant | faithfulness |
| --- | ---: |
| short |
| `stepwise` | 3.4 |
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="production"):
        load_committed_judge_metrics(path)


def test_current_git_sha_returns_unknown_when_git_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals import gate as gate_mod

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise OSError("no git")

    monkeypatch.setattr(gate_mod.subprocess, "run", _boom)
    assert gate_mod._current_git_sha() == "unknown"


def test_main_passes_against_committed_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`python -m evals.gate` must load named columns and exit 0 on tip reports."""
    from evals import gate as gate_mod

    retrieval = tmp_path / "retrieval.md"
    llm = tmp_path / "llm_eval.md"
    baseline = tmp_path / "baseline.json"
    history = tmp_path / "history.jsonl"
    retrieval.write_text(_RETRIEVAL_WINNER_TABLE, encoding="utf-8")
    llm.write_text(_LLM_EVAL_TABLE, encoding="utf-8")
    baseline.write_text(REAL_BASELINE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(gate_mod, "_DEFAULT_RETRIEVAL_REPORT", retrieval)
    monkeypatch.setattr(gate_mod, "_DEFAULT_LLM_REPORT", llm)
    monkeypatch.setattr(gate_mod, "_DEFAULT_BASELINE", baseline)
    monkeypatch.setattr(gate_mod, "_DEFAULT_HISTORY", history)

    assert gate_mod.main([]) == 0
    assert history.exists()
    record = json.loads(history.read_text(encoding="utf-8").splitlines()[0])
    assert record["metrics"]["hybrid_rerank.hit_rate_at_5"] == pytest.approx(0.638)
    assert record["metrics"]["judge.mean_faithfulness"] == pytest.approx(2.60)
def test_load_run_metrics_accepts_metrics_wrapper(tmp_path: Path) -> None:
    from evals.gate import load_run_metrics

    path = tmp_path / "run.json"
    path.write_text(
        json.dumps(
            {
                "run_id": "abc123",
                "metrics": {
                    "hybrid_rerank.hit_rate_at_5": 0.91,
                    "hybrid_rerank.mrr_at_5": 0.8,
                },
            }
        ),
        encoding="utf-8",
    )
    assert load_run_metrics(path) == {
        "hybrid_rerank.hit_rate_at_5": 0.91,
        "hybrid_rerank.mrr_at_5": 0.8,
    }


def test_load_run_metrics_rejects_empty_or_non_numeric(tmp_path: Path) -> None:
    from evals.gate import load_run_metrics

    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"run_id": "x", "metrics": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="no metrics"):
        load_run_metrics(empty)

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"hit_rate_at_5": "nope"}), encoding="utf-8")
    with pytest.raises(ValueError, match="numeric"):
        load_run_metrics(bad)


def test_main_from_run_gates_fresh_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from evals import gate as gate_mod

    baseline_path = tmp_path / "baseline.json"
    history_path = tmp_path / "history.jsonl"
    _write_baseline(baseline_path, _make_baseline("hit_rate_at_5", 0.78, margin=0.03))
    run_path = tmp_path / "metrics.json"
    run_path.write_text(json.dumps({"metrics": {"hit_rate_at_5": 0.79}}), encoding="utf-8")
    monkeypatch.setattr(gate_mod, "_DEFAULT_BASELINE", baseline_path)
    monkeypatch.setattr(gate_mod, "_DEFAULT_HISTORY", history_path)

    assert gate_mod.main(["--from-run", str(run_path)]) == 0
    assert history_path.exists()


def test_main_committed_mode_unchanged_without_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evals import gate as gate_mod

    baseline_path = tmp_path / "baseline.json"
    history_path = tmp_path / "history.jsonl"
    _write_baseline(
        baseline_path,
        Baseline(
            metrics={
                "hybrid_rerank.hit_rate_at_5": 0.5,
                "hybrid_rerank.mrr_at_5": 0.4,
                "judge.mean_faithfulness": 1.0,
            },
            specs={
                "hybrid_rerank.hit_rate_at_5": MetricSpec(
                    key="hybrid_rerank.hit_rate_at_5",
                    direction="higher_is_better",
                    margin=0.03,
                ),
                "hybrid_rerank.mrr_at_5": MetricSpec(
                    key="hybrid_rerank.mrr_at_5",
                    direction="higher_is_better",
                    margin=0.03,
                ),
                "judge.mean_faithfulness": MetricSpec(
                    key="judge.mean_faithfulness",
                    direction="higher_is_better",
                    margin=0.4,
                ),
            },
            notes={
                "hybrid_rerank.hit_rate_at_5": "t",
                "hybrid_rerank.mrr_at_5": "t",
                "judge.mean_faithfulness": "t",
            },
        ),
    )
    monkeypatch.setattr(gate_mod, "_DEFAULT_BASELINE", baseline_path)
    monkeypatch.setattr(gate_mod, "_DEFAULT_HISTORY", history_path)
    # Use the real committed reports so default mode stays archive regression.
    assert gate_mod.main([]) in {0, 1}


def test_ci_workflow_invokes_eval_gate() -> None:
    """Audit E04: Forgejo CI must call the committed-report gate."""
    text = Path(".forgejo/workflows/ci.yml").read_text(encoding="utf-8")
    assert "uv run python -m evals.gate" in text
    assert "Eval gate (committed reports)" in text
