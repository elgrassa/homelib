"""Tests for evals/ground_truth.py — see specs/evals-retrieval.md.

No test in this module reaches a live LLM: `_call_llm` is monkeypatched
wherever generation is exercised, and `sample_chunks`/`build_ground_truth`/
`write_ground_truth` are monkeypatched in the `main()` test. The real
generation run that produced the committed `evals/ground_truth.jsonl` is a
separate, one-off invocation of `python -m evals.ground_truth`.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from homelib_core.chunk import chunk_book
from homelib_core.models import Block, BookDoc, Chunk, Provenance

from evals.ground_truth import (
    GROUND_TRUTH_PATH,
    GroundTruthRow,
    _clean_questions,
    _client,
    _is_self_referential,
    _is_substantial,
    _model_name,
    build_ground_truth,
    generate_questions,
    load_corpus_chunks,
    main,
    sample_chunks,
    write_ground_truth,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "data" / "corpus_snapshot.jsonl.gz"

_MIN_QUESTION_CHARS = 20


def _make_book(book_id: str, n_sentences: int = 120) -> BookDoc:
    """A tiny synthetic book with enough sentence-delimited text for a few
    substantial chunks, so sampling/filtering tests never touch the real
    corpus snapshot."""
    template = (
        "Sentence number {i} of this synthetic passage exists purely to give "
        "the chunker enough substantial, sentence-delimited text to work "
        "with when building deterministic fixtures for unit tests. "
    )
    text = "".join(template.format(i=i) for i in range(n_sentences))
    block = Block(
        block_id=f"{book_id}-b0",
        book_id=book_id,
        ordinal=0,
        section_path=["Chapter 1"],
        text=text,
        char_start=0,
        char_end=len(text),
        provenance=Provenance(format="txt", source_sha256="0" * 64),
    )
    return BookDoc(
        book_id=book_id,
        title=book_id,
        authors=["Test Author"],
        language="en",
        source_url="https://example.invalid",
        license_note="public domain",
        blocks=[block],
        canonical_text=text,
    )


def _fake_chunk(book_id: str, idx: int, *, text: str | None = None) -> Chunk:
    """A minimal, directly-constructed `Chunk` for tests that don't need a
    real `BookDoc`/`chunk_book` round trip — just something long enough to
    clear `_is_substantial`'s length floor."""
    body = text if text is not None else "x" * 450
    return Chunk(
        chunk_id=f"{book_id}-{idx}",
        book_id=book_id,
        block_ids=[f"{book_id}-blk"],
        section_path=["C"],
        text=body,
        char_start=0,
        char_end=len(body),
    )


@pytest.fixture
def fixture_chunks() -> list[Chunk]:
    books = [_make_book(f"book-{i}") for i in range(4)]
    chunks: list[Chunk] = []
    for book in books:
        # target_chars=850 packs ~4 of the ~188-char template sentences per
        # chunk (~750 chars), comfortably clearing the 400-char substance
        # floor in evals.ground_truth._is_substantial.
        chunks.extend(chunk_book(book, target_chars=850, overlap=150))
    return chunks


# ── load_corpus_chunks ───────────────────────────────────────────────────


def test_load_corpus_chunks_skips_blank_lines(tmp_path: Path) -> None:
    book = _make_book("blank-book", n_sentences=10)
    path = tmp_path / "mini.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("\n")  # blank line: must be skipped, not raise
        f.write(book.model_dump_json() + "\n")
        f.write("   \n")  # whitespace-only line: also skipped

    chunks = load_corpus_chunks(path)

    assert chunks
    assert all(c.book_id == "blank-book" for c in chunks)


# ── _is_substantial ──────────────────────────────────────────────────────


def test_is_substantial_rejects_toc_like_text() -> None:
    toc_text = "\n".join(f"Chapter {i}" for i in range(60))
    assert len(toc_text) >= 400  # clears the length floor alone
    chunk = _fake_chunk("book-toc", 0, text=toc_text)

    assert _is_substantial(chunk) is False


def test_is_substantial_accepts_long_single_paragraph() -> None:
    assert _is_substantial(_fake_chunk("book-x", 0)) is True


