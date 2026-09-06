"""Tests for evals/answer_similarity.py — the cosine-similarity LLM eval.

Every test here runs with NO model download: `score_answers`'s `embed` seam
is replaced with `_toy_embed`, a tiny deterministic hash-based embedding that
guarantees identical strings map to identical vectors (cosine similarity
exactly 1.0) without ever importing `sentence_transformers`. The one thing
this file cannot fake is `evals/llm_eval.py --save-answers` itself — that is
a separate, live invocation (see docs/handoffs and evals/results/llm_eval.md
for whether one has been run).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from homelib_core.models import Chunk

from evals.answer_similarity import (
    SavedAnswer,
    VariantSimilarity,
    build_reference_lookup,
    load_answers,
    score_answers,
    summarize_by_variant,
    write_similarity_section,
)


def _toy_embed(texts: list[str]) -> np.ndarray:
    """Deterministic, hash-based fake embedding — no model download.

    Not semantically meaningful; it only guarantees identical strings embed
    to identical vectors (so cosine similarity is exactly 1.0) and that
    different strings very likely embed to different vectors — enough to
    exercise `score_answers`/`_cosine` without a real model.
    """
    dim = 16
    vectors = np.zeros((len(texts), dim), dtype=np.float64)
    for row, text in enumerate(texts):
        for position, char in enumerate(text):
            vectors[row, position % dim] += ord(char)
    return vectors


def _chunk(chunk_id: str, book_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        book_id=book_id,
        block_ids=["b1"],
        section_path=["ch1"],
        text=text,
        char_start=0,
        char_end=len(text),
    )


# ── scoring ──────────────────────────────────────────────────────────────────


def test_answer_similarity_scores_identical_text_as_one() -> None:
    answers = [SavedAnswer(question="q1", variant="concise", answer="The sky is blue.")]
    reference = {"q1": "The sky is blue."}

    scores = score_answers(answers, reference, embed=_toy_embed)

    assert len(scores) == 1
    assert scores[0].question == "q1"
    assert scores[0].variant == "concise"
    assert scores[0].similarity == pytest.approx(1.0)


def test_answer_similarity_scores_unrelated_text_below_one() -> None:
    answers = [SavedAnswer(question="q1", variant="concise", answer="zzz")]
    reference = {"q1": "The quick brown fox jumps over the lazy dog."}

    scores = score_answers(answers, reference, embed=_toy_embed)

    assert scores[0].similarity < 1.0


def test_answer_similarity_excludes_answers_with_no_matching_reference() -> None:
    # "unknown question" never appears in the ground truth (e.g. corpus
    # drift, or a typo) -- excluded, not scored as 0.0.
    answers = [
        SavedAnswer(question="known", variant="concise", answer="a"),
        SavedAnswer(question="unknown question", variant="concise", answer="b"),
    ]
    reference = {"known": "a"}

    scores = score_answers(answers, reference, embed=_toy_embed)

    assert len(scores) == 1
    assert scores[0].question == "known"


def test_answer_similarity_raises_nothing_on_all_excluded() -> None:
    # Every question misses the reference lookup -> empty list, not an error.
    answers = [SavedAnswer(question="q1", variant="concise", answer="a")]

    scores = score_answers(answers, {}, embed=_toy_embed)

    assert scores == []


def test_summarize_by_variant_computes_mean_and_median() -> None:
    answers = [
        SavedAnswer(question="q1", variant="concise", answer="The sky is blue."),
        SavedAnswer(question="q2", variant="concise", answer="zzz"),
    ]
    reference = {"q1": "The sky is blue.", "q2": "The sky is blue."}

    scores = score_answers(answers, reference, embed=_toy_embed)
    summary = summarize_by_variant(scores)

    assert len(summary) == 1
    assert summary[0].variant == "concise"
    assert summary[0].n == 2
    assert summary[0].mean_similarity == pytest.approx(
        (scores[0].similarity + scores[1].similarity) / 2
    )


def test_summarize_by_variant_keeps_variants_separate() -> None:
    answers = [
        SavedAnswer(question="q1", variant="concise", answer="The sky is blue."),
        SavedAnswer(question="q1", variant="stepwise", answer="The sky is blue."),
    ]
    reference = {"q1": "The sky is blue."}

    scores = score_answers(answers, reference, embed=_toy_embed)
    summary = {vs.variant: vs for vs in summarize_by_variant(scores)}

    assert set(summary) == {"concise", "stepwise"}
    assert summary["concise"].n == 1
    assert summary["stepwise"].n == 1


# ── loading ──────────────────────────────────────────────────────────────────


def test_load_answers_reads_jsonl_and_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "answers.jsonl"
    rows = [
        {"question": "q1", "variant": "concise", "answer": "a1"},
        {"question": "q2", "variant": "stepwise", "answer": "a2", "citations": [], "extra": 1},
    ]
    path.write_text(f"\n{json.dumps(rows[0])}\n\n{json.dumps(rows[1])}\n", encoding="utf-8")

    answers = load_answers(path)

    assert [a.question for a in answers] == ["q1", "q2"]
    assert [a.variant for a in answers] == ["concise", "stepwise"]
    assert [a.answer for a in answers] == ["a1", "a2"]


def test_build_reference_lookup_maps_question_to_chunk_text(tmp_path: Path) -> None:
    gt_path = tmp_path / "ground_truth.jsonl"
    gt_path.write_text(
        json.dumps({"question": "what colour is the sky?", "chunk_id": "c1", "book_id": "b1"})
        + "\n",
        encoding="utf-8",
    )
    chunks = [_chunk("c1", "b1", "The sky is blue on a clear day.")]

    lookup = build_reference_lookup(gt_path, chunks=chunks)

    assert lookup == {"what colour is the sky?": "The sky is blue on a clear day."}


def test_build_reference_lookup_drops_rows_with_drifted_chunk_ids(tmp_path: Path) -> None:
    # "c-gone" is not in the fixture corpus -- corpus drift. The row is
    # silently absent from the lookup (score_answers treats that as
    # "exclude"), never mapped to an empty/wrong string.
    gt_path = tmp_path / "ground_truth.jsonl"
    gt_path.write_text(
        json.dumps({"question": "missing?", "chunk_id": "c-gone", "book_id": "b1"}) + "\n",
        encoding="utf-8",
    )

    lookup = build_reference_lookup(gt_path, chunks=[_chunk("c1", "b1", "irrelevant text")])

    assert lookup == {}


# ── report ───────────────────────────────────────────────────────────────────


def _sim(variant: str, mean: float, median: float, n: int = 10) -> VariantSimilarity:
    return VariantSimilarity(variant=variant, n=n, mean_similarity=mean, median_similarity=median)


def test_write_similarity_section_appends_to_an_existing_report(tmp_path: Path) -> None:
    path = tmp_path / "llm_eval.md"
    path.write_text(
        "# LLM prompt-variant eval\n\n| variant | n |\n| --- | --- |\n", encoding="utf-8"
    )

    write_similarity_section([_sim("concise", 0.5, 0.5)], path)
    text = path.read_text(encoding="utf-8")

    assert "## Answer similarity (cosine)" in text
    assert "| `concise` | 10 | 0.500 | 0.500 |" in text
    assert "# LLM prompt-variant eval" in text  # the original report survives


def test_write_similarity_section_replaces_not_duplicates_on_rerun(tmp_path: Path) -> None:
    path = tmp_path / "llm_eval.md"
    path.write_text("# LLM prompt-variant eval\n\nsome other content\n", encoding="utf-8")

    write_similarity_section([_sim("concise", 0.5, 0.5)], path)
    write_similarity_section([_sim("concise", 0.9, 0.9)], path)
    text = path.read_text(encoding="utf-8")

    assert text.count("## Answer similarity (cosine)") == 1
    assert "| `concise` | 10 | 0.900 | 0.900 |" in text
    assert "0.500" not in text
    assert "some other content" in text


def test_write_similarity_section_refuses_empty_scores(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no scores"):
        write_similarity_section([], tmp_path / "llm_eval.md")
