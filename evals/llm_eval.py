"""Prompt-variant bake-off with an LLM judge — see specs/evals-llm.md.

Picks which answer-synthesis prompt ships on evidence rather than taste. At
least three named variants each answer the same set of ground-truth
questions through the real `homelib_rag.answer` path — same retrieval, same
citation validation, same degradation contract — and every answer is scored
by `evals.judge`, whose prompt is explicitly told it is not the model being
graded.

Only ONE thing varies between arms: the system prompt. `_VariantClient`
wraps the shared `OpenAICompatibleClient` seam and swaps the system message
on its way to the endpoint, so `answer.py` is exercised unmodified rather
than forked into an eval-only copy that could drift from production.

Two invariants worth stating out loud, because both hide failures if broken:

- A case the judge cannot parse is EXCLUDED from `VariantScore.n`, never
  scored as a neutral default. A silently defaulted score is worse than a
  missing one: it moves the mean and looks like data.
- A case the answer path could not produce is kept with `answer=""` and
  judged on its merits. Dropping it would let a variant that fails half the
  time outscore one that answers everything adequately.

Budget: a grounded answer costs roughly 13 s warm against the local model
(~18 tok/s, measured on the dev machine), and every case is answered once per
variant and judged once. `DEFAULT_QUESTION_BUDGET` questions x 3 variants x
(1 answer + 1 judge call) is therefore about 40*3*2*13 s ~ 50 min of wall
clock. That is the reason the budget is a parameter (`--questions`) and not
a number buried in a loop.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from homelib_rag.answer import (
    ChatMessage,
    Citation,
    LLMResponse,
    LLMUnreachableError,
    OpenAICompatibleClient,
    answer,
    default_llm_client,
)
from homelib_rag.models import Hit
from pydantic import BaseModel, ConfigDict

# `just eval-llm` runs this file as a script (`python evals/llm_eval.py`), which
# puts `evals/` — not the repo root — on sys.path, so the sibling `evals.*`
# imports below would not resolve. `uv` installs no top-level `homelib`
# package (pyproject sets `package = false`), so there is nothing else to put
# the root there. Prepending it here keeps the justfile recipe and
# `python -m evals.llm_eval` both working from one entry point.
if __package__ in (None, ""):  # pragma: no cover - only on the script path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.gate import Baseline, append_history, compare_to_baseline, load_baseline
from evals.ground_truth import GROUND_TRUTH_PATH, GroundTruthRow
from evals.judge import (
    JUDGE_PROMPT_VERSION,
    JUDGE_SCHEMA_SHAPE,
    JUDGE_SYSTEM_TEMPLATE,
    JudgeParseError,
    JudgeScore,
    judge,
    prompt_hash,
)

__all__ = [
    "DEFAULT_K",
    "DEFAULT_QUESTION_BUDGET",
    "PROMPT_VARIANTS",
    "REPORT_PATH",
    "AnsweredCase",
    "VariantScore",
    "run_variant",
    "score_variants",
    "write_report",
]

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPO_ROOT / "evals" / "results" / "llm_eval.md"
BASELINE_PATH = REPO_ROOT / "evals" / "eval-baseline.json"
HISTORY_PATH = REPO_ROOT / "evals" / "history.jsonl"

#: How many ground-truth questions each variant answers in a live run.
#: 40 sits in the middle of the spec's 30-50 band: enough that a 0.2-point
#: difference in a 1-5 mean is not one lucky case, few enough that the run
#: (see the budget note in the module docstring) finishes inside an hour.
#: Override with `--questions` when re-measuring a floor or smoke-testing.
DEFAULT_QUESTION_BUDGET = 40

#: Retrieval depth per question — matches `AskRequest.k`'s default in
#: specs/api.md, so the eval measures the prompt under production conditions.
DEFAULT_K = 5

#: The arm the bake-off runs on. Fixed across variants on purpose: this eval
#: isolates the prompt, and `evals/retrieval_eval.py` isolates the arm.
_ARM = "hybrid_rerank"

# The initial attempt plus exactly one retry, matching the judge's bound.
_MAX_ANSWER_ATTEMPTS = 2

# A bake-off needs at least three arms to be the comparison specs/evals-llm.md
# asks for; two arms and a winner is a coin toss with a table around it.
_MIN_VARIANTS_FOR_A_WINNER = 3

# Only the `judge.*` floors are this eval's to defend. The `hybrid_rerank.*`
# floors belong to evals/retrieval_eval.py; comparing against them here would
# report them "missing" and paint every run red for a reason that has nothing
# to do with prompt variants.
_JUDGE_METRIC_PREFIX = "judge."


# The shipped prompt, imported so the control arm cannot drift from production.
from homelib_rag.answer import _SYSTEM_PROMPT as _PRODUCTION_SYSTEM_PROMPT  # noqa: E402

# ── the prompt variants under test ──────────────────────────────────────────

# Every variant must keep the contract `homelib_rag.answer` parses and
# validates against: JSON only, a `passage` number drawn from the passages
# shown, and a `quote` copied verbatim. A variant that drops those does not
# lose the bake-off on prompt quality, it loses on failing to produce
# parseable output at all — which measures nothing, and measures it equally
# badly for every arm. So the shared contract text is appended to each
# variant, and only the reasoning style above it differs.
#
# `test_output_contract_names_the_fields_answer_py_actually_parses` pins this
# to `_RawCitation`'s real fields. Without that, production could move to a
# new citation shape while the eval kept asking for the old one, and every
# arm would score identically at rock bottom — a bake-off that looks like a
# result and is really just a broken harness.
_OUTPUT_CONTRACT = (
    " Every claim you make needs an entry in `citations` whose `quote` is "
    "copied VERBATIM (an exact run of words, not a paraphrase) from the "
    "passage you are citing, and whose `passage` is that passage's number in "
    "square brackets — one of the numbers shown, never one you were not "
    "given. The author names shown with each passage are authoritative: never "
    "attribute a passage to an author not listed for it. If the passages do "
    "not answer the question, say so plainly and return an empty `citations` "
    "list rather than guessing. Respond with ONLY a JSON object of the form "
    '{"answer": "...", "citations": [{"passage": 1, "quote": "..."}]} '
    "and no other text."
)

PROMPT_VARIANTS: dict[str, str] = {
    # Baseline style: shortest answer that fully answers the question.
    "concise": (
        "You answer a question using ONLY the numbered passages given below — "
        "never outside knowledge. Answer in at most three sentences. Say the "
        "answer first; do not restate the question, do not preface, do not "
        "summarise what you are about to say." + _OUTPUT_CONTRACT
    ),
    # Quote-anchored style: the evidence is chosen before the prose, which is
    # the ordering most likely to keep `faithfulness` high.
    "cited_first": (
        "You answer a question using ONLY the numbered passages given below — "
        "never outside knowledge. Work evidence-first: pick the passages that "
        "actually bear on the question, take the exact sentence from each that "
        "carries the point, and write your answer around those sentences. "
        "Every sentence of your answer must be traceable to one of the quotes "
        "you picked; if a sentence is not, delete it rather than cite something "
        "loosely related." + _OUTPUT_CONTRACT
    ),
    # Explicit-reasoning style: costs tokens, and is the variant most likely
    # to leak its scratch work into `answer` — which is itself worth measuring.
    "stepwise": (
        "You answer a question using ONLY the numbered passages given below — "
        "never outside knowledge. Reason in this order before writing: (1) what "
        "exactly is being asked; (2) which numbered passages contain something "
        "relevant, and which are near-misses to be ignored; (3) what those "
        "passages jointly support, and where they disagree or fall short. Then "
        "write the answer. Keep the reasoning to yourself: the `answer` field "
        "contains the conclusion for a reader, not your steps." + _OUTPUT_CONTRACT
    ),
    # The INCUMBENT — the prompt `answer.py` actually ships, imported rather
    # than copied so it cannot drift out of sync with production.
    #
    # Without it the bake-off compares three challengers to each other and says
    # nothing about whether to change anything. A winner among alternatives is
    # not evidence for switching; only a winner measured against what is
    # already running is. This arm is the control.
    #
    # It runs LAST, which matters more than it should: arms execute in this
    # dict's order, so anything that degrades over the run — memory pressure,
    # a second model loading — lands hardest here and would read as "the
    # prompt we ship is the worst one". That artifact has already been
    # produced once. Do not interpret a poor showing from this arm without
    # checking what the machine was doing.
    "production": _PRODUCTION_SYSTEM_PROMPT,
}


# ── data contracts ──────────────────────────────────────────────────────────


class AnsweredCase(BaseModel):
    """One question answered under one prompt variant."""

    model_config = ConfigDict(extra="allow")

    question: str
    variant: str
    answer: str
    citations: list[Citation]
    latency_ms: int


class VariantScore(BaseModel):
    """Judge means for one variant. `n` counts only successfully judged cases."""

    model_config = ConfigDict(extra="allow")

    variant: str
    n: int
    mean_faithfulness: float
    mean_relevance: float
    mean_citation_quality: float
    mean_suggested_score: float


# ── the one thing that varies between arms ──────────────────────────────────


class _VariantClient:
    """An `OpenAICompatibleClient` that substitutes the system prompt.

    `answer()` owns its own `_SYSTEM_PROMPT` and takes no prompt argument, by
    design — production must not be able to pass an arbitrary system prompt.
    Swapping the message here, at the client seam, lets the bake-off vary the
    prompt while leaving every other line of the answer path (context
    building, citation validation, degradation) exactly as it ships.
    """

    def __init__(self, inner: OpenAICompatibleClient, system_prompt: str) -> None:
        self.model = inner.model
        self._inner = inner
        self._system_prompt = system_prompt

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        response_format: Mapping[str, Any] | None = None,
    ) -> LLMResponse:
        swapped = [
            message.model_copy(update={"content": self._system_prompt})
            if message.role == "system"
            else message
            for message in messages
        ]
        return self._inner.chat(swapped, tools=tools, response_format=response_format)


def _default_retrieve(query: str, k: int) -> list[Hit]:
    """Production retrieval for the fixed `_ARM`: hybrid search plus rerank.

    Imported lazily because `homelib_rag.index` pulls in
    `sentence_transformers` at import time; keeping that out of module import
    means the unit tests (which never retrieve) do not pay for it.
    """
    from homelib_rag.hybrid import hybrid_search
    from homelib_rag.rerank import rerank

    hits, _mode_used = hybrid_search(query, k, mode="hybrid")
    if not hits:
        return []
    reranked = rerank(query, hits)
    return reranked if reranked is not None else hits


# ── run one variant ─────────────────────────────────────────────────────────


def _answer_one(
    variant: str,
    row: GroundTruthRow,
    client: OpenAICompatibleClient,
    retrieve: Callable[[str, int], list[Hit]],
    k: int,
) -> AnsweredCase:
    """Answer one question, retrying once, then recording the failure honestly.

    `answer()` never raises — it reports trouble as `degraded=True` — so a
    degraded result is the signal to retry, and a second degraded result
    becomes an `answer=""` case the judge will (correctly) score at the floor.
    """
    started = time.monotonic()
    for attempt in range(1, _MAX_ANSWER_ATTEMPTS + 1):
        try:
            hits = retrieve(row.question, k)
        except Exception as exc:
            logger.warning(
                "retrieval failed on attempt %d/%d for variant %r: %s",
                attempt,
                _MAX_ANSWER_ATTEMPTS,
                variant,
                exc,
            )
            continue

        result = answer(row.question, hits, client=client, arm_used=_ARM)
        if not result.degraded:
            return AnsweredCase(
                question=row.question,
                variant=variant,
                answer=result.answer,
                citations=result.citations,
                latency_ms=result.latency_ms,
            )
        logger.warning(
            "degraded answer on attempt %d/%d for variant %r",
            attempt,
            _MAX_ANSWER_ATTEMPTS,
            variant,
        )

    return AnsweredCase(
        question=row.question,
        variant=variant,
        answer="",
        citations=[],
        latency_ms=int((time.monotonic() - started) * 1000),
    )


def run_variant(
    variant: str,
    questions: list[GroundTruthRow],
    *,
    client: OpenAICompatibleClient | None = None,
    retrieve: Callable[[str, int], list[Hit]] | None = None,
    k: int = DEFAULT_K,
) -> list[AnsweredCase]:
    """Answer every question in `questions` under `variant`'s system prompt.

    Always returns one `AnsweredCase` per question — a failure is recorded
    with `answer=""`, never dropped, so a variant cannot improve its own
    means by failing.
    """
    if variant not in PROMPT_VARIANTS:
        raise KeyError(f"unknown prompt variant {variant!r}; known: {sorted(PROMPT_VARIANTS)}")

    inner = client if client is not None else default_llm_client()
    variant_client = _VariantClient(inner, PROMPT_VARIANTS[variant])
    retrieve_fn = retrieve if retrieve is not None else _default_retrieve

    return [_answer_one(variant, row, variant_client, retrieve_fn, k) for row in questions]


# ── score the arms ──────────────────────────────────────────────────────────


def _mean(values: Sequence[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def score_variants(
    cases_by_variant: dict[str, list[AnsweredCase]],
    *,
    client: OpenAICompatibleClient | None = None,
) -> list[VariantScore]:
    """Judge every case and reduce to one `VariantScore` per variant.

    A case whose judge call fails to parse (twice) or whose endpoint is
    unreachable is excluded from `n` and from every mean — see the module
    docstring on why a defaulted score is worse than a missing one. Variants
    with no judgeable case at all still get a row, with `n == 0`, so
    `write_report` can see the hole rather than infer it from an absence.
    """
    scores: list[VariantScore] = []
    for variant, cases in cases_by_variant.items():
        judged: list[JudgeScore] = []
        for case in cases:
            try:
                judged.append(
                    judge(
                        case.question,
                        case.answer,
                        case.citations,
                        client=client,
                        variant=variant,
                    )
                )
            except JudgeParseError as exc:
                logger.warning("excluding an unjudgeable case from %r: %s", variant, exc)
            except LLMUnreachableError as exc:
                logger.warning("excluding a case from %r, judge endpoint down: %s", variant, exc)

        scores.append(
            VariantScore(
                variant=variant,
                n=len(judged),
                mean_faithfulness=_mean([j.faithfulness for j in judged]),
                mean_relevance=_mean([j.relevance for j in judged]),
                mean_citation_quality=_mean([j.citation_quality for j in judged]),
                mean_suggested_score=_mean([j.suggested_score for j in judged]),
            )
        )
    return scores


def _winner(scores: Sequence[VariantScore]) -> VariantScore | None:
    """The winning variant, or `None` when the comparison is not sound.

    Refuses in two cases, both of which would otherwise be presented as a
    finished result: fewer than three arms, or any arm with `n == 0`. An arm
    that scored nothing did not lose — it did not run, and a report that
    quietly crowns one of the survivors hides a broken pipeline.
    """
    if len(scores) < _MIN_VARIANTS_FOR_A_WINNER:
        return None
    if any(score.n == 0 for score in scores):
        return None
    # Ranked on the judge's own overall rating, deliberately — not on a
    # recomputed average of the sub-scores. Faithfulness breaks ties because
    # an ungrounded answer is the failure this whole system exists to avoid.
    return max(scores, key=lambda s: (s.mean_suggested_score, s.mean_faithfulness))


def write_report(scores: list[VariantScore], path: Path) -> None:
    """Write the markdown bake-off report, marking a winner only if there is one."""
    current_hash = prompt_hash(JUDGE_PROMPT_VERSION, JUDGE_SYSTEM_TEMPLATE, JUDGE_SCHEMA_SHAPE)
    lines = [
        "# LLM prompt-variant eval",
        "",
        f"Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"Judge prompt: version {JUDGE_PROMPT_VERSION}, hash `{current_hash}`",
        f"Answer arm: `{_ARM}`, k={DEFAULT_K}",
        "",
        "| variant | n | faithfulness | relevance | citation_quality | suggested_score |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for score in sorted(scores, key=lambda s: s.variant):
        lines.append(
            f"| `{score.variant}` | {score.n} | {score.mean_faithfulness:.2f} | "
            f"{score.mean_relevance:.2f} | {score.mean_citation_quality:.2f} | "
            f"{score.mean_suggested_score:.2f} |"
        )
    lines.append("")

    winner = _winner(scores)
    if winner is not None:
        lines.append(
            f"**Winner: `{winner.variant}`** — highest mean suggested_score "
            f"({winner.mean_suggested_score:.2f}), the judge's own overall rating "
            "rather than an average of the sub-scores."
        )
    else:
        empty = [score.variant for score in scores if score.n == 0]
        lines.append("**No winner marked.**")
        if empty:
            lines.append("")
            lines.append(
                "Variant(s) with zero scored cases: "
                + ", ".join(f"`{variant}`" for variant in sorted(empty))
                + ". A report with a missing arm is a build failure, not a "
                "narrower comparison presented as complete."
            )
        if len(scores) < _MIN_VARIANTS_FOR_A_WINNER:
            lines.append("")
            lines.append(
                f"Only {len(scores)} variant(s) scored; a bake-off needs at least "
                f"{_MIN_VARIANTS_FOR_A_WINNER}."
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── entry point ─────────────────────────────────────────────────────────────


def load_questions(
    path: Path = GROUND_TRUTH_PATH, *, budget: int = DEFAULT_QUESTION_BUDGET
) -> list[GroundTruthRow]:
    """Up to `budget` ground-truth rows, spread round-robin across books.

    Taking the first `budget` lines would sample one or two books, because
    `evals/ground_truth.jsonl` is written grouped by chunk. Round-robin over
    `book_id` in file order keeps the selection deterministic (no seed to
    drift) while covering the shelf.
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
    while len(picked) < budget and any(depth < len(by_book[book]) for book in books):
        for book in books:
            if len(picked) >= budget:
                break
            if depth < len(by_book[book]):
                picked.append(by_book[book][depth])
        depth += 1
    return picked


