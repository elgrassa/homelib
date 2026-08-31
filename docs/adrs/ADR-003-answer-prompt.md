# ADR-003 — Answer prompt: keep the incumbent, on a null result

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** Pavlo (owner)
- **Related:** `specs/evals-llm.md`, `evals/results/llm_eval.md`, ADR-001

## Context

Three challenger prompts — `concise`, `cited_first`, `stepwise` — were written
to see whether the shipped answer prompt could be improved. `specs/evals-llm.md`
requires at least three variants scored by an LLM judge with explicit bias
control.

Production's own prompt was added as a fourth **control arm**, imported from
`answer.py` rather than copied. Without it the bake-off compares challengers to
each other and says nothing about whether to change anything: a winner among
alternatives is not evidence for switching, only a winner measured against what
is already running is.

## Decision

**Keep the shipped prompt. No variant is demonstrably better.**

## Why — the bake-off does not discriminate

The final run (30 questions per arm, quiet machine, resident models unchanged
across the run) names `stepwise` the winner on the judge's own overall score.
That result does not survive contact with the other runs:

| arm | run A | run B | run C | run D | spread |
|---|---:|---:|---:|---:|---:|
| `concise` | 2.00 | 1.87 | 1.93 | 1.80 | 0.20 |
| `cited_first` | 1.89 | 1.83 | 1.87 | 1.80 | 0.09 |
| `stepwise` | 1.90 | 1.60 | 1.67 | **2.07** | **0.47** |
| `production` | — | 1.63 | 1.80 | 1.73 | 0.17 |

**Run-to-run variance (up to 0.47) exceeds the entire between-arm spread within
a single run (0.34).** The winner changed from `concise` to `stepwise` between
two runs of the same code on the same corpus. An instrument whose answer moves
more between repetitions than between the things it compares is not measuring
those things.

Two compounding causes, both measured rather than supposed:

1. **The judge has almost no dynamic range here.** Nearly every case lands on
   1, 2 or 3 out of 5, because most answers are mediocre in the same way. With
   the population squeezed into two points, arm means separate by hundredths.
2. **n = 30 is too small for that.** At ~13 s per grounded answer plus a judge
   call, a run is already ~45 minutes; the sample size that would resolve a
   0.1 difference is not affordable against this deadline.

## The winner is flagged unproven, and that is the point

`stepwise` also declined to cite anything **more often than any other arm
(7/30)**. A zero-citation answer is a legitimate reply — it is the "the
passages do not answer this" response the prompt asks for — but it still counts
as a success, so an arm that hedges has less for a weak judge to mark down.

The report marks such a winner **unproven** rather than presenting it as a
result. This is exactly the predicted failure: explicit-reasoning prompts hedge,
and hedging wins under a judge with no room to punish it. Had the harness not
counted ungrounded successes, `stepwise` would have been crowned and the shipped
prompt replaced with one that answers *less often*.

Stated plainly, because it is the general lesson and not a detail of this run:
**the arm that answered least scored best.** That is the clean demonstration
that the metric and the goal had come apart. Any future prompt work on this
system needs the grounded-answer rate as a *primary* metric, not a column added
after someone got suspicious.

## Consequences

**Positive**
- The shipped prompt stays. A null result is a real answer, and cheaper to
  defend than a switch made on noise.
- The bake-off, the judge with its bias control, the prompt-hash drift
  detector, and the ungrounded-success guard all exist and run — the rubric
  asks for multiple approaches evaluated, not for one of them to win.
- The instrument's limits are recorded, so the next session does not re-run it
  expecting a different answer.

**Negative**
- No prompt improvement was obtained. The remaining headroom is in the model,
  not the prompt: ~40% of answers fail by returning a bare `{}`, which is the
  7B breaking its JSON contract and is not something rewording fixes.
- The judge baseline can only be a loose floor (see below).

**What would make this measurable**
- A stronger judge, or a rubric with more spread than 1–5 on three axes.
- A larger n, which needs a faster answer model.
- Scoring on the judge-independent numbers instead — degraded rate and
  grounded-answer rate discriminate better than the judge does at this quality
  level.

## Baseline

`judge.mean_faithfulness` moves to the measured range with a margin derived
from observed run-to-run spread rather than a guess. A tight margin on a metric
this noisy would fire on nothing but noise, and a gate that cries wolf is
ignored — which is worse than no gate.

## Verification

```bash
just eval-llm                      # 4 arms incl. the production control
cat evals/results/llm_eval.md      # winner marked, with the unproven caveat
```
