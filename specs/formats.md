# spec: formats — `homelib_core.formats` + `homelib_core.normalize`

**Implemented by:** WP-03 (TXT/MD, EPUB), WP-04 (PDF native + OCR), WP-05 (DJVU, conditional).
**Consumed by:** `chunk_book` (specs/chunking.md), `apps/ingest/pipeline.py` (specs/ingestion.md).

## Purpose

One dispatch entry point that turns any supported source file into a
`BookDoc` + `ExtractionResult` (specs/core-models.md), regardless of format,
so every downstream component depends on a single normalized shape instead of
five parsers.

## Public interface

```python
# homelib_core.normalize
def parse_file(path: Path) -> tuple[BookDoc, ExtractionResult]: ...
    # dispatches on path.suffix.lower(): .epub -> formats.epub, .pdf -> formats.pdf,
    # .txt/.md -> formats.txt, .djvu -> formats.djvu. Unknown suffix -> ValueError.

# homelib_core.formats.epub
def parse_epub(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]: ...

# homelib_core.formats.pdf
def parse_pdf(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]: ...
def _is_likely_scanned(text_by_page: list[str], page_count: int) -> bool: ...

# homelib_core.formats.txt
def parse_txt(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]: ...

# homelib_core.formats.djvu
def parse_djvu(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]: ...
def djvu_available() -> bool: ...   # shutil.which("djvutxt") is not None
```

## Data contracts (field-level)

Output is always `BookDoc` + `ExtractionResult` per specs/core-models.md.
Format-specific `Provenance` population:

```
epub   Provenance.spine_index = OPF spine position (int, 0-based)
       Provenance.anchor      = NCX/nav fragment id, or None
       Provenance.page        = None
pdf    Provenance.page        = 1-based page number
       Provenance.spine_index = None
txt/md Provenance.page = None, spine_index = None, anchor = heading slug or None
djvu   Provenance.page        = 1-based page number (from djvutxt page breaks)
all    Provenance.source_sha256 = sha256 of the ORIGINAL file bytes (not the extracted text)
```

`ExtractionResult.method`:

```
native_text        pypdf / ebooklib / plain read succeeded, no OCR involved
ocr_fallback        _is_likely_scanned triggered PyMuPDF get_textpage_ocr on every page
mixed               some pages native, some OCR'd (partial scan)
extraction_failed   parse_file caught an unrecoverable error; BookDoc has 0 blocks,
                     warnings explain why (never raised past this boundary except
                     for the explicit refusals below)
```

TXT/MD heading inference: `#`/`##` (Markdown) or an all-caps / Title-Case
line shorter than 80 chars followed by a blank line (plain TXT) opens a new
`section_path` level; body text accumulates into the current section's block
until the next heading or EOF.

## Error / degradation behavior

- **Optional-dependency guard idiom (binding, every optional import):**
  ```python
  try:
      import fitz  # PyMuPDF
  except ImportError:
      fitz = None
  ```
  at module scope. The `ImportError`/`None` check happens **at the use site**
  (inside `parse_pdf`'s OCR branch), raising `RuntimeError("PyMuPDF not
  installed; install homelib-core[ocr]")` there. Never a silent skip that
  returns an empty `BookDoc` — a missing optional dependency on a page that
  actually needed it is a loud failure, not a quiet one.
- **Encrypted PDF: explicit refusal.** `parse_pdf` checks
  `PdfReader(path).is_encrypted`; if true, raises `ValueError("encrypted PDF
  not supported: <path>")` before any extraction attempt — never a silent
  empty-text result, never an attempted blank-password unlock.
- **EPUB zip-bomb guard.** Before `ebooklib` opens the archive, sum
  `ZipInfo.file_size` for all entries in the zip's central directory; if the
  uncompressed total exceeds `EPUB_MAX_UNCOMPRESSED_BYTES` (500 MB), raise
  `ValueError("epub exceeds size cap: <path>")` without decompressing.
- **DJVU: graceful skip, not a hard failure.** `parse_djvu` calls
  `djvu_available()` first; if `False`, raises
  `RuntimeError("djvutxt not found on PATH; install djvulibre or skip DJVU
  ingestion")` — callers (the corpus builder, `parse_file` dispatch) catch this
  specific exception and skip the file with a warning, never crash the whole
  ingestion run.
- **OCR path gate.** `_is_likely_scanned(text_by_page, page_count)` returns
  `True` when the mean extracted-chars-per-page across native `pypdf`
  extraction falls below a threshold (empirically: < 20 chars/page average,
  or > 50% of pages empty) — cheap enough to run on every PDF before deciding
  whether to pay for OCR.

## Named red tests (write before the code)

- `test_parse_file_dispatches_by_extension` — `.epub`/`.pdf`/`.txt`/`.md` each
  route to the right parser; unsupported suffix raises `ValueError`.
- `test_epub_zip_bomb_guard` — a crafted `ZipInfo` with an inflated
  `file_size` beyond the cap raises before any member is read.
- `test_encrypted_pdf_raises_clear_error` — an encrypted synthetic PDF raises
  `ValueError` mentioning "encrypted", never returns a `BookDoc`.
- `test_scanned_pdf_triggers_ocr_path` — a synthetic PDF with near-empty
  native text triggers the OCR branch (monkeypatched `fitz`); `method ==
  "ocr_fallback"`.
- `test_ocr_missing_dependency_fails_loudly` — with `fitz` monkeypatched to
  `None` at module scope, a page that needs OCR raises `RuntimeError`
  mentioning the install extra, never silently skips the page.
- `test_djvu_skips_cleanly_without_binary` — `shutil.which` monkeypatched to
  return `None`; `parse_djvu` raises the specific `RuntimeError`, and
  `parse_file` on a `.djvu` path is caught by the corpus builder without
  aborting the run (`pytest.importorskip`-style guard, run once with and once
  without PATH per WP-05).

## Verify

```
uv run pytest packages/homelib-core/tests/test_format_txt.py packages/homelib-core/tests/test_format_epub.py packages/homelib-core/tests/test_format_pdf.py -v
uv run pytest -k djvu -v
uv run python -c "from homelib_core.normalize import parse_file; d,r=parse_file(Path('tests/fixtures/sample.epub')); print(len(d.blocks), r.method)"
```