def _judge_metrics(scores: Sequence[VariantScore]) -> dict[str, float]:
    """The gate-facing metrics for this run: the winning variant's means.

    Empty when there is no winner — an unsound comparison must not publish a
    number the gate would then treat as a real measurement.
    """
    winner = _winner(scores)
    if winner is None:
        return {}
    return {"judge.mean_faithfulness": winner.mean_faithfulness}


def _run_judge_gate(scores: Sequence[VariantScore]) -> int:
    """Compare this run's judge metrics to the committed baseline; record history."""
    full = load_baseline(BASELINE_PATH)
    scoped_keys = [key for key in full.metrics if key.startswith(_JUDGE_METRIC_PREFIX)]
    scoped = Baseline(
        metrics={key: full.metrics[key] for key in scoped_keys},
        specs={key: full.specs[key] for key in scoped_keys},
        notes={key: full.notes[key] for key in scoped_keys},
    )

    current = _judge_metrics(scores)
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


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score answer-prompt variants with an LLM judge.")
    parser.add_argument(
        "--questions",
        type=int,
        default=DEFAULT_QUESTION_BUDGET,
        help="ground-truth questions per variant (default: %(default)s)",
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_K, help="retrieval depth (default: %(default)s)"
    )
    parser.add_argument(
        "--variant",
        action="append",
        choices=sorted(PROMPT_VARIANTS),
        help="restrict to one variant; repeatable (default: all)",
    )
    parser.add_argument(
        "--report", type=Path, default=REPORT_PATH, help="report path (default: %(default)s)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(argv)
    started = time.monotonic()

    variants = args.variant if args.variant else sorted(PROMPT_VARIANTS)
    questions = load_questions(budget=args.questions)
    print(f"{len(questions)} questions x {len(variants)} variants (+ one judge call each)")

    cases_by_variant: dict[str, list[AnsweredCase]] = {}
    for variant in variants:
        cases_by_variant[variant] = run_variant(variant, questions, k=args.k)
        print(f"  answered {variant}: {len(cases_by_variant[variant])} cases")

    scores = score_variants(cases_by_variant)
    write_report(scores, args.report)
    print(f"wrote {args.report} in {time.monotonic() - started:.1f}s")
    print(json.dumps([score.model_dump() for score in scores], indent=2))

    if _winner(scores) is None:
        print("✗ no winner: an arm scored zero cases, or fewer than 3 arms ran")
        return 1
    return _run_judge_gate(scores)


if __name__ == "__main__":
    raise SystemExit(main())