def test_is_substantial_rejects_short_text() -> None:
    assert _is_substantial(_fake_chunk("book-y", 0, text="Too short.")) is False


# ── sample_chunks ────────────────────────────────────────────────────────


def test_sampling_is_deterministic(fixture_chunks: list[Chunk]) -> None:
    first = sample_chunks(10, seed=42, chunks=fixture_chunks)
    second = sample_chunks(10, seed=42, chunks=fixture_chunks)

    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert len(first) == 10


def test_sampling_spreads_across_books(fixture_chunks: list[Chunk]) -> None:
    picks = sample_chunks(8, seed=0, chunks=fixture_chunks)

    assert len({c.book_id for c in picks}) == 4  # all 4 fixture books represented


def test_sampling_different_seed_can_differ(fixture_chunks: list[Chunk]) -> None:
    a = sample_chunks(10, seed=1, chunks=fixture_chunks)
    b = sample_chunks(10, seed=2, chunks=fixture_chunks)

    assert [c.chunk_id for c in a] != [c.chunk_id for c in b]


def test_sampling_skips_short_chunks() -> None:
    tiny_block = Block(
        block_id="tiny-b0",
        book_id="tiny",
        ordinal=0,
        section_path=["C"],
        text="Too short.",
        char_start=0,
        char_end=10,
        provenance=Provenance(format="txt", source_sha256="1" * 64),
    )
    tiny_doc = BookDoc(
        book_id="tiny",
        title="tiny",
        authors=[],
        language="en",
        source_url="https://example.invalid",
        license_note="pd",
        blocks=[tiny_block],
        canonical_text="Too short.",
    )
    chunks = chunk_book(tiny_doc)

    assert sample_chunks(5, seed=0, chunks=chunks) == []


def test_sampling_with_no_chunks_returns_empty() -> None:
    assert sample_chunks(5, seed=0, chunks=[]) == []


def test_sampling_reuses_and_skips_already_exhausted_books() -> None:
    # book-a has only 2 substantial chunks, book-b has 5; asking for 6 forces
    # the round-robin loop to both exhaust book-a mid-run *and* skip past it
    # on a later lap once it is already marked exhausted.
    chunks = [_fake_chunk("book-a", i) for i in range(2)] + [
        _fake_chunk("book-b", i) for i in range(5)
    ]

    picks = sample_chunks(6, seed=0, chunks=chunks)

    assert len(picks) == 6
    assert sum(1 for c in picks if c.book_id == "book-a") == 2
    assert sum(1 for c in picks if c.book_id == "book-b") == 4


# ── generate_questions (LLM stubbed) ────────────────────────────────────


def test_generate_questions_filters_short_duplicate_and_echoing(
    monkeypatch: pytest.MonkeyPatch, fixture_chunks: list[Chunk]
) -> None:
    chunk = fixture_chunks[0]
    raw = json.dumps(
        {
            "questions": [
                "Short?",
                "Hi?",
                "How many sentences reference the number forty in this synthetic passage?",
                "How many sentences reference the number forty in this synthetic passage?",
                "Sentence number 0 of this synthetic passage exists purely?",
            ]
        }
    )
    monkeypatch.setattr("evals.ground_truth._call_llm", lambda text, n: raw)

    questions = generate_questions(chunk, n=5)

    assert questions == ["How many sentences reference the number forty in this synthetic passage?"]


def test_generate_questions_returns_empty_on_malformed_json(
    monkeypatch: pytest.MonkeyPatch, fixture_chunks: list[Chunk]
) -> None:
    chunk = fixture_chunks[0]
    monkeypatch.setattr("evals.ground_truth._call_llm", lambda text, n: "not json at all")

    assert generate_questions(chunk, n=5) == []


def test_generate_questions_returns_empty_on_transport_failure(
    monkeypatch: pytest.MonkeyPatch, fixture_chunks: list[Chunk]
) -> None:
    chunk = fixture_chunks[0]

    def _boom(text: str, n: int) -> str:
        raise RuntimeError("connection refused")

    monkeypatch.setattr("evals.ground_truth._call_llm", _boom)

    assert generate_questions(chunk, n=5) == []


