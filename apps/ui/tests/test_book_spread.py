"""Official Pottermore two-page book viewer + allowlisted PDF proxy."""

from __future__ import annotations

from apps.ui.book_spread import build_book_spread_html, official_book_by_id
from apps.ui.view_model import build_official_preview_stage_html, load_official_preview_books


def test_official_book_by_id_resolves_fixture() -> None:
    book = official_book_by_id("hp-uk-1")
    assert book is not None
    assert book.pdf_url.endswith(".pdf")
    assert official_book_by_id("nope") is None


def test_book_spread_html_is_two_page_pdfjs_stage() -> None:
    book = official_book_by_id("hp-uk-1")
    assert book is not None
    doc = build_book_spread_html(book)
    assert "<!doctype html>" in doc.lower()
    assert 'id="left"' in doc
    assert 'id="right"' in doc
    assert "pdf.js" in doc or "pdf.min.mjs" in doc
    assert "/pdf/" in doc
    assert "Prev" in doc and "Next" in doc
    assert "flip-leaf" in doc
    assert 'id="toggle-read"' in doc
    assert 'id="reader"' in doc
    assert "Reading / Listen" in doc
    assert "wantsReadMode" in doc
    assert 'q.get("read")' in doc


def test_projector_stage_embeds_book_viewer_not_pottermore_iframe() -> None:
    books = load_official_preview_books("uk")
    book = books[0]
    doc = build_official_preview_stage_html(book, projector=True)
    assert 'id="hl-official-book"' in doc
    assert "/book/" in doc
    assert "window.open(" not in doc
    assert 'src="https://www.pottermorepublishing.com' not in doc
    assert "Publisher PDF" in doc  # lawful fallback link OK
    assert 'id="hl-official-read"' in doc
    assert "?read=1" in doc
    assert "location.assign" in doc
