"""Format dispatcher — see specs/formats.md.

`parse_file` is the single entry point every downstream component depends
on: it turns any supported source file into a `BookDoc` + `ExtractionResult`
pair, regardless of which of the five supported formats it arrived in, so
downstream code (chunking, ingestion) never has to special-case a format
again.

WP-04 (PDF) and WP-05 (DJVU) replace only `formats/pdf.py` and
`formats/djvu.py` respectively — this module's dispatch shape is final as of
WP-03 and must never need to change for either of those work packages.
"""

import re
from pathlib import Path

from homelib_core.formats import djvu, epub, pdf, txt
from homelib_core.models import BookDoc, ExtractionResult

_SLUG_RE = re.compile(r"[^a-z0-9]+")

_TXT_SUFFIXES = frozenset({".txt", ".md"})
_DJVU_SUFFIXES = frozenset({".djvu", ".djv"})


def _slugify(stem: str) -> str:
    """Derive a `book_id` slug from a file stem (e.g. `"Moby Dick!" -> "moby-dick"`)."""
    slug = _SLUG_RE.sub("-", stem.lower()).strip("-")
    return slug or "book"


def parse_file(path: Path) -> tuple[BookDoc, ExtractionResult]:
    """Dispatch `path` to the right format handler by its suffix.

    Dispatches on `path.suffix.lower()`: `.epub` -> `formats.epub`, `.pdf` ->
    `formats.pdf`, `.txt`/`.md` -> `formats.txt`, `.djvu`/`.djv` ->
    `formats.djvu`. `book_id` is derived by slugifying the file stem —
    callers that need a specific `book_id` should call the format-specific
    `parse_*` function directly instead.

    Raises `ValueError` for any other suffix.
    """
    suffix = path.suffix.lower()
    book_id = _slugify(path.stem)

    if suffix == ".epub":
        return epub.parse_epub(path, book_id=book_id)
    if suffix == ".pdf":
        return pdf.parse_pdf(path, book_id=book_id)
    if suffix in _TXT_SUFFIXES:
        return txt.parse_txt(path, book_id=book_id)
    if suffix in _DJVU_SUFFIXES:
        return djvu.parse_djvu(path, book_id=book_id)

    raise ValueError(f"unsupported file extension {suffix!r}: {path}")
