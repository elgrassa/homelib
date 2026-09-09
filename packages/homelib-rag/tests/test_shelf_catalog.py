"""Shelf → catalog bridge for Stoicism / Meditations Mentor+Roadmap."""

from __future__ import annotations

from homelib_core.models import CatalogEntry
from homelib_rag.shelf_catalog import merge_catalog_with_shelf, shelf_catalog_entries


def test_shelf_catalog_entries_maps_stoicism_to_meditations() -> None:
    books = [
        ("aurelius-meditations", "Meditations", ["Marcus Aurelius"]),
        ("smith-wealth-of-nations", "Wealth of Nations", ["Adam Smith"]),
    ]
    entries = shelf_catalog_entries("calm", ["stoicism"], books)
    assert len(entries) == 1
    assert entries[0].ol_key == "shelf:aurelius-meditations"
    assert entries[0].title == "Meditations"


def test_shelf_catalog_entries_empty_books() -> None:
    assert shelf_catalog_entries("stoicism", ["stoicism"], []) == []


def test_shelf_catalog_entries_matches_title_substring() -> None:
    books = [("aurelius-meditations", "Meditations", ["Marcus Aurelius"])]
    entries = shelf_catalog_entries("read Meditations slowly", None, books)
    assert [e.ol_key for e in entries] == ["shelf:aurelius-meditations"]


def test_merge_catalog_with_shelf_dedupes_title() -> None:
    catalog = [
        CatalogEntry(
            ol_key="/works/OL1W",
            title="Meditations",
            authors=["Marcus Aurelius"],
            subjects=["Philosophy"],
            provenance_note="ol",
        )
    ]
    shelf = shelf_catalog_entries(
        "x",
        ["stoicism"],
        [("aurelius-meditations", "Meditations", ["M"])],
    )
    merged = merge_catalog_with_shelf(catalog, shelf)
    assert len(merged) == 1
    assert merged[0].ol_key == "/works/OL1W"


def test_merge_catalog_with_shelf_appends_new_title() -> None:
    catalog = [
        CatalogEntry(
            ol_key="/works/OL2W",
            title="Walden",
            authors=["Thoreau"],
            subjects=[],
            provenance_note="ol",
        )
    ]
    shelf = shelf_catalog_entries(
        "stoicism",
        ["stoicism"],
        [("aurelius-meditations", "Meditations", ["Marcus Aurelius"])],
    )
    merged = merge_catalog_with_shelf(catalog, shelf)
    assert [e.title for e in merged] == ["Walden", "Meditations"]


def test_needle_hits_blob_via_token_parts() -> None:
    from homelib_rag.shelf_catalog import _needle_hits_blob

    assert _needle_hits_blob("stoic calm", "meditations marcus") is False
    assert _needle_hits_blob("marcus aurelius", "by marcus aurelius") is True
