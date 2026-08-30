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
