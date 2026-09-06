"""Answer-similarity (cosine) eval — a second, judge-free LLM-eval method.

`evals/llm_eval.py` scores generated answers with an LLM judge (faithfulness,
relevance, citation_quality, suggested_score). That judge is itself a model
call: slow (~13s per case), noisy (see `evals/eval-baseline.json`'s
`judge.mean_faithfulness` note — up to 0.47 run-to-run variance on the same
code and corpus), and scored on a 1-5 scale with almost no dynamic range at
this answer quality. This module offers a cheap, deterministic complement,
not a replacement: embed each generated answer and its REFERENCE text (the
ground-truth chunk the question was generated from, per
`evals/ground_truth.jsonl`) with the same `all-MiniLM-L6-v2` model
`homelib_rag.index`'s vector arm already uses, and score cosine similarity
between the two. A high similarity says "this answer talks about the same
content as the passage it should be grounded in" — a narrower claim than the
judge's faithfulness/relevance, useful precisely because it needs no LLM call
and is perfectly reproducible given the same answers.

Input is a `--save-answers` JSON Lines file from `evals/llm_eval.py` (one
`AnsweredCase`-shaped row per line: `question`/`variant`/`answer`, extra
fields ignored). This module does not run `evals/llm_eval.py` itself — it
only scores whatever answers already exist on disk.

An answer whose question does not resolve to a live ground-truth chunk (a
typo'd question, or corpus drift since the answers were generated) is
EXCLUDED from scoring, never defaulted to 0.0 or 1.0 — same "excluded, not
scored as a neutral default" rule `evals/llm_eval.py`'s judge scoring uses
for a case the judge could not parse.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from statistics import mean, median
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

# `python evals/answer_similarity.py` runs this file as a script, which puts
# `evals/` — not the repo root — on sys.path, so the sibling `evals.*` imports
# below would not resolve. Mirrors evals/retrieval_eval.py and evals/llm_eval.py.
if __package__ in (None, ""):  # pragma: no cover - only on the script path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.ground_truth import GROUND_TRUTH_PATH, GroundTruthRow, load_corpus_chunks

if TYPE_CHECKING:
    import numpy as np
    from homelib_core.models import Chunk
    from numpy.typing import NDArray

__all__ = [
    "REPORT_PATH",
    "AnswerSimilarityScore",
    "SavedAnswer",
    "VariantSimilarity",
    "build_reference_lookup",
    "load_answers",
    "score_answers",
    "summarize_by_variant",
    "write_similarity_section",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
#: Same file `evals/llm_eval.py` writes its judge table into — this module
#: upserts a second, independent section rather than writing its own file, so
#: a reader sees both LLM-eval methods for the same run side by side.
REPORT_PATH = REPO_ROOT / "evals" / "results" / "llm_eval.md"

#: Matches `homelib_rag.index._DEFAULT_EMBED_MODEL` — the vector arm's own
#: embedder. Repeated rather than imported because importing
#: `homelib_rag.index` pulls in `psycopg`/Postgres connection machinery this
#: module has no other reason to need.
_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

#: `texts -> one row-vector per text`. The test seam: a unit test supplies a
#: tiny deterministic fake so scoring never downloads a model.
Embedder = Callable[[Sequence[str]], "NDArray[np.float64]"]


# ── data contracts ───────────────────────────────────────────────────────────


class SavedAnswer(BaseModel):
    """One row of a `--save-answers` JSONL file from `evals/llm_eval.py`.

    Deliberately its own minimal model rather than importing
    `evals.llm_eval.AnsweredCase`: only `question`/`variant`/`answer` are
    needed here, and importing `llm_eval.py` pulls in `homelib_rag.answer`
    (the OpenAI SDK) at module import time for no benefit to this module.
    `extra="allow"` so the extra fields `AnsweredCase` writes (`citations`,
    `latency_ms`) round-trip through unused rather than failing validation.
    """

    model_config = ConfigDict(extra="allow")

    question: str
    variant: str
    answer: str


class AnswerSimilarityScore(BaseModel):
    """One answered case's cosine similarity to its reference chunk text."""

    model_config = ConfigDict(extra="allow")

    question: str
    variant: str
    similarity: float


