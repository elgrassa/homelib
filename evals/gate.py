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
    "load_committed_judge_metrics",
    "load_committed_retrieval_metrics",
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


# ── committed markdown report loaders (`just eval-gate`) ─────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RETRIEVAL_REPORT = _REPO_ROOT / "evals" / "results" / "retrieval.md"
_DEFAULT_LLM_REPORT = _REPO_ROOT / "evals" / "results" / "llm_eval.md"
_DEFAULT_BASELINE = _REPO_ROOT / "evals" / "eval-baseline.json"
_DEFAULT_HISTORY = _REPO_ROOT / "evals" / "history.jsonl"


def _split_md_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator_row(cells: Sequence[str]) -> bool:
    return bool(cells) and all(set(cell) <= {"-", ":"} for cell in cells)


def _parse_markdown_table(text: str) -> tuple[list[str], list[list[str]]]:
    """Return (header, data rows) for the first pipe table in `text`."""
    lines = [line for line in text.splitlines() if "|" in line]
    if len(lines) < 2:
        raise ValueError("markdown table missing from report")
    header = _split_md_row(lines[0])
    body_start = 1
    if _is_separator_row(_split_md_row(lines[1])):
        body_start = 2
    rows = [_split_md_row(line) for line in lines[body_start:]]
    rows = [row for row in rows if row and not _is_separator_row(row)]
    if not rows:
        raise ValueError("markdown table has no data rows")
    return header, rows


def _column_index(header: Sequence[str], *names: str) -> int:
    lowered = [name.casefold() for name in header]
    for name in names:
        key = name.casefold()
        if key in lowered:
            return lowered.index(key)
    raise ValueError(f"table missing required column among {names!r}; got {list(header)!r}")


def _require_unit_interval(name: str, value: float) -> float:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name}={value} is outside the unit interval [0, 1]")
    return value


def load_committed_retrieval_metrics(path: Path) -> dict[str, float]:
    """Read hybrid_rerank hit-rate@5 and MRR@5 by column name from a retrieval report.

    Positional regex captures after `(winner)` are unsafe: the `n` column can be
    mistaken for hit-rate. Named columns reject that class of false green.
    """
    header, rows = _parse_markdown_table(path.read_text(encoding="utf-8"))
    arm_i = _column_index(header, "arm")
    hit_i = _column_index(header, "hit-rate@5")
    mrr_i = _column_index(header, "MRR@5", "mrr@5")

    winner_row: list[str] | None = None
    for row in rows:
        if len(row) <= max(arm_i, hit_i, mrr_i):
            continue
        arm_cell = row[arm_i]
        if "hybrid_rerank" in arm_cell and "winner" in arm_cell.casefold():
            winner_row = row
            break
    if winner_row is None:
        for row in rows:
            if len(row) <= max(arm_i, hit_i, mrr_i):
                continue
            if "hybrid_rerank" in row[arm_i]:
                winner_row = row
                break
    if winner_row is None:
        raise ValueError("hybrid_rerank row missing from retrieval report")

    hit_rate = _require_unit_interval("hybrid_rerank.hit_rate_at_5", float(winner_row[hit_i]))
    mrr = _require_unit_interval("hybrid_rerank.mrr_at_5", float(winner_row[mrr_i]))
    return {
        "hybrid_rerank.hit_rate_at_5": hit_rate,
        "hybrid_rerank.mrr_at_5": mrr,
    }


def load_committed_judge_metrics(path: Path) -> dict[str, float]:
    """Read `production` faithfulness from an llm_eval.md table (not the bake-off winner)."""
    header, rows = _parse_markdown_table(path.read_text(encoding="utf-8"))
    variant_i = _column_index(header, "variant")
    faith_i = _column_index(header, "faithfulness")

    for row in rows:
        if len(row) <= max(variant_i, faith_i):
            continue
        if row[variant_i].strip("` ") == "production":
            return {"judge.mean_faithfulness": float(row[faith_i])}
    raise ValueError("production variant row missing from llm_eval report")


def main(argv: list[str] | None = None) -> int:
    """Compare committed retrieval + production-judge report numbers to the baseline."""
    del argv  # reserved for future CLI flags; recipe takes no args today
    current = {
        **load_committed_retrieval_metrics(_DEFAULT_RETRIEVAL_REPORT),
        **load_committed_judge_metrics(_DEFAULT_LLM_REPORT),
    }
    return run_gate(current, _DEFAULT_BASELINE, _DEFAULT_HISTORY)


if __name__ == "__main__":
    raise SystemExit(main())
