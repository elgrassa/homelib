# spec: chunking — `homelib_core.chunk`

**Implemented by:** WP-06.
**Consumed by:** `apps/ingest/pipeline.py` (specs/ingestion.md), `homelib_rag.index`.

## Purpose

Turn a `BookDoc`'s ordered `Block`s into retrieval-sized `Chunk`s that are
still traceable back to exact offsets in `canonical_text` and to the
`Block`(s) they came from — so a citation can always be expanded to its
source page or chapter anchor.

## Public interface

```python
def chunk_book(
    doc: BookDoc,
    *,
    target_chars: int = 1200,
    overlap: int = 200,
) -> list[Chunk]: ...

def _split_sentences(text: str) -> list[str]: ...          # internal, no NLP dep beyond stdlib/regex
def _pack_sentences(sentences: Sequence[str], target_chars: int, overlap: int) -> list[str]: ...
```

## Data contracts (field-level)

Output is `list[Chunk]` per specs/core-models.md:

```
Chunk  chunk_id: str            # sha256(f"{book_id}|{ordinal_within_book}")[:16]
       book_id: str
       block_ids: list[str]     # non-empty; every block this chunk's span touches
       section_path: list[str]  # the section_path of the first block in the chunk's span
       text: str
       char_start: int          # into doc.canonical_text
       char_end: int
```

Algorithm shape: iterate blocks in `ordinal` order **within one chapter at a
time** (grouped by the top-level entry of `section_path`); inside a chapter,
split its concatenated block text into sentences, then greedily pack
sentences into windows of `target_chars` with `overlap` chars of trailing
context repeated at the start of the next window, snapping window boundaries
to sentence starts (never mid-sentence) and to block starts when a block
boundary falls within `overlap` of the chosen split point (never mid-word).
`block_ids` on a chunk lists every `Block.block_id` whose `[char_start,
char_end)` range intersects the chunk's own `[char_start, char_end)`.

## Binding invariants

1. **`doc.canonical_text[c.char_start:c.char_end] == c.text` for every
   chunk, no exceptions.** This is the contract every downstream consumer
   (citation expansion, eval ground truth, the UI's "show source") relies on.
   A chunk whose text was normalized (whitespace-collapsed, etc.) breaks this
   and is therefore not allowed — chunk text is a raw slice, never a
   transform.
2. **No chunk crosses a chapter boundary.** A chapter = the outermost element
   of `section_path` (index 0). If a chapter's tail is shorter than
   `overlap`, it still gets its own final (possibly short) chunk rather than
   being merged into the next chapter's first chunk.
3. `overlap < target_chars`; chunks are non-empty (`char_end > char_start`).
4. Chunk ordering matches block ordering: `chunk_id`s are assigned by walking
   blocks in `ordinal` order, so retrieval results can be sorted back into
   book-reading order without extra bookkeeping.

## Error / degradation behavior

- `target_chars <= overlap` or `target_chars <= 0` raises `ValueError` at
  call time — never silently clamped, since a silently-clamped chunk size
  would desync the embedding/retrieval tuning from what the caller asked for.
- A block whose own text exceeds `target_chars` by itself is still emitted as
  one or more chunks that respect invariant 1 (sentence-packed within the
  block); it is never truncated or dropped.
- An empty `BookDoc.blocks` (extraction failed upstream) returns `[]`, not an
  error — chunking degrades gracefully; the emptiness was already recorded in
  `ExtractionResult.warnings` by the format handler.

## Named red tests (write before the code)

- `test_chunk_spans_reconstruct_source` — for every chunk of every fixture
  `BookDoc` (including the OCR-path PDF fixture), assert
  `doc.canonical_text[c.char_start:c.char_end] == c.text`.
- `test_no_chunk_crosses_chapter_boundary` — for every chunk, all blocks in
  `c.block_ids` share the same `section_path[0]`.
- `test_overlap_within_bounds` — consecutive chunks' overlapping region is
  `<= overlap` chars and `> 0` unless one of the two is a chapter's first or
  last chunk.
- `test_short_chapter_gets_its_own_chunk` — a chapter shorter than
  `target_chars` is not merged into the neighboring chapter.
- `test_invalid_target_overlap_raises` — `target_chars <= overlap` raises
  `ValueError`.

## Verify

```
uv run pytest packages/homelib-core/tests/test_chunk.py -v
uv run python -c "
from homelib_core.normalize import parse_file
from homelib_core.chunk import chunk_book
from pathlib import Path
doc, _ = parse_file(Path('tests/fixtures/sample.epub'))
chunks = chunk_book(doc)
assert all(doc.canonical_text[c.char_start:c.char_end] == c.text for c in chunks)
print(len(chunks), 'chunks, invariant holds')
"
```