class VariantSimilarity(BaseModel):
    """Mean/median cosine similarity for one variant, over scoreable cases."""

    model_config = ConfigDict(extra="allow")

    variant: str
    n: int
    mean_similarity: float
    median_similarity: float


# ── loading ──────────────────────────────────────────────────────────────────


def load_answers(path: Path) -> list[SavedAnswer]:
    """Load a `--save-answers` JSON Lines file. Blank lines are skipped."""
    answers: list[SavedAnswer] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            answers.append(SavedAnswer.model_validate_json(stripped))
    return answers


def _load_ground_truth_rows(path: Path) -> list[GroundTruthRow]:
    """Every row of `evals/ground_truth.jsonl`, blank lines skipped.

    A third near-identical copy of this loop, alongside
    `evals/retrieval_eval.py` and `evals/llm_eval.py`'s own `load_questions` —
    each module keeps its own so it stays importable without pulling in the
    others' heavier dependencies (Postgres, the OpenAI SDK). This module
    needs every row, unsampled, so there is no budget/round-robin logic to
    duplicate on top of the read.
    """
    rows: list[GroundTruthRow] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(GroundTruthRow.model_validate_json(stripped))
    return rows


def build_reference_lookup(
    ground_truth_path: Path = GROUND_TRUTH_PATH,
    *,
    chunks: Sequence[Chunk] | None = None,
) -> dict[str, str]:
    """`question -> reference text` (the ground-truth chunk's own text).

    `chunks` lets a test supply a small fixture corpus instead of
    `load_corpus_chunks()`, which re-chunks the full 18-book snapshot — fine
    for a live run, unnecessarily slow for a unit test. A ground-truth row
    whose `chunk_id` is no longer in the corpus (drift) is silently absent
    from the returned mapping rather than raising — `score_answers` treats a
    missing lookup entry as "exclude this answer", the same corpus-drift
    handling `evals/retrieval_eval.py` uses.
    """
    rows = _load_ground_truth_rows(ground_truth_path)
    corpus_chunks = chunks if chunks is not None else load_corpus_chunks()
    text_by_chunk_id = {chunk.chunk_id: chunk.text for chunk in corpus_chunks}

    lookup: dict[str, str] = {}
    for row in rows:
        text = text_by_chunk_id.get(row.chunk_id)
        if text is not None:
            lookup[row.question] = text
    return lookup


# ── embedding + scoring ──────────────────────────────────────────────────────

_embedder: object | None = None


def _get_embedder() -> object:
    """Lazy singleton — mirrors `homelib_rag.index`'s embedder pattern.

    Imported lazily so importing this module (e.g. from a test that only
    exercises `load_answers`/`build_reference_lookup`) never pays for
    `sentence_transformers`.
    """
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(_EMBED_MODEL)
    return _embedder


def _default_embed(texts: Sequence[str]) -> NDArray[np.float64]:
    import numpy as np

    embedder = _get_embedder()
    vectors = embedder.encode(list(texts))  # type: ignore[attr-defined]
    return np.asarray(vectors, dtype=np.float64)


