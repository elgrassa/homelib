"""Bridge shelf titles into catalog candidates for Mentor / Roadmap.

The Open Library snapshot is an engineering/management subject slice — topics
like Stoicism are on the full-text shelf (Meditations) but absent from catalog
subjects. Roadmap's caption already promises shelf hits; this module supplies
them as `CatalogEntry` rows with `ol_key=shelf:<book_id>`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from homelib_core.models import CatalogEntry

__all__ = ["merge_catalog_with_shelf", "shelf_catalog_entries"]

# Demo-shelf topic bridges when the OL subject filter has no philosophy slice.
_TOPIC_SHELF_BOOK_IDS: dict[str, tuple[str, ...]] = {
    "stoicism": ("aurelius-meditations",),
    "stoic": ("aurelius-meditations",),
    "meditations": ("aurelius-meditations",),
}


def shelf_catalog_entries(
    query: str,
    subjects: Sequence[str] | None,
    books: Sequence[tuple[str, str, Sequence[str]]],
) -> list[CatalogEntry]:
    """Return shelf books matching the goal/interests by title, author, or topic."""
    if not books:
        return []
    needles = [query.strip().casefold(), *[s.strip().casefold() for s in (subjects or [])]]
    needles = [n for n in needles if n]
    by_id = {book_id: (title, list(authors)) for book_id, title, authors in books}
    matched_ids: list[str] = []
    seen: set[str] = set()

    for book_id, title, authors in books:
        blob = f"{title} {' '.join(authors)}".casefold()
        if book_id not in seen and any(_needle_hits_blob(needle, blob) for needle in needles):
            seen.add(book_id)
            matched_ids.append(book_id)

    for needle in needles:
        for token in re.findall(r"[a-z0-9']+", needle):
            for book_id in _TOPIC_SHELF_BOOK_IDS.get(token, ()):
                if book_id in by_id and book_id not in seen:
                    seen.add(book_id)
                    matched_ids.append(book_id)

    out: list[CatalogEntry] = []
    for book_id in matched_ids:
        title, authors = by_id[book_id]
        out.append(
            CatalogEntry(
                ol_key=f"shelf:{book_id}",
                title=title,
                authors=authors,
                subjects=list(subjects or []),
                first_publish_year=None,
                description=None,
                provenance_note="Full-text shelf",
            )
        )
    return out


def _needle_hits_blob(needle: str, blob: str) -> bool:
    if needle in blob:
        return True
    return any(len(part) >= 4 and part in blob for part in re.findall(r"[a-z0-9']+", needle))


def merge_catalog_with_shelf(
    catalog: list[CatalogEntry],
    shelf: list[CatalogEntry],
) -> list[CatalogEntry]:
    """Catalog first, then shelf rows whose title is not already present."""
    seen_titles = {entry.title.casefold() for entry in catalog}
    merged = list(catalog)
    for entry in shelf:
        if entry.title.casefold() in seen_titles:
            continue
        seen_titles.add(entry.title.casefold())
        merged.append(entry)
    return merged
