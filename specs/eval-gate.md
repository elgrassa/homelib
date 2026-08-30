# spec: eval-gate — `evals/gate.py`

**Implemented by:** WP-15.
**Consumed by:** `just ci` (deterministic parts) and `just eval` (LLM parts);
Forgejo CI fails the build on a real regression.

## Purpose

Make "the eval numbers got worse" a build failure instead of a paragraph nobody
reads. A regression is defined per-metric (direction + tolerance margin), the
comparison is a pure function against a committed baseline, and every run is
appended to an audit trail so a metric drifting slowly across many small PRs is
still visible.

## Public interface

```python
class MetricSpec(BaseModel):
    key: str                       # e.g. "hybrid_rerank.hit_rate_at_5"
    direction: Literal["higher_is_better", "lower_is_better"]
    margin: float                  # absolute tolerance; a drop/rise within margin is NOT a regression

class Baseline(BaseModel):
    metrics: dict[str, float]          # key -> baseline value
    specs: dict[str, MetricSpec]       # key -> its MetricSpec
    notes: dict[str, str]              # key -> human "_note" explaining why THIS is the floor

class Regression(BaseModel):
    key: str
    baseline: float
    current: float
    margin: float
    delta: float                       # current - baseline, signed

def load_baseline(path: Path) -> Baseline: ...
def compare_to_baseline(current: dict[str, float], baseline: Baseline) -> list[Regression]: ...
def append_history(current: dict[str, float], path: Path) -> None: ...
    # evals/history.jsonl — one line per run, append-only, never rewritten or truncated
def run_gate(current: dict[str, float], baseline_path: Path, history_path: Path) -> int: ...
    # writes history, prints regressions, returns process exit code (0 or 1)
```

## Data contracts (field-level)

`evals/eval-baseline.json`:

```json
{
  "metrics": {"hybrid_rerank.hit_rate_at_5": 0.78, "hybrid_rerank.mrr_at_5": 0.61,
              "judge.mean_faithfulness": 4.1},
  "specs": {
    "hybrid_rerank.hit_rate_at_5": {"key": "hybrid_rerank.hit_rate_at_5",
      "direction": "higher_is_better", "margin": 0.03},
    "judge.mean_faithfulness": {"key": "judge.mean_faithfulness",
      "direction": "higher_is_better", "margin": 0.15}
  },
  "notes": {
    "hybrid_rerank.hit_rate_at_5": "0.78 measured on the 2026-08 ground-truth set (WP-12 winner run); 0.03 margin absorbs LLM ground-truth generation noise between runs, not real regressions.",
    "judge.mean_faithfulness": "4.1/5 measured with the WP-15 winning prompt; 0.15 margin absorbs judge-model variance, chosen after re-running the same variant 3x and observing +-0.1 spread."
  }
}
```

Every key present in `metrics` MUST have a matching entry in `specs` and a
non-empty `_note`-equivalent string in `notes` — an un-noted floor is not a
floor, it is a number someone will not remember the reason for.

`evals/history.jsonl` — one JSON object per line, append-only:

```
{ts: str (ISO8601), git_sha: str, metrics: dict[str, float], regressions: list[str]}
```

## Error/degradation behavior

- A `current` run missing a key that `baseline.metrics` has is itself a
  regression (`Regression` with `current = float("nan")`-safe sentinel and a
  message distinguishing "missing" from "worse") — a metric that silently
  stopped being computed must fail the gate, not be skipped.
- `compare_to_baseline` never mutates `baseline` or `current` and has no I/O —
  it is a pure function so it can be unit tested without a real eval run.
- `append_history` opens in append mode only; the spec forbids any code path
  that opens `history.jsonl` for write/truncate. A corrupt trailing line found
  on read is logged and skipped, never silently dropped without a warning.
- `run_gate` always appends to history — even on a failing run — so the
  history is a true record of every attempt, not just the passing ones.

## Named red tests (write before the code)

- `test_regression_detected_beyond_margin` — baseline `0.78`, current `0.70`,
  margin `0.03`, `higher_is_better` -> exactly one `Regression` returned with
  `delta == -0.08`.
- `test_within_margin_is_not_a_regression` — baseline `0.78`, current `0.76`,
  margin `0.03` -> `compare_to_baseline` returns `[]`.
- `test_lower_is_better_direction_flips_comparison` — a `lower_is_better`
  metric that INCREASES beyond margin is flagged; the same increase on a
  `higher_is_better` metric of equal magnitude is not (paired hand-computed
  case, both directions in one test).
- `test_missing_current_metric_is_a_regression`.
- `test_history_is_append_only` — call `append_history` three times against
  the same file, assert the file has exactly 3 lines and all 3 are still
  present (no line was overwritten).
- `test_every_baseline_metric_has_a_note` — loads the real committed
  `evals/eval-baseline.json` and asserts `notes[key]` is non-empty for every
  key in `metrics`.

## Verify

```
uv run pytest evals/tests/test_gate.py -v
just eval-llm    # exit 0 on a healthy run, appends one evals/history.jsonl line
# red drill: tamper with evals/eval-baseline.json (tighten a margin on a metric
# the current run is close to), re-run `just eval`, confirm non-zero exit and a
# printed Regression, then restore the file:
git diff --stat evals/eval-baseline.json   # confirm restored, no leftover diff
```
