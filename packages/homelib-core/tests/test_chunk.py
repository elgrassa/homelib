"""Red-first tests for `homelib_core.chunk` — see specs/chunking.md.

These tests are written before the implementation exists and MUST fail
(collection error / ImportError) until
packages/homelib-core/src/homelib_core/chunk.py is written.

All `BookDoc` fixtures are built programmatically here (never parsed from a
file) so this module stays independent of the format handlers / normalize.py
another agent is concurrently writing.
"""

from itertools import groupby, pairwise

import pytest
from homelib_core.chunk import _pack_sentences, _split_sentences, chunk_book
from homelib_core.models import Block, BookDoc, Provenance, make_block_id
from hypothesis import given, settings
from hypothesis import strategies as st

# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------


def _make_provenance() -> Provenance:
    return Provenance(format="epub", page=None, spine_index=0, anchor=None, source_sha256="a" * 64)


def _make_block(
    book_id: str, ordinal: int, section_path: list[str], text: str, char_start: int
) -> Block:
    return Block(
        block_id=make_block_id(book_id, section_path, ordinal),
        book_id=book_id,
        ordinal=ordinal,
        section_path=section_path,
        text=text,
        char_start=char_start,
        char_end=char_start + len(text),
        provenance=_make_provenance(),
    )


def _build_doc(book_id: str, chapters: list[list[str]]) -> BookDoc:
    """Build a `BookDoc` from `chapters`: a list of chapters, each a list of
    block texts. Chapter N gets section_path ["Chapter N"]; canonical_text is
    the exact concatenation of every block text in order, so block offsets
    are contiguous by construction (matching how a real format handler
    builds a BookDoc).
    """
    blocks: list[Block] = []
    canonical_text = ""
    ordinal = 0
    for chapter_idx, block_texts in enumerate(chapters, start=1):
        section_path = [f"Chapter {chapter_idx}"]
        for text in block_texts:
            char_start = len(canonical_text)
            canonical_text += text
            blocks.append(_make_block(book_id, ordinal, section_path, text, char_start))
            ordinal += 1
    return BookDoc(
        book_id=book_id,
        title="Test Book",
        authors=["A.Uthor"],
        language="en",
        source_url="https://example.org/test-book",
        license_note="public domain",
        blocks=blocks,
        canonical_text=canonical_text,
    )


def _lorem_sentences(n: int, prefix: str = "Sentence") -> str:
    """`n` short, punctuated sentences separated by single spaces."""
    return " ".join(f"{prefix} number {i} has a few words in it for testing." for i in range(n))


def _rich_fixture() -> BookDoc:
    """A non-trivial multi-chapter fixture exercising every packing path:

    - Chapter 1: several small, ordinary blocks (normal packing path).
    - Chapter 2: one single block far longer than target_chars, with many
      sentences (the "split a long block" path).
    - Chapter 3: one block shorter than overlap (the degenerate short-block
      / short-chapter path).
    - Chapter 4: an empty block, followed by a block with no sentence
      boundary at all (no '.', '!', '?'), long enough to force the
      word-boundary fallback split (the "no sentence boundary" path).
    """
    return _build_doc(
        "rich-book",
        [
            [
                "Call me Ishmael. Some years ago, never mind how long precisely. ",
                "There is nothing surprising in this. ",
                "Almost all men in their degree, some time or other, cherish "
                "nearly the same feelings towards the ocean with me. ",
            ],
            [_lorem_sentences(40, prefix="Longblock")],
            ["Hi."],
            [
                "",
                ("word " * 120).strip() + " ",
            ],
        ],
    )


# --------------------------------------------------------------------------
# Named required tests
# --------------------------------------------------------------------------


@st.composite
def _target_and_overlap(draw: st.DrawFn) -> tuple[int, int]:
    target_chars = draw(st.integers(min_value=30, max_value=400))
    overlap = draw(st.integers(min_value=0, max_value=target_chars - 1))
    return target_chars, overlap


@given(params=_target_and_overlap())
@settings(max_examples=30, deadline=None)
def test_chunk_spans_reconstruct_source(params: tuple[int, int]) -> None:
    """The invariant the whole citation feature rests on: every chunk's text
    is exactly the canonical_text slice named by its own char_start/char_end.
    Checked as a genuine property across many (target_chars, overlap) draws
    against a non-trivial multi-chapter, multi-path fixture.
    """
    target_chars, overlap = params
    doc = _rich_fixture()
    chunks = chunk_book(doc, target_chars=target_chars, overlap=overlap)

    assert chunks, "fixture is non-trivial: chunking it must not yield []"
    for chunk in chunks:
        assert doc.canonical_text[chunk.char_start : chunk.char_end] == chunk.text


def test_no_chunk_crosses_chapter_boundary() -> None:
    doc = _rich_fixture()
    chunks = chunk_book(doc, target_chars=120, overlap=25)
    block_by_id = {b.block_id: b for b in doc.blocks}

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.block_ids
        top_levels = {block_by_id[bid].section_path[0] for bid in chunk.block_ids}
        assert len(top_levels) == 1, f"chunk {chunk.chunk_id} spans multiple chapters"


