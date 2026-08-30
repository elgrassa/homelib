"""PDF format handler — see specs/formats.md.

Two extraction paths, chosen per document by `_is_likely_scanned`:

- **native text**: `pypdf` extracts each page's text layer directly. This is
  the common case (a PDF produced by a word processor or `LaTeX`) and is
  cheap — no OCR engine involved.
- **OCR fallback**: for a page whose native text is too sparse to be real
  body text (see `_is_likely_scanned`'s docstring for the exact thresholds
  and the reasoning behind them), PyMuPDF's `get_textpage_ocr` rasterizes
  the page and runs Tesseract over it. This only runs on the pages that
  actually need it — a document with a few scanned pages mixed into an
  otherwise-native book gets `ExtractionResult.method == "mixed"` rather
  than paying for OCR on every page.

Block granularity: one `Block` per non-empty page, in page order.
`Provenance.page` is the 1-based page number; PDF has no reliable in-band
heading structure to hang a `section_path` on, so every PDF block's
`section_path` is `[]` (unlike TXT/EPUB, which infer headings).

PyMuPDF is an optional dependency (`homelib-core[ocr]`) so a production
install that never ingests scanned PDFs doesn't need to ship Tesseract's
weight. See the module-scope `try`/`except ImportError` below: importing it
never raises past this module, but calling into the OCR branch without it
installed raises loudly (`RuntimeError`), never a silent empty result — see
`_ocr_extract`.
"""

import hashlib
from pathlib import Path
from typing import Literal

from pypdf import PdfReader

from homelib_core.models import Block, BookDoc, ExtractionResult, Provenance, make_block_id

try:
    import pymupdf
except ImportError:  # pragma: no cover - exercised via monkeypatch in tests
    pymupdf = None  # type: ignore[assignment]

EXTRACTOR_NAME = "homelib-core.formats.pdf"
EXTRACTOR_VERSION = "1.0.0"

OCR_ENGINE = "pymupdf-tesseract"

# `_is_likely_scanned`'s two independent signals, and the per-page decision
# of whether an individual page needs OCR once the document as a whole has
# been judged scanned (see `_ocr_extract`) — all share this single "a real
# text page carries far more than this many characters" threshold. Chosen
# empirically: normal body-text pages run into the hundreds/thousands of
# characters, so 20 chars/page is comfortably below any real paragraph while
# still well above the handful of stray characters `pypdf` sometimes pulls
# from an image-only page's incidental vector content (page numbers stamped
# as text, watermarks, etc.).
_SCANNED_CHARS_PER_PAGE_THRESHOLD = 20

# The second signal: even if the *mean* looks fine (a few dense text pages
# can hide a mostly-scanned document), more than half the pages having
# (near-)zero native text is on its own enough to call the whole document
# scanned.
_SCANNED_EMPTY_PAGE_RATIO_THRESHOLD = 0.5

_Method = Literal["native_text", "ocr_fallback", "mixed"]


def _is_likely_scanned(text_by_page: list[str], page_count: int) -> bool:
    """Heuristic gate: does this PDF need the OCR fallback at all?

    Cheap enough to run on every PDF right after native `pypdf` extraction,
    before paying for OCR on anything (see specs/formats.md, "OCR path
    gate"). Triggers on either of two independent signals:

    - the mean native chars/page across the whole document falls below
      `_SCANNED_CHARS_PER_PAGE_THRESHOLD` (20) — most pages are effectively
      blank to `pypdf`, which is what an image-only scan looks like.
    - more than `_SCANNED_EMPTY_PAGE_RATIO_THRESHOLD` (50%) of pages
      individually fall below that same per-page threshold — catches a
      document where a handful of unusually text-dense pages (a title page,
      an OCR'd cover) would otherwise pull the mean up and mask a mostly
      scanned body.

    A `page_count` of 0 is judged not scanned (there is nothing to OCR).
    """
    if page_count == 0:
        return False

    stripped_lengths = [len(text.strip()) for text in text_by_page]
    mean_chars_per_page = sum(stripped_lengths) / page_count
    sparse_pages = sum(
        1 for length in stripped_lengths if length < _SCANNED_CHARS_PER_PAGE_THRESHOLD
    )
    sparse_ratio = sparse_pages / page_count

    return (
        mean_chars_per_page < _SCANNED_CHARS_PER_PAGE_THRESHOLD
        or sparse_ratio > _SCANNED_EMPTY_PAGE_RATIO_THRESHOLD
    )


