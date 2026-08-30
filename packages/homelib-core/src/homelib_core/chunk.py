"""Block-aware, sentence-boundary chunking — see specs/chunking.md.

Turns a `BookDoc`'s ordered `Block`s into retrieval-sized `Chunk`s that stay
traceable back to exact offsets in `canonical_text` and to the `Block`(s)
they came from.

The core trick that keeps invariant 1 (`canonical_text[c.char_start:c.char_end]
== c.text` for every chunk) trivially true: chunk boundaries are always
computed as *indices* into `canonical_text` (via cumulative sentence/word
spans), and chunk text is always produced by slicing `canonical_text` with
those indices — never by concatenating or otherwise transforming strings.
"""

import hashlib
import itertools
import re
from collections.abc import Sequence
from typing import NamedTuple

from homelib_core.models import Block, BookDoc, Chunk

__all__ = ["chunk_book"]

# A sentence boundary is a run of whitespace immediately following one or
# more sentence-ending punctuation marks. The trailing whitespace is kept
# attached to the *preceding* sentence so that concatenating the resulting
# spans always reconstructs the original text exactly (no characters are
# ever dropped or moved).
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


class _RawChunk(NamedTuple):
    """A chunk's data before its final, position-dependent `chunk_id`."""

    block_ids: list[str]
    section_path: list[str]
    text: str
    char_start: int
    char_end: int


def chunk_book(
    doc: BookDoc,
    *,
    target_chars: int = 1200,
    overlap: int = 200,
) -> list[Chunk]:
    """Chunk `doc` into retrieval-sized, citation-traceable `Chunk`s.

    Chunks never cross a chapter boundary (`Block.section_path[0]`), never
    split a sentence, and are packed to `target_chars` with up to `overlap`
    characters of trailing context repeated at the start of the next chunk
    within the same chapter.
    """
    if target_chars <= 0:
        raise ValueError("target_chars must be positive")
    if overlap < 0 or overlap >= target_chars:
        raise ValueError("overlap must be non-negative and less than target_chars")
    if not doc.blocks:
        return []

    raw_chunks: list[_RawChunk] = []
    for _, group_iter in itertools.groupby(doc.blocks, key=_chapter_key):
        chapter_blocks = list(group_iter)
        raw_chunks.extend(_chunk_chapter(doc, chapter_blocks, target_chars, overlap))

    return [
        Chunk(
            chunk_id=_make_chunk_id(doc.book_id, ordinal),
            book_id=doc.book_id,
            block_ids=raw.block_ids,
            section_path=raw.section_path,
            text=raw.text,
            char_start=raw.char_start,
            char_end=raw.char_end,
        )
        for ordinal, raw in enumerate(raw_chunks)
    ]


def _chapter_key(block: Block) -> str:
    """The chapter grouping key: the outermost entry of `section_path`."""
    return block.section_path[0] if block.section_path else ""


def _make_chunk_id(book_id: str, ordinal_within_book: int) -> str:
    raw = f"{book_id}|{ordinal_within_book}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _chunk_chapter(
    doc: BookDoc,
    blocks: list[Block],
    target_chars: int,
    overlap: int,
) -> list[_RawChunk]:
    """Chunk one chapter's worth of blocks (all sharing the same top-level
    `section_path` entry), never merging its tail into the next chapter.
    """
    if not blocks:
        return []

    chapter_start = blocks[0].char_start
    chapter_end = max(block.char_end for block in blocks)
    if chapter_end <= chapter_start:
        return []

    chapter_text = doc.canonical_text[chapter_start:chapter_end]
    units = _atomic_unit_spans(chapter_text, target_chars)
    if not units:
        return []

    lengths = [end - start for start, end in units]
    windows = _pack_indices(lengths, target_chars, overlap)

    raw_chunks: list[_RawChunk] = []
    for start_idx, end_idx in windows:
        local_start = units[start_idx][0]
        local_end = units[end_idx - 1][1]
        if local_end <= local_start:
            continue

        char_start = chapter_start + local_start
        char_end = chapter_start + local_end
        matching = sorted(
            (b for b in blocks if b.char_start < char_end and b.char_end > char_start),
            key=lambda b: b.ordinal,
        )
        if not matching:
            continue

        raw_chunks.append(
            _RawChunk(
                block_ids=[b.block_id for b in matching],
                section_path=matching[0].section_path,
                text=doc.canonical_text[char_start:char_end],
                char_start=char_start,
                char_end=char_end,
            )
        )
    return raw_chunks


