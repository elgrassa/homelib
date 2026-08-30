"""PDF format handler — see specs/formats.md.

Minimal stub. WP-04 implements native `pypdf` extraction plus the
`PyMuPDF`-based OCR fallback for scanned pages. This stub exists only so
`homelib_core.normalize.parse_file` can dispatch `.pdf` files today; WP-04
replaces the body of this file and must never need to touch
`homelib_core.normalize`.
"""

from pathlib import Path

from homelib_core.models import BookDoc, ExtractionResult


def parse_pdf(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]:
    """Extract a `BookDoc` from a PDF file.

    Not yet implemented — see specs/formats.md, WP-04.
    """
    raise NotImplementedError(f"parse_pdf is implemented by WP-04 (got {path}, {book_id})")


def _is_likely_scanned(text_by_page: list[str], page_count: int) -> bool:
    """Heuristic gate deciding whether a PDF needs OCR.

    Not yet implemented — see specs/formats.md, WP-04.
    """
    raise NotImplementedError(
        f"_is_likely_scanned is implemented by WP-04 (got {len(text_by_page)} pages, "
        f"page_count={page_count})"
    )