def test_generate_questions_caps_at_n(
    monkeypatch: pytest.MonkeyPatch, fixture_chunks: list[Chunk]
) -> None:
    chunk = fixture_chunks[0]
    candidates = [f"Distinct specific question number {i} about the passage?" for i in range(9)]
    raw = json.dumps({"questions": candidates})
    monkeypatch.setattr("evals.ground_truth._call_llm", lambda text, n: raw)

    assert len(generate_questions(chunk, n=3)) == 3


def test_clean_questions_drops_candidates_without_question_mark() -> None:
    chunk_text = "Something entirely different opens this passage for testing purposes."
    candidates = ["This is a long enough statement without any question mark at all in it"]

    assert _clean_questions(candidates, chunk_text, n=3) == []


# ── _client / _model_name ────────────────────────────────────────────────


def test_model_name_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "custom-model")

    assert _model_name() == "custom-model"


def test_model_name_defaults_without_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_MODEL", raising=False)

    assert _model_name() == "qwen2.5:7b-instruct"


def test_client_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://example.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    client = _client()

    assert "example.invalid" in str(client.base_url)
    assert client.api_key == "test-key"


# ── build_ground_truth / write_ground_truth ─────────────────────────────


def test_build_ground_truth_never_reaches_a_real_llm(
    monkeypatch: pytest.MonkeyPatch, fixture_chunks: list[Chunk]
) -> None:
    calls = {"n": 0}

    def _fake_call_llm(text: str, n: int) -> str:
        calls["n"] += 1
        return json.dumps(
            {"questions": [f"Question {calls['n']}-{i} about the passage?" for i in range(n)]}
        )

    monkeypatch.setattr("evals.ground_truth._call_llm", _fake_call_llm)

    rows = build_ground_truth(fixture_chunks[:3], questions_per_chunk=2)

    assert len(rows) == 6
    assert all(isinstance(r, GroundTruthRow) for r in rows)
    assert len({r.question for r in rows}) == len(rows)  # globally deduped
    assert calls["n"] == 3  # one call per chunk, no retries needed


def test_build_ground_truth_retry_appends_a_genuinely_new_question(
    monkeypatch: pytest.MonkeyPatch, fixture_chunks: list[Chunk]
) -> None:
    calls = {"n": 0}

    def _fake_call_llm(text: str, n: int) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            questions = [
                "First initial specific question about the passage?",
                "Second initial specific question about the passage?",
            ]
        else:
            questions = [
                "First initial specific question about the passage?",  # dup, dropped
                "Brand new question surfaced only on the retry call?",
            ]
        return json.dumps({"questions": questions})

    monkeypatch.setattr("evals.ground_truth._call_llm", _fake_call_llm)

    rows = build_ground_truth(fixture_chunks[:1], questions_per_chunk=3)

    assert {r.question for r in rows} == {
        "First initial specific question about the passage?",
        "Second initial specific question about the passage?",
        "Brand new question surfaced only on the retry call?",
    }
    assert calls["n"] == 2  # the initial call plus exactly one retry


def test_build_ground_truth_warns_and_dedupes_when_llm_repeats_itself(
    monkeypatch: pytest.MonkeyPatch, fixture_chunks: list[Chunk], caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "evals.ground_truth._call_llm",
        lambda text, n: json.dumps(
            {"questions": ["Repeated identical question about the text?"] * n}
        ),
    )

    with caplog.at_level("WARNING"):
        rows = build_ground_truth(fixture_chunks[:3], questions_per_chunk=3)

    # every chunk's batch collapses to one usable question, and every chunk
    # offers the *same* normalized question -> only the very first survives.
    assert len(rows) == 1
    assert any("usable questions after retry" in msg for msg in caplog.messages)


def test_write_ground_truth_round_trips(tmp_path: Path) -> None:
    rows = [
        GroundTruthRow(
            question="What happened at the start of chapter one?",
            chunk_id="abc123",
            book_id="book-a",
        ),
        GroundTruthRow(
            question="Who founded the organization described here?",
            chunk_id="def456",
            book_id="book-b",
        ),
    ]
    out = tmp_path / "gt.jsonl"

    write_ground_truth(rows, out)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    loaded = [json.loads(line) for line in lines]
    assert loaded[0] == {
        "question": "What happened at the start of chapter one?",
        "chunk_id": "abc123",
        "book_id": "book-a",
    }