def _cosine(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    import numpy as np

    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def score_answers(
    answers: Sequence[SavedAnswer],
    reference_by_question: Mapping[str, str],
    *,
    embed: Embedder | None = None,
) -> list[AnswerSimilarityScore]:
    """Cosine-similarity-score every answer whose question has a reference.

    An answer whose `question` is not a key of `reference_by_question` is
    EXCLUDED, never scored as 0.0 — see the module docstring. Embeds all
    answer texts in one batch and all reference texts in another (rather
    than one call per case) so a real `SentenceTransformer` amortizes model
    overhead across the whole run.
    """
    embed_fn = embed if embed is not None else _default_embed
    scoreable = [a for a in answers if a.question in reference_by_question]
    if not scoreable:
        return []

    answer_vecs = embed_fn([a.answer for a in scoreable])
    reference_vecs = embed_fn([reference_by_question[a.question] for a in scoreable])

    return [
        AnswerSimilarityScore(
            question=case.question,
            variant=case.variant,
            similarity=_cosine(answer_vecs[i], reference_vecs[i]),
        )
        for i, case in enumerate(scoreable)
    ]


def summarize_by_variant(scores: Sequence[AnswerSimilarityScore]) -> list[VariantSimilarity]:
    """Mean/median similarity per variant, sorted by variant name."""
    by_variant: dict[str, list[float]] = {}
    for score in scores:
        by_variant.setdefault(score.variant, []).append(score.similarity)
    return [
        VariantSimilarity(
            variant=variant,
            n=len(values),
            mean_similarity=mean(values),
            median_similarity=median(values),
        )
        for variant, values in sorted(by_variant.items())
    ]


# ── report ───────────────────────────────────────────────────────────────────

_SIMILARITY_HEADING = "## Answer similarity (cosine)"


def _replace_or_append_section(text: str, heading: str, new_lines: Sequence[str]) -> str:
    """Replace the section starting at `heading` (up to the next `## `
    heading or EOF) with `new_lines`, or append it if `heading` is absent.
    Keeps every OTHER section of `text` untouched, so re-running this eval
    updates only its own table rather than duplicating it or clobbering the
    judge table above it. Same helper as `evals/retrieval_eval.py`'s "RRF k
    sweep" section — duplicated rather than imported so each eval module
    stays self-contained (see that module's docstring on why each keeps its
    own ground-truth loader for the same reason).
    """
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        prefix = lines
        if prefix and prefix[-1] != "":
            prefix = [*prefix, ""]
        return "\n".join([*prefix, *new_lines]) + "\n"

    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return "\n".join([*lines[:start], *new_lines, *lines[end:]]) + "\n"


def write_similarity_section(
    variant_scores: Sequence[VariantSimilarity], path: Path = REPORT_PATH
) -> None:
    """Upsert the "Answer similarity (cosine)" table into `path`.

    Raises `ValueError` on empty `variant_scores` — same "no data is a bug,
    not a blank section" rule `evals/retrieval_eval.py`'s report writers use.
    """
    if not variant_scores:
        raise ValueError("refusing to write an answer-similarity section with no scores")

    lines = [
        _SIMILARITY_HEADING,
        "",
        "Second LLM-eval method, judge-free: embeds each generated answer and "
        "its reference (the ground-truth chunk's own text) with "
        "`all-MiniLM-L6-v2` and scores cosine similarity between the two — "
        "cheap, deterministic, and independent of the judge table above, "
        "which it complements rather than replaces. Re-run: `uv run python "
        "evals/answer_similarity.py --answers <path>`.",
        "",
        "| variant | n | mean similarity | median similarity |",
        "| --- | ---: | ---: | ---: |",
    ]
    for score in variant_scores:
        lines.append(
            f"| `{score.variant}` | {score.n} | {score.mean_similarity:.3f} | "
            f"{score.median_similarity:.3f} |"
        )

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = _replace_or_append_section(existing, _SIMILARITY_HEADING, lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")


# ── entry point ──────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score saved answers by cosine similarity to their ground-truth chunk text."
    )
    parser.add_argument(
        "--answers",
        type=Path,
        required=True,
        help="JSON Lines file from `evals/llm_eval.py --save-answers`",
    )
    parser.add_argument(
        "--ground-truth",
        dest="ground_truth",
        type=Path,
        default=GROUND_TRUTH_PATH,
        help="ground-truth path (default: %(default)s)",
    )
    parser.add_argument(
        "--report", type=Path, default=REPORT_PATH, help="report path (default: %(default)s)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.answers.exists():
        print(f"✗ no answers file at {args.answers} — run `evals/llm_eval.py --save-answers` first")
        return 1
    answers = load_answers(args.answers)
    if not answers:
        print(f"✗ no answers loaded from {args.answers}; no report written")
        return 1

    reference_by_question = build_reference_lookup(args.ground_truth)
    scores = score_answers(answers, reference_by_question)
    if not scores:
        print(
            f"✗ none of the {len(answers)} saved answer(s) matched a ground-truth question "
            "with a live chunk; no report written"
        )
        return 1
    if len(scores) < len(answers):
        print(f"⚠ excluded {len(answers) - len(scores)} answer(s) with no matching ground truth")

    variant_scores = summarize_by_variant(scores)
    write_similarity_section(variant_scores, args.report)
    print(f"wrote answer-similarity section to {args.report}")
    print(json.dumps([vs.model_dump() for vs in variant_scores], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
