"""DJVU format handler — see specs/formats.md.

Minimal stub. WP-05 implements extraction via the `djvutxt` CLI (conditional
on `djvulibre` being installed on the host). This stub exists only so
`homelib_core.normalize.parse_file` can dispatch `.djvu`/`.djv` files today;
WP-05 replaces the body of this file and must never need to touch
`homelib_core.normalize`.
"""

from pathlib import Path

from homelib_core.models import BookDoc, ExtractionResult


def parse_djvu(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]:
    """Extract a `BookDoc` from a DJVU file via `djvutxt`.

    Not yet implemented — see specs/formats.md, WP-05.
    """
    raise NotImplementedError(f"parse_djvu is implemented by WP-05 (got {path}, {book_id})")


def djvu_available() -> bool:
    """Whether the `djvutxt` binary is on PATH.

    Not yet implemented — see specs/formats.md, WP-05.
    """
    raise NotImplementedError("djvu_available is implemented by WP-05")
