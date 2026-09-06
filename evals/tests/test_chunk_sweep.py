"""Tests for evals/chunk_sweep.py — the target_chars/overlap experiment.

Every test here runs against a tiny synthetic `BookDoc` corpus (never the
committed 18-book snapshot) with a faked, deterministic embedder (`_toy_embed`,
same hash-based approach as `evals/tests/test_answer_similarity.py`'s), so
nothing here downloads a model or reads `data/corpus_snapshot.jsonl.gz`. The
lexical arm's `:memory:` FTS5 table is real SQLite (stdlib, no fixture
needed).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from homelib_core.models import Block, BookDoc, Provenance

from evals.chunk_sweep import (
    ChunkConfigResult,
    build_lexical_index,
    build_vector_index,
    chunk_corpus,
    filter_rows_to_available_books,
    lexical_search,
    run_chunk_sweep,
    score_config,
    vector_search,
    whole_section_token_baseline,
    write_report,
)
from evals.ground_truth import GroundTruthRow


def _toy_embed(texts: list[str]) -> np.ndarray:
    """Deterministic, hash-based fake embedding — no model download.

    Not semantically meaningful; guarantees identical strings embed to
    identical vectors and that texts sharing more words embed closer
    together than texts sharing none, via per-word hashing into a fixed-dim
    bag-of-words vector — enough to exercise ranking without a real model.
    """
    dim = 32
    vectors = np.zeros((len(texts), dim), dtype=np.float64)
    for row, text in enumerate(texts):
        for word in text.lower().split():
            vectors[row, hash(word) % dim] += 1.0
    return vectors


def _provenance() -> Provenance:
    return Provenance(format="txt", page=None, spine_index=0, anchor=None, source_sha256="a" * 64)


def _build_doc(book_id: str, chapters: list[list[str]]) -> BookDoc:
    """A `BookDoc` from `chapters`: a list of chapters, each a list of block
    texts. Chapter N gets `section_path=["Chapter N"]`; `canonical_text` is
    the exact concatenation of every block's text, in order, so block
    offsets are contiguous by construction — same fixture-building pattern
    as `packages/homelib-core/tests/test_chunk.py`.
    """
    blocks: list[Block] = []
    canonical_text = ""
    ordinal = 0
    for chapter_idx, block_texts in enumerate(chapters, start=1):
        section_path = [f"Chapter {chapter_idx}"]
        for text in block_texts:
            char_start = len(canonical_text)
            canonical_text += text
            blocks.append(
                Block(
                    block_id=f"{book_id}-b{ordinal}",
                    book_id=book_id,
                    ordinal=ordinal,
                    section_path=section_path,
                    text=text,
                    char_start=char_start,
                    char_end=char_start + len(text),
                    provenance=_provenance(),
                )
            )
            ordinal += 1
    return BookDoc(
        book_id=book_id,
        title=f"Test Book {book_id}",
        authors=["A.Uthor"],
        language="en",
        source_url="https://example.org/test-book",
        license_note="public domain",
        blocks=blocks,
        canonical_text=canonical_text,
    )


def _sentence(n: int, topic: str) -> str:
    return f"This sentence discusses {topic} in some detail with extra words. "


def _corpus() -> list[BookDoc]:
    # Two books, two chapters each, with distinct vocabulary per book so a
    # lexical/vector search can tell them apart.
    apples_book = _build_doc(
        "apples-book",
        chapters=[
            [_sentence(i, "apples orchards harvest") * 6 for i in range(3)],
            [_sentence(i, "cider pressing apples") * 6 for i in range(3)],
        ],
    )
    trains_book = _build_doc(
        "trains-book",
        chapters=[
            [_sentence(i, "steam locomotives railways") * 6 for i in range(3)],
            [_sentence(i, "signals tracks trains") * 6 for i in range(3)],
        ],
    )
    return [apples_book, trains_book]


def _rows() -> list[GroundTruthRow]:
    return [
        GroundTruthRow(
            question="apples orchards harvest", chunk_id="ignored", book_id="apples-book"
        ),
        GroundTruthRow(
            question="steam locomotives railways", chunk_id="ignored", book_id="trains-book"
        ),
    ]


# ── chunking + tokens ────────────────────────────────────────────────────────


def test_chunk_corpus_produces_more_smaller_chunks_at_a_smaller_target() -> None:
    docs = _corpus()

    small = chunk_corpus(docs, target_chars=100, overlap=20)
    large = chunk_corpus(docs, target_chars=2000, overlap=400)

    assert len(small) >= len(large)
    assert all(chunk.book_id in {"apples-book", "trains-book"} for chunk in small)


def test_whole_section_token_baseline_is_positive_and_book_independent_of_chunking() -> None:
    docs = _corpus()
    baseline = whole_section_token_baseline(docs)

    assert baseline > 0
    # Re-chunking (a downstream, separate call) never changes the BookDoc's
    # own blocks/section_path, so the baseline is identical either way.
    chunk_corpus(docs, target_chars=100, overlap=20)
    assert whole_section_token_baseline(docs) == pytest.approx(baseline)


# ── lexical arm ──────────────────────────────────────────────────────────────


def test_lexical_search_finds_the_book_matching_the_query_vocabulary() -> None:
    docs = _corpus()
    chunks = chunk_corpus(docs, target_chars=1200, overlap=200)
    conn = build_lexical_index(chunks)
    try:
        hits = lexical_search(conn, "apples orchards harvest", k=5)
    finally:
        conn.close()

    assert hits
    assert all(book_id == "apples-book" for _chunk_id, book_id in hits)


# ── vector arm ───────────────────────────────────────────────────────────────


def test_vector_search_ranks_the_matching_book_first() -> None:
    docs = _corpus()
    chunks = chunk_corpus(docs, target_chars=1200, overlap=200)
    index = build_vector_index(chunks, embed=_toy_embed)
    (query_vec,) = _toy_embed(["steam locomotives railways"])

    hits = vector_search(index, query_vec, k=3)

    assert hits
    assert hits[0][1] == "trains-book"


# ── end-to-end scoring: the named test the task brief requires ─────────────


def test_chunk_sweep_reports_tokens_and_mrr_per_config() -> None:
    """One config, both books findable, book-level hit-rate/MRR both perfect
    (each question's book is the only one that shares its vocabulary), and
    `mean_tokens_top5` is a positive, finite number — the shape
    `write_report` needs. No model download: `_toy_embed` throughout.
    """
    docs = _corpus()
    rows = _rows()

    result = score_config(docs, rows, target_chars=1200, overlap=200, k=5, embed=_toy_embed)

    assert isinstance(result, ChunkConfigResult)
    assert result.target_chars == 1200
    assert result.overlap == 200
    assert result.n_questions == 2
    assert result.n_chunks > 0
    assert result.vector_hit_rate_book_at_5 == pytest.approx(1.0)
    assert result.vector_mrr_book_at_5 == pytest.approx(1.0)
    assert result.lexical_hit_rate_book_at_5 == pytest.approx(1.0)
    assert result.mean_tokens_top5 > 0


def test_run_chunk_sweep_scores_every_config_in_order() -> None:
    docs = _corpus()
    rows = _rows()
    configs = [(600, 100), (1200, 200), (2000, 400)]

    results = run_chunk_sweep(docs, rows, configs=configs, embed=_toy_embed)

    assert [(r.target_chars, r.overlap) for r in results] == configs
    assert all(r.n_questions == 2 for r in results)


# ── report ───────────────────────────────────────────────────────────────────


def _result(target_chars: int, overlap: int, hit_rate: float) -> ChunkConfigResult:
    return ChunkConfigResult(
        target_chars=target_chars,
        overlap=overlap,
        n_chunks=10,
        n_questions=2,
        lexical_hit_rate_book_at_5=hit_rate,
        lexical_mrr_book_at_5=hit_rate,
        vector_hit_rate_book_at_5=hit_rate,
        vector_mrr_book_at_5=hit_rate,
        mean_tokens_top5=500.0,
    )


def test_write_report_includes_every_config_and_a_conclusion(tmp_path: Path) -> None:
    path = tmp_path / "chunking.md"
    results = [
        _result(600, 100, 0.5),
        _result(1200, 200, 0.8),
        _result(2000, 400, 0.6),
    ]

    write_report(
        results,
        whole_section_tokens=3000.0,
        path=path,
        question_budget=2,
        n_books_used=18,
        n_books_total=18,
    )
    text = path.read_text(encoding="utf-8")

    assert "600/100" in text
    assert "1200/200" in text
    assert "2000/400" in text
    assert "**Conclusion:**" in text
    assert "1200/200" in text.split("**Conclusion:**")[1]  # the best config is named
    assert "3000" in text


def test_write_report_notes_a_book_subset_when_books_is_capped(tmp_path: Path) -> None:
    path = tmp_path / "chunking.md"
    results = [_result(1200, 200, 0.8)]

    write_report(
        results,
        whole_section_tokens=100.0,
        path=path,
        question_budget=None,
        n_books_used=6,
        n_books_total=18,
        rows_dropped_book_not_in_subset=3,
    )
    text = path.read_text(encoding="utf-8")

    assert "6/18 book(s)" in text
    assert "3 row(s) dropped" in text


def test_write_report_refuses_empty_results(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no configs scored"):
        write_report(
            [],
            whole_section_tokens=100.0,
            path=tmp_path / "chunking.md",
            question_budget=None,
            n_books_used=18,
            n_books_total=18,
        )


def test_filter_rows_to_available_books_drops_rows_whose_book_is_excluded() -> None:
    docs = _corpus()  # apples-book, trains-book
    rows = [
        *_rows(),
        GroundTruthRow(question="unrelated?", chunk_id="ignored", book_id="excluded-book"),
    ]

    kept, dropped = filter_rows_to_available_books(rows, docs[:1])  # only apples-book kept

    assert dropped == 2
    assert [row.book_id for row in kept] == ["apples-book"]