# ── main() (fully stubbed pipeline) ─────────────────────────────────────


def test_main_uses_stubbed_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_chunk = Chunk(
        chunk_id="c1",
        book_id="b1",
        block_ids=["blk"],
        section_path=["C"],
        text="x" * 500,
        char_start=0,
        char_end=500,
    )
    fake_row = GroundTruthRow(
        question="What does this fixture chunk stand in for?", chunk_id="c1", book_id="b1"
    )
    out_path = tmp_path / "gt.jsonl"

    monkeypatch.setattr("evals.ground_truth.sample_chunks", lambda n, seed=0: [fake_chunk])
    monkeypatch.setattr("evals.ground_truth.build_ground_truth", lambda chunks: [fake_row])
    monkeypatch.setattr("evals.ground_truth.GROUND_TRUTH_PATH", out_path)

    exit_code = main()

    assert exit_code == 0
    assert out_path.exists()
    assert "wrote 1 ground-truth pairs" in capsys.readouterr().out


# ── the committed evals/ground_truth.jsonl itself ───────────────────────


def _load_committed_rows() -> list[dict[str, str]]:
    with GROUND_TRUTH_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_ground_truth_rows_reference_real_chunks() -> None:
    """Every committed `chunk_id` must exist in the real corpus — ground
    truth pointing at chunks that do not exist would make every retrieval
    arm look equally (and misleadingly) bad."""
    rows = _load_committed_rows()
    assert rows, "evals/ground_truth.jsonl is empty"

    real_chunk_ids = {c.chunk_id for c in load_corpus_chunks(SNAPSHOT_PATH)}
    missing = [r["chunk_id"] for r in rows if r["chunk_id"] not in real_chunk_ids]

    assert not missing, f"{len(missing)} ground-truth rows reference nonexistent chunk ids"


def test_ground_truth_questions_are_specific() -> None:
    rows = _load_committed_rows()
    assert rows

    too_short = [r["question"] for r in rows if len(r["question"]) < _MIN_QUESTION_CHARS]
    assert not too_short, f"{len(too_short)} questions shorter than {_MIN_QUESTION_CHARS} chars"

    questions = [r["question"] for r in rows]
    assert len(questions) == len(set(questions)), "duplicate questions in committed ground truth"


def test_ground_truth_row_count_within_spec_target() -> None:
    rows = _load_committed_rows()

    assert 150 <= len(rows) <= 250, f"expected 150-250 pairs, got {len(rows)}"


def test_ground_truth_covers_most_books() -> None:
    rows = _load_committed_rows()

    # 18 books total; require broad coverage rather than every single one so
    # a couple of small/degraded books don't make this test brittle.
    assert len({r["book_id"] for r in rows}) >= 10


def test_questions_are_not_self_referential() -> None:
    """Ground truth must not point at "the passage" instead of its subject.

    Retrieval is handed the question alone. "What causes wrinkles according to
    the passage?" says nothing about WHICH passage, so it depresses every arm
    equally — noise in the measurement wearing the costume of difficulty.

    The first generated batch was 40% such questions; the prompt now forbids
    them and _clean_questions rejects any the model emits anyway.
    """
    rows = [json.loads(line) for line in GROUND_TRUTH_PATH.read_text().splitlines() if line]
    offenders = [r["question"] for r in rows if _is_self_referential(r["question"])]
    ratio = len(offenders) / len(rows)
    assert ratio <= 0.02, (
        f"{len(offenders)}/{len(rows)} ({ratio:.0%}) questions refer to their own "
        f"passage; e.g. {offenders[:3]}"
    )


def test_self_referential_detector_catches_real_examples() -> None:
    """Pin the detector to the exact phrasings observed in the first batch."""
    assert _is_self_referential("What causes wrinkles according to the passage?")
    assert _is_self_referential("How does age correlate with expression according to the text?")
    assert _is_self_referential("What does the passage imply about a philosopher?")
    # ...and does not fire on questions that merely mention an author by name.
    assert not _is_self_referential("What did Franklin say about industry and frugality?")
    assert not _is_self_referential("How does Taylor define a fair day's work?")
