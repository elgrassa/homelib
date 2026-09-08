"""Behavioural tests for shelf/collection-meta Ask routing."""

from __future__ import annotations

from homelib_core.models import CatalogEntry
from homelib_rag.shelf_meta import (
    ShelfBookRef,
    answer_shelf_meta,
    is_shelf_meta_intent,
)


def _walden() -> ShelfBookRef:
    return ShelfBookRef.from_parts(
        "Walden, and On The Duty Of Civil Disobedience",
        ["Henry David Thoreau"],
    )


def _meditations() -> ShelfBookRef:
    return ShelfBookRef.from_parts("Meditations", ["Marcus Aurelius"])


def test_walden_author_question_stays_on_passage_path() -> None:
    """Content Q about a shelf book must NOT take the shelf-meta shortcut."""
    assert is_shelf_meta_intent("Who wrote Walden?") is False
    assert is_shelf_meta_intent("What does Thoreau say about solitude?") is False


def test_inventory_and_romance_available_are_shelf_meta_intent() -> None:
    """Corpus-drawn inventory / genre-among-available asks route to shelf meta."""
    assert is_shelf_meta_intent("what do you have") is True
    assert is_shelf_meta_intent("which available romance book should I read?") is True
    assert is_shelf_meta_intent("what is the best science-fiction book to read in 2026?") is True
    assert is_shelf_meta_intent("what from available books is more interesting") is True


def test_what_do_you_have_lists_shelf_titles_not_empty_abstain() -> None:
    """Inventory must name grounded shelf titles — never empty refuse body."""
    result = answer_shelf_meta(
        "what do you have",
        [_walden(), _meditations()],
        arm_used="shelf_meta",
    )

    assert result.degraded is False
    assert result.citations == []
    assert result.arm_used == "shelf_meta"
    assert result.answer.strip() != ""
    assert "Walden" in result.answer
    assert "Meditations" in result.answer
    assert "Henry David Thoreau" in result.answer
    assert "passages do not answer" not in result.answer.lower()


def test_romance_from_available_uses_shelf_metadata_not_passage_abstain() -> None:
    """Genre-among-available with no romance titles still lists the shelf."""
    result = answer_shelf_meta(
        "which available romance book should I read?",
        [_walden(), _meditations()],
        arm_used="shelf_meta",
    )

    assert result.degraded is False
    assert result.answer.strip() != ""
    assert "romance" in result.answer.lower()
    assert "Walden" in result.answer
    assert "Meditations" in result.answer
    assert "passages do not answer" not in result.answer.lower()
    assert result.citations == []


def test_shelf_meta_can_append_catalog_links() -> None:
    entry = CatalogEntry(
        ol_key="/works/OL123W",
        title="Pride and Prejudice",
        authors=["Jane Austen"],
        subjects=["Romance"],
        first_publish_year=1813,
        description=None,
        provenance_note="Open Library",
    )
    result = answer_shelf_meta(
        "which available romance book?",
        [_walden()],
        catalog_entries=[entry],
    )

    assert "Pride and Prejudice" in result.answer
    assert "https://openlibrary.org/works/OL123W" in result.answer
    assert "Related catalog matches (not on this shelf)" in result.answer


def test_inventory_mentions_catalog_total_when_provided() -> None:
    result = answer_shelf_meta(
        "what do you have",
        [_walden(), _meditations()],
        catalog_total=3061,
    )

    assert "2 full-text" in result.answer or "2 full-text books" in result.answer
    assert "3061 Open Library" in result.answer
    assert "metadata only" in result.answer.lower()