def _sentence_split_points(text: str) -> list[int]:
    """End offsets partitioning `text` into sentences (last point == len(text))."""
    if not text:
        return []
    points = [m.end() for m in _SENTENCE_BOUNDARY_RE.finditer(text)]
    if not points or points[-1] != len(text):
        points.append(len(text))
    return points


def _points_to_spans(points: Sequence[int]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for point in points:
        spans.append((start, point))
        start = point
    return spans


def _split_sentences(text: str) -> list[str]:
    """Split `text` into sentences using stdlib regex only (no NLP dep).

    A "sentence" here is delimited by `.`/`!`/`?` followed by whitespace (or
    the end of the string). Text with no such boundary at all comes back as
    a single-element list containing the whole text — the degenerate path
    exercised by e.g. a heading or a caption with no terminal punctuation.
    Concatenating the result always reconstructs `text` exactly.
    """
    return [text[start:end] for start, end in _points_to_spans(_sentence_split_points(text))]


def _split_long_span(text: str, start: int, end: int, target_chars: int) -> list[tuple[int, int]]:
    """Fall back to word-boundary splitting for a sentence longer than
    `target_chars` on its own (e.g. no sentence-ending punctuation at all).

    Never splits mid-word when a whitespace break is available within the
    window; falls back to a hard cut only when a single "word" itself
    exceeds `target_chars`, which still guarantees forward progress.
    """
    if end - start <= target_chars:
        return [(start, end)]

    pieces: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        piece_end = min(cursor + target_chars, end)
        if piece_end < end:
            space_at = text.rfind(" ", cursor, piece_end)
            if space_at > cursor:
                piece_end = space_at + 1
        pieces.append((cursor, piece_end))
        cursor = piece_end
    return pieces


def _atomic_unit_spans(text: str, target_chars: int) -> list[tuple[int, int]]:
    """Sentence spans, with any sentence longer than `target_chars` further
    split on word boundaries so every atomic unit fits within one window.
    """
    units: list[tuple[int, int]] = []
    for start, end in _points_to_spans(_sentence_split_points(text)):
        units.extend(_split_long_span(text, start, end, target_chars))
    return units


def _pack_indices(
    lengths: Sequence[int],
    target_chars: int,
    overlap: int,
) -> list[tuple[int, int]]:
    """Greedily pack a sequence of unit lengths into windows of index ranges.

    Each window `[i, j)` always contains at least one unit (so a single unit
    longer than `target_chars` still gets its own window rather than being
    silently truncated or dropped). Consecutive windows repeat up to
    `overlap` chars of trailing units as leading context for the next
    window, snapped to unit boundaries. The cursor `i` strictly increases
    every iteration, so this always terminates within `len(lengths)` steps
    regardless of degenerate input (empty units, a single huge unit, a
    window whose entire content is short enough to fit within `overlap`,
    ...).
    """
    n = len(lengths)
    windows: list[tuple[int, int]] = []
    i = 0
    while i < n:
        j = i
        total = 0
        while j < n and (total == 0 or total + lengths[j] <= target_chars):
            total += lengths[j]
            j += 1
        windows.append((i, j))
        if j >= n:
            break

        # Pull back up to `overlap` chars of trailing units as leading
        # context for the next window, but never past i + 1: fully
        # reabsorbing the window's own first unit would set the next
        # window's start back to i, rebuilding the *same* window forever
        # (this bites whenever a window's whole content is short enough to
        # fit within `overlap`, e.g. a single small unit). Bounding the
        # pull-back at i + 1 guarantees the cursor strictly advances.
        k = j
        overlap_total = 0
        while k > i + 1 and overlap_total + lengths[k - 1] <= overlap:
            k -= 1
            overlap_total += lengths[k]
        i = k
    return windows


def _pack_sentences(sentences: Sequence[str], target_chars: int, overlap: int) -> list[str]:
    """Greedily pack `sentences` into `target_chars`-sized windows with up to
    `overlap` chars of trailing context repeated at the start of the next
    window. Public per specs/chunking.md; `chunk_book` uses the
    offset-tracking `_pack_indices` directly instead of this string-only
    wrapper, so that chunk spans are computed arithmetically rather than by
    re-locating substrings in `canonical_text`.
    """
    lengths = [len(s) for s in sentences]
    windows = _pack_indices(lengths, target_chars, overlap)
    return ["".join(sentences[i:j]) for i, j in windows]
