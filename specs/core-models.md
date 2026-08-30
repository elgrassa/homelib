# spec: core-models — `homelib_core.models`

**Implemented by:** WP-02 · **Consumed by:** every other component.

## Purpose

One universal in-memory representation for a book, whatever format it arrived
in, such that a retrieved passage can always be traced back to a page or a
chapter anchor in the original file.

## Public interface

```python
class Provenance(BaseModel)
class Block(BaseModel)
class BookDoc(BaseModel)
class Chunk(BaseModel)
class ExtractionResult(BaseModel)
class CatalogEntry(BaseModel)

BookDoc.to_jsonl(self) -> str          # one JSON object per line: header line, then blocks
BookDoc.from_jsonl(cls, text: str) -> BookDoc
make_block_id(book_id: str, section_path: Sequence[str], ordinal: int) -> str
```

## Data contracts (field-level)

```
Provenance   format: "epub"|"pdf"|"txt"|"md"|"djvu"
             page: int|None            # PDF/DjVu, 1-based
             spine_index: int|None     # EPUB
             anchor: str|None          # EPUB fragment id
             source_sha256: str        # sha256 of the ORIGINAL file

Block        block_id: str             # sha256(f"{book_id}|{'/'.join(section_path)}|{ordinal}")[:16]
             book_id: str
             ordinal: int              # 0-based, monotonic within the book
             section_path: list[str]   # chapter -> subsection, outermost first
             text: str
             char_start: int           # index into BookDoc.canonical_text
             char_end: int
             provenance: Provenance

BookDoc      book_id: str              # slug
             title: str
             authors: list[str]
             language: str
             source_url: str
             license_note: str
             blocks: list[Block]
             canonical_text: str

Chunk        chunk_id: str
             book_id: str
             block_ids: list[str]      # non-empty; the blocks this chunk spans
             section_path: list[str]
             text: str
             char_start: int
             char_end: int

ExtractionResult
             method: "native_text"|"ocr_fallback"|"mixed"|"extraction_failed"
             extractor_name: str
             extractor_version: str
             extraction_sha256: str    # sha256 of the extracted canonical_text
             ocr_engine: str|None
             warnings: list[str]

CatalogEntry ol_key: str               # Open Library work key, e.g. "/works/OL27448W"
             title: str
             authors: list[str]
             subjects: list[str]
             first_publish_year: int|None
             description: str|None      # optional context only — never shown as our copy
             provenance_note: str
```

## Invariants

1. **`model_config = ConfigDict(extra="allow")` on EVERY model.** Metadata we
   did not anticipate must survive a round trip rather than being silently
   dropped at the boundary. This is not stylistic: silent metadata loss is the
   single defect this spec exists to prevent.
2. `canonical_text[b.char_start:b.char_end] == b.text` for every block.
3. `block_id` is stable: same `(book_id, section_path, ordinal)` always yields
   the same id across runs and processes, so citations survive re-ingestion.
4. Blocks are ordered by `ordinal`, and ordinals are dense from 0.

## Error behavior

Construction is strict about *types* (Pydantic validation) and permissive about
*extra fields*. `from_jsonl` on malformed input raises `ValueError` with the
offending line number — never returns a partially populated `BookDoc`.

## Named red tests (write before the code)

- `test_extra_metadata_survives_roundtrip` — attach an unknown field to a
  `Block`, serialize, load, assert it is still readable.
- `test_block_offsets_index_into_canonical_text` — invariant 2 over a fixture.
- `test_jsonl_roundtrip_stable_ids` — round trip preserves every `block_id`,
  and recomputing ids from `(book_id, section_path, ordinal)` reproduces them.

## Verify

```
uv run pytest packages/homelib-core/tests/test_models.py -v
uv run mypy
grep -c 'extra="allow"' packages/homelib-core/src/homelib_core/models.py   # == number of models
```