def _ocr_extract(path: Path, page_count: int) -> list[str]:
    """Run PyMuPDF's OCR text extraction over every page of `path`.

    Raises `RuntimeError` naming the install extra if PyMuPDF is not
    installed — this is only ever called once `_is_likely_scanned` has
    already decided OCR is needed, so a missing optional dependency here is
    a real failure to surface, never a silent empty-page result.
    """
    if pymupdf is None:
        raise RuntimeError("PyMuPDF not installed; install homelib-core[ocr] to OCR scanned PDFs")

    ocr_text_by_page: list[str] = []
    ocr_doc = pymupdf.open(path)  # type: ignore[no-untyped-call]
    try:
        for index in range(page_count):
            ocr_page = ocr_doc[index]
            textpage = ocr_page.get_textpage_ocr(  # type: ignore[no-untyped-call]
                flags=3, dpi=300, full=True
            )
            text: str = ocr_page.get_text(textpage=textpage)  # type: ignore[no-untyped-call]
            ocr_text_by_page.append(text)
    finally:
        ocr_doc.close()  # type: ignore[no-untyped-call]

    return ocr_text_by_page


def _extract_title(reader: PdfReader, fallback: str) -> str:
    metadata = reader.metadata
    title = metadata.title if metadata is not None else None
    return str(title) if title else fallback


def _extract_authors(reader: PdfReader) -> list[str]:
    metadata = reader.metadata
    author = metadata.author if metadata is not None else None
    return [str(author)] if author else []


def parse_pdf(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]:
    """Extract a `BookDoc` from a PDF file.

    Raises `ValueError` (mentioning "encrypted") for an encrypted PDF,
    before any extraction is attempted — never a silent empty result, never
    an attempted blank-password unlock.
    """
    warnings: list[str] = []
    raw_bytes = path.read_bytes()
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError(f"encrypted PDF not supported: {path}")

    page_count = len(reader.pages)
    native_text_by_page: list[str] = [page.extract_text() or "" for page in reader.pages]

    title = _extract_title(reader, fallback=path.stem)
    authors = _extract_authors(reader)

    final_text_by_page = list(native_text_by_page)
    page_used_ocr = [False] * page_count

    if _is_likely_scanned(native_text_by_page, page_count):
        ocr_text_by_page = _ocr_extract(path, page_count)
        for index in range(page_count):
            # Only replace pages that actually need it: a document judged
            # scanned overall may still have a handful of pages with real
            # native text (a born-digital cover bound into a scanned book),
            # and those should stay native rather than be re-OCR'd.
            if len(native_text_by_page[index].strip()) < _SCANNED_CHARS_PER_PAGE_THRESHOLD:
                final_text_by_page[index] = ocr_text_by_page[index]
                page_used_ocr[index] = True

    ocr_page_count = sum(page_used_ocr)
    method: _Method
    ocr_engine: str | None
    if ocr_page_count == 0:
        method, ocr_engine = "native_text", None
    elif ocr_page_count == page_count:
        method, ocr_engine = "ocr_fallback", OCR_ENGINE
    else:
        method, ocr_engine = "mixed", OCR_ENGINE

    blocks: list[Block] = []
    canonical_text = ""
    ordinal = 0
    for page_index, page_text in enumerate(final_text_by_page):
        text = page_text.strip()
        if not text:
            warnings.append(f"page {page_index + 1} produced no extractable text")
            continue

        if canonical_text:
            canonical_text += "\n\n"
        char_start = len(canonical_text)
        canonical_text += text
        char_end = len(canonical_text)

        blocks.append(
            Block(
                block_id=make_block_id(book_id, [], ordinal),
                book_id=book_id,
                ordinal=ordinal,
                section_path=[],
                text=text,
                char_start=char_start,
                char_end=char_end,
                provenance=Provenance(
                    format="pdf",
                    page=page_index + 1,
                    spine_index=None,
                    anchor=None,
                    source_sha256=source_sha256,
                ),
            )
        )
        ordinal += 1

    extraction_sha256 = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    doc = BookDoc(
        book_id=book_id,
        title=title,
        authors=authors,
        language="en",
        source_url="",
        license_note="",
        blocks=blocks,
        canonical_text=canonical_text,
    )
    result = ExtractionResult(
        method=method,
        extractor_name=EXTRACTOR_NAME,
        extractor_version=EXTRACTOR_VERSION,
        extraction_sha256=extraction_sha256,
        ocr_engine=ocr_engine,
        warnings=warnings,
    )
    return doc, result