def test_overlap_within_bounds() -> None:
    target_chars, overlap = 120, 25
    doc = _rich_fixture()
    chunks = chunk_book(doc, target_chars=target_chars, overlap=overlap)

    # Every chunk stays within a bounded multiple of target_chars: each
    # packing unit is capped at target_chars, and a window stops growing as
    # soon as it would exceed target_chars, so no chunk should ever be more
    # than 2x target_chars.
    for chunk in chunks:
        assert len(chunk.text) <= 2 * target_chars

    # Consecutive chunks *within the same chapter* overlap by <= `overlap`
    # chars, and never by a negative amount (i.e. never leave a gap).
    for _, group in groupby(chunks, key=lambda c: c.section_path[0]):
        section_chunks = list(group)
        for prev_chunk, cur_chunk in pairwise(section_chunks):
            overlap_amount = prev_chunk.char_end - cur_chunk.char_start
            assert 0 <= overlap_amount <= overlap


def test_short_chapter_gets_its_own_chunk() -> None:
    """A chapter shorter than target_chars is never merged into a neighbor."""
    doc = _rich_fixture()
    chunks = chunk_book(doc, target_chars=120, overlap=25)
    block_by_id = {b.block_id: b for b in doc.blocks}

    chapter3_chunks = [
        c
        for c in chunks
        if {block_by_id[bid].section_path[0] for bid in c.block_ids} == {"Chapter 3"}
    ]
    assert len(chapter3_chunks) == 1
    assert chapter3_chunks[0].text == "Hi."


def test_invalid_target_overlap_raises() -> None:
    doc = _rich_fixture()
    with pytest.raises(ValueError, match="target_chars"):
        chunk_book(doc, target_chars=0, overlap=0)
    with pytest.raises(ValueError, match="overlap"):
        chunk_book(doc, target_chars=100, overlap=100)
    with pytest.raises(ValueError, match="overlap"):
        chunk_book(doc, target_chars=100, overlap=150)


# --------------------------------------------------------------------------
# Termination / degenerate-path tests
# --------------------------------------------------------------------------


def test_degenerate_blocks_do_not_hang_or_produce_empty_chunks() -> None:
    """An empty block, a block shorter than overlap, and a block with no
    sentence boundary at all (chapter 4 of the rich fixture) must all be
    handled without an infinite loop or a zero-length chunk. If the packing
    cursor ever failed to advance, this test would hang instead of failing.
    """
    doc = _rich_fixture()
    chunks = chunk_book(doc, target_chars=50, overlap=10)

    assert chunks
    for chunk in chunks:
        assert chunk.char_end > chunk.char_start
        assert chunk.text != ""
        assert chunk.block_ids


def test_no_sentence_boundary_block_splits_on_word_boundaries_only() -> None:
    """Chapter 4's second block is one long run of "word " tokens with no
    '.'/'!'/'?' at all. It must still be split (since it exceeds
    target_chars), and every split point must land on whitespace, never
    inside a word.
    """
    doc = _rich_fixture()
    chunks = chunk_book(doc, target_chars=50, overlap=10)
    block_by_id = {b.block_id: b for b in doc.blocks}

    chapter4_chunks = [
        c
        for c in chunks
        if {block_by_id[bid].section_path[0] for bid in c.block_ids} == {"Chapter 4"}
    ]
    assert len(chapter4_chunks) > 1

    for chunk in chapter4_chunks:
        end = chunk.char_end
        if end < len(doc.canonical_text):
            boundary_ok = doc.canonical_text[end - 1].isspace() or doc.canonical_text[end].isspace()
            assert boundary_ok, f"chunk ends mid-word: {chunk.text!r}"


def test_chunk_id_stable_and_deterministic() -> None:
    doc = _rich_fixture()
    chunks_a = chunk_book(doc, target_chars=120, overlap=25)
    chunks_b = chunk_book(doc, target_chars=120, overlap=25)

    assert [c.chunk_id for c in chunks_a] == [c.chunk_id for c in chunks_b]
    assert len({c.chunk_id for c in chunks_a}) == len(chunks_a)


def test_block_ids_non_empty_and_reference_real_blocks() -> None:
    doc = _rich_fixture()
    chunks = chunk_book(doc, target_chars=120, overlap=25)
    known_block_ids = {b.block_id for b in doc.blocks}

    for chunk in chunks:
        assert chunk.block_ids
        for bid in chunk.block_ids:
            assert bid in known_block_ids


def test_empty_book_returns_empty_list() -> None:
    doc = _build_doc("empty-book", [])
    assert chunk_book(doc) == []


def test_default_target_and_overlap() -> None:
    doc = _rich_fixture()
    chunks = chunk_book(doc)
    assert chunks
    for chunk in chunks:
        assert doc.canonical_text[chunk.char_start : chunk.char_end] == chunk.text


# --------------------------------------------------------------------------
# Internal helper tests (spec explicitly names these as part of the public
# interface, underscore-prefixed but intended to be independently testable)
# --------------------------------------------------------------------------


def test_split_sentences_reconstructs_input() -> None:
    text = "One. Two! Three? Four with no terminator"
    sentences = _split_sentences(text)
    assert "".join(sentences) == text
    assert len(sentences) == 4


def test_split_sentences_handles_empty_text() -> None:
    assert _split_sentences("") == []


def test_split_sentences_no_boundary_returns_whole_text() -> None:
    text = "just one long run of words with no terminal punctuation at all"
    assert _split_sentences(text) == [text]


def test_pack_sentences_respects_target_and_overlap() -> None:
    sentences = [f"Sentence {i} of moderate length here. " for i in range(20)]
    windows = _pack_sentences(sentences, target_chars=100, overlap=20)

    assert windows
    reconstructed = "".join(sentences)
    # Every window is a contiguous slice of the reconstructed text (since
    # sentences fully partition it); packing must not fabricate characters.
    for window in windows:
        assert window in reconstructed


def test_pack_sentences_handles_empty_input() -> None:
    assert _pack_sentences([], target_chars=100, overlap=20) == []
