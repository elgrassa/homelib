"""Eval regression gate — see specs/eval-gate.md.

Turns "the eval numbers got worse" into a build failure. A regression is
defined per-metric as a `MetricSpec` (direction + absolute tolerance
`margin`); `compare_to_baseline` is a pure function (no I/O, never mutates
its arguments) so it is unit-testable without a real eval run; every run is
appended to `evals/history.jsonl` (append-only, never rewritten or
truncated) so slow drift across many small PRs stays visible.

Regression rule: a metric that moves in the *wrong* direction (down for
`higher_is_better`, up for `lower_is_better`) by more than its `margin` is a
regression. Movement within the margin, or movement in the *right*
direction by any amount, is not. A metric present in the baseline but
missing from the current run is always a regression — a metric that
silently stopped being computed must fail the gate, not be skipped.
"""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, model_validator

__all__ = [
    "Baseline",
    "MetricSpec",
    "Regression",
    "append_history",
    "compare_to_baseline",
    "load_baseline",
    "run_gate",
]


class MetricSpec(BaseModel):
    """How to judge movement in one metric."""

    key: str
    direction: Literal["higher_is_better", "lower_is_better"]
    margin: float


class Baseline(BaseModel):
    """The committed floor every eval run is compared against.

    Every key in `metrics` MUST have a matching `MetricSpec` in `specs` and a
    non-empty explanatory string in `notes` — an un-noted floor is not a
    floor, it is a number nobody will remember the reason for.
    """

    metrics: dict[str, float]
    specs: dict[str, MetricSpec]
    notes: dict[str, str]

    @model_validator(mode="after")
    def _check_every_metric_is_specced_and_noted(self) -> Self:
        for key in self.metrics:
            if key not in self.specs:
                raise ValueError(f"baseline metric {key!r} has no MetricSpec in `specs`")
            if not self.notes.get(key, "").strip():
                raise ValueError(f"baseline metric {key!r} has no non-empty note in `notes`")
        return self


class Regression(BaseModel):
    """One metric that regressed beyond its margin (or went missing)."""

    key: str
    baseline: float
    current: float
    margin: float
    delta: float  # current - baseline, signed; NaN when `current` is missing


def load_baseline(path: Path) -> Baseline:
    """Load and validate `evals/eval-baseline.json`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return Baseline.model_validate(data)


def compare_to_baseline(current: dict[str, float], baseline: Baseline) -> list[Regression]:
    """Return every metric that regressed beyond its margin.

    Pure: never mutates `current` or `baseline`, performs no I/O. A metric
    present in `baseline.metrics` but absent from `current` is always
    reported as a `Regression`, with `current=float("nan")` acting as the
    "missing" sentinel (`math.isnan` distinguishes it from "worse").
    """
    regressions: list[Regression] = []
    for key, baseline_value in baseline.metrics.items():
        spec = baseline.specs[key]

        if key not in current:
            regressions.append(
                Regression(
                    key=key,
                    baseline=baseline_value,
                    current=float("nan"),
                    margin=spec.margin,
                    delta=float("nan"),
                )
            )
            continue

        current_value = current[key]
        delta = current_value - baseline_value
        # Positive `wrong_direction_move` means movement the wrong way.
        wrong_direction_move = -delta if spec.direction == "higher_is_better" else delta
        if wrong_direction_move > spec.margin:
            regressions.append(
                Regression(
                    key=key,
                    baseline=baseline_value,
                    current=current_value,
                    margin=spec.margin,
                    delta=delta,
                )
            )
    return regressions


def _current_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - fixed args, no shell, best-effort
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"
    return result.stdout.strip()


def append_history(
    current: dict[str, float],
    path: Path,
    *,
    regressions: Sequence[str] | None = None,
    git_sha: str | None = None,
) -> None:
    """Append one run record to `path` as a JSON line. Never truncates or rewrites.

    `regressions`/`git_sha` are optional so callers that only care about the
    append-only contract (or don't yet know the regression set) can call this
    with just `current` and `path`; `run_gate` supplies both.
    """
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "git_sha": git_sha if git_sha is not None else _current_git_sha(),
        "metrics": current,
        "regressions": list(regressions) if regressions is not None else [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as history_file:
        history_file.write(json.dumps(record, sort_keys=True) + "\n")


def _describe(regression: Regression) -> str:
    if math.isnan(regression.current):
        return (
            f"REGRESSION {regression.key}: MISSING from current run "
            f"(baseline={regression.baseline})"
        )
    return (
        f"REGRESSION {regression.key}: baseline={regression.baseline} "
        f"current={regression.current} delta={regression.delta:+.4f} margin={regression.margin}"
    )


def run_gate(current: dict[str, float], baseline_path: Path, history_path: Path) -> int:
    """Compare `current` to the committed baseline, always record history, return exit code.

    History is appended even when the run fails the gate, so `history.jsonl`
    is a true record of every attempt, not just the passing ones.
    """
    baseline = load_baseline(baseline_path)
    regressions = compare_to_baseline(current, baseline)
    append_history(
        current,
        history_path,
        regressions=[regression.key for regression in regressions],
        git_sha=_current_git_sha(),
    )
    for regression in regressions:
        print(_describe(regression))
    return 1 if regressions else 0
