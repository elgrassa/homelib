"""Projection / official preview / clean read HTML — MagicLib LAN plan."""

from __future__ import annotations

from pathlib import Path

from apps.ui.read_html import ReadPage, build_read_article_html
from apps.ui.view_model import (
    CROSSROADS_DOORS,
    DEFAULT_OFFICIAL_LANGUAGE,
    DEFAULT_PROJECTION_SOURCE,
    load_official_preview_books,
    normalize_official_language,
    normalize_projection_source,
    projection_wants_chrome_hidden,
)

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "apps" / "ui" / "fixtures" / "pottermore_uk_hp_preview.json"


def test_projection_flag_not_inferred_from_viewport_alone() -> None:
    assert projection_wants_chrome_hidden(projector_mode=False, query_projection=None) is False
    assert projection_wants_chrome_hidden(projector_mode=True, query_projection=None) is True
    assert projection_wants_chrome_hidden(projector_mode=False, query_projection="1") is True


def test_official_preview_language_defaults_to_ukrainian_for_demo() -> None:
    assert DEFAULT_PROJECTION_SOURCE == "official"
    assert DEFAULT_OFFICIAL_LANGUAGE == "uk"
    assert normalize_official_language(None) == "uk"
    assert normalize_official_language("en") == "en"


def test_normalize_projection_source_unknown_falls_back_to_shelf() -> None:
    assert normalize_projection_source("bogus") == "shelf"
    assert normalize_projection_source(None) == "official"


def test_ukrainian_hp_fixture_is_metadata_only_and_pottermore_hosts() -> None:
    books = load_official_preview_books("uk", fixture_path=FIXTURE)
    assert len(books) == 7
    for book in books:
        assert "pottermorepublishing.com" in book.reader_url
        assert "pottermorepublishing.com" in book.pdf_url
        assert book.pdf_url.endswith(".pdf")
    assert load_official_preview_books("en") == []


def test_ukrainian_hp_pdf_bytes_absent_from_repo() -> None:
    offenders = [
        p
        for p in (REPO / "apps" / "ui" / "fixtures").rglob("*")
        if p.is_file() and "potter" in p.name.lower()
    ]
    assert offenders, "expected pottermore metadata fixture under apps/ui/fixtures"
    for path in offenders:
        assert path.suffix.lower() != ".pdf", path
        assert path.stat().st_size < 50_000, path


def test_pottermore_fixture_ships_inside_ui_package() -> None:
    """UI image only COPY's apps/ — fixture must live under apps/ui, not data/."""
    assert FIXTURE.is_file()
    assert "apps/ui/fixtures" in str(FIXTURE)
    assert load_official_preview_books("uk")  # default path, no fixture_path=


def test_crossroads_doors_unchanged_with_projection_submenu() -> None:
    assert "Official preview" not in CROSSROADS_DOORS
    assert "Pottermore" not in CROSSROADS_DOORS
    assert len(CROSSROADS_DOORS) == 7
    assert "Projection" in CROSSROADS_DOORS


def test_read_html_is_article_and_not_streamlit_shell() -> None:
    doc = build_read_article_html(
        ReadPage(
            book_id="walden",
            title="Walden",
            authors="Thoreau",
            ordinal=0,
            text="I went to the woods.",
            prev_ordinal=None,
            next_ordinal=1,
        )
    )
    assert "<article>" in doc
    assert "streamlit" not in doc.lower()
    assert "I went to the woods." in doc
    assert 'href="/read/walden?ordinal=1"' in doc


def test_official_preview_stage_uses_real_anchors_not_window_open() -> None:
    from apps.ui.view_model import (
        build_official_preview_stage_html,
        load_official_preview_books,
    )

    books = load_official_preview_books("uk", fixture_path=FIXTURE)
    assert books, "expected Ukrainian Pottermore fixture books"
    book = books[0]
    doc = build_official_preview_stage_html(book, projector=False)
    assert "<iframe" not in doc.lower()
    assert "window.open(" not in doc
    assert f'href="{book.pdf_url}"' in doc or f"href='{book.pdf_url}'" in doc
    assert book.reader_url in doc
    assert "Open Ukrainian PDF" in doc
    assert "Open HTML reader" in doc
    assert "aspect-ratio:16/9" in doc.replace(" ", "")


def test_official_preview_projector_embeds_internal_two_page_book() -> None:
    from apps.ui.view_model import build_official_preview_stage_html, load_official_preview_books

    book = load_official_preview_books("uk", fixture_path=FIXTURE)[0]
    doc = build_official_preview_stage_html(book, projector=True)
    assert 'id="hl-official-book"' in doc
    assert "/book/" in doc
    assert book.id in doc
    assert 'id="hl-official-read"' in doc
    assert "Reading / Listen" in doc
    assert "location.assign" in doc
    assert "?read=1" in doc
    assert "window.open(" not in doc
    assert 'src="https://www.pottermorepublishing.com' not in doc


def test_ukrainian_hp_fixture_exposes_direct_pdf_urls() -> None:
    books = load_official_preview_books("uk", fixture_path=FIXTURE)
    assert len(books) == 7
    for book in books:
        assert book.pdf_url.startswith("https://www.pottermorepublishing.com/")
        assert book.pdf_url.endswith(".pdf")
        assert "wp-content/uploads/" in book.pdf_url
