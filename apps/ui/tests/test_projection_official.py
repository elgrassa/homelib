"""Projection / official preview / clean read HTML — MagicLib LAN plan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.ui.read_html import ReadPage, build_read_article_html
from apps.ui.view_model import (
    CROSSROADS_DOORS,
    DEFAULT_OFFICIAL_LANGUAGE,
    DEFAULT_PROJECTION_SOURCE,
    DEFAULT_READ_PORT,
    OFFICIAL_VIEWER_ENV,
    clean_read_url,
    is_allowlisted_official_url,
    load_official_preview_books,
    normalize_official_language,
    normalize_projection_source,
    official_viewer_enabled,
    projection_wants_chrome_hidden,
    read_port,
)

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "apps" / "ui" / "fixtures" / "pottermore_uk_hp_preview.json"


def test_projection_flag_not_inferred_from_viewport_alone() -> None:
    assert projection_wants_chrome_hidden(projector_mode=False, query_projection=None) is False
    assert projection_wants_chrome_hidden(projector_mode=True, query_projection=None) is True
    assert projection_wants_chrome_hidden(projector_mode=False, query_projection="1") is True


def test_official_preview_language_defaults_to_ukrainian_for_demo() -> None:
    assert DEFAULT_PROJECTION_SOURCE == "shelf"
    assert DEFAULT_OFFICIAL_LANGUAGE == "uk"
    assert normalize_official_language(None) == "uk"
    assert normalize_official_language("en") == "en"


def test_normalize_projection_source_unknown_falls_back_to_shelf() -> None:
    assert normalize_projection_source("bogus") == "shelf"
    assert normalize_projection_source(None) == "shelf"


def test_projection_default_is_shelf() -> None:
    """The public capstone repo / Streamlit Cloud demo must default to the
    shelf, not a publisher-hosted (Pottermore) preview."""
    assert DEFAULT_PROJECTION_SOURCE == "shelf"
    assert normalize_projection_source("") == "shelf"
    assert normalize_projection_source(None) == "shelf"


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
    doc = build_official_preview_stage_html(book, projector=True, viewer_enabled=True)
    assert 'id="hl-official-book"' in doc
    assert "/book/" in doc
    assert book.id in doc
    assert 'id="hl-official-read"' in doc
    assert "Reading / Listen" in doc
    assert "location.assign" in doc
    assert "?read=1" in doc
    assert "window.open(" not in doc
    assert 'src="https://www.pottermorepublishing.com' not in doc


def test_official_preview_is_links_only_without_viewer_flag() -> None:
    """Owner decision: public demo shows Official preview as external links
    only; the internal iframe stage is opt-in via HOMELIB_OFFICIAL_VIEWER."""
    from apps.ui.view_model import build_official_preview_stage_html, load_official_preview_books

    book = load_official_preview_books("uk", fixture_path=FIXTURE)[0]
    doc = build_official_preview_stage_html(book, projector=True, viewer_enabled=False)
    assert "<iframe" not in doc.lower()
    assert "/book/" not in doc
    assert "location.assign" not in doc
    assert f'href="{book.pdf_url}"' in doc or f"href='{book.pdf_url}'" in doc
    assert f'href="{book.reader_url}"' in doc or f"href='{book.reader_url}'" in doc
    assert "Open Ukrainian PDF" in doc
    assert "Open HTML reader" in doc


def test_official_stage_never_embeds_read_port_without_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.ui.view_model import build_official_preview_stage_html, load_official_preview_books

    monkeypatch.delenv(OFFICIAL_VIEWER_ENV, raising=False)
    monkeypatch.setenv("READ_PORT", "9999")
    book = load_official_preview_books("uk", fixture_path=FIXTURE)[0]
    doc = build_official_preview_stage_html(book, projector=True, read_port=read_port())
    assert ":9999" not in doc
    assert "8502" not in doc


def test_official_viewer_flag_parses_truthy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for truthy in ("1", "true", "True", "yes", "YES", "on", "On"):
        monkeypatch.setenv(OFFICIAL_VIEWER_ENV, truthy)
        assert official_viewer_enabled() is True, truthy
    for falsy in ("0", "false", "no", "off", ""):
        monkeypatch.setenv(OFFICIAL_VIEWER_ENV, falsy)
        assert official_viewer_enabled() is False, falsy
    monkeypatch.delenv(OFFICIAL_VIEWER_ENV, raising=False)
    assert official_viewer_enabled() is False


def test_read_port_defaults_and_rejects_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("READ_PORT", raising=False)
    assert read_port() == DEFAULT_READ_PORT == 8502
    monkeypatch.setenv("READ_PORT", "9100")
    assert read_port() == 9100
    monkeypatch.setenv("READ_PORT", "not-a-port")
    assert read_port() == DEFAULT_READ_PORT
    monkeypatch.setenv("READ_PORT", "")
    assert read_port() == DEFAULT_READ_PORT


def test_allowlist_rejects_lookalike_and_http_hosts() -> None:
    assert (
        is_allowlisted_official_url("https://www.pottermorepublishing.com.evil.tld/x.pdf") is False
    )
    assert (
        is_allowlisted_official_url("https://evil.example/?x=www.pottermorepublishing.com") is False
    )
    assert is_allowlisted_official_url("http://www.pottermorepublishing.com/x.pdf") is False
    assert is_allowlisted_official_url("https://www.pottermorepublishing.com/x.pdf") is True


def test_load_official_preview_books_rejects_non_allowlisted_fixture(tmp_path: Path) -> None:
    bad_fixture = tmp_path / "bad.json"
    bad_fixture.write_text(
        json.dumps(
            {
                "books": [
                    {
                        "id": "hp-uk-1",
                        "title": "Test",
                        "authors": ["Author"],
                        "reader_url": "https://www.pottermorepublishing.com.evil.tld/x.html",
                        "pdf_url": "https://www.pottermorepublishing.com.evil.tld/x.pdf",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_official_preview_books("uk", fixture_path=bad_fixture)


def test_ukrainian_hp_fixture_exposes_direct_pdf_urls() -> None:
    books = load_official_preview_books("uk", fixture_path=FIXTURE)
    assert len(books) == 7
    for book in books:
        assert book.pdf_url.startswith("https://www.pottermorepublishing.com/")
        assert book.pdf_url.endswith(".pdf")
        assert "wp-content/uploads/" in book.pdf_url


def test_read_port_env_flows_into_links(monkeypatch: pytest.MonkeyPatch) -> None:
    """READ_PORT is the single source for the companion port in link text (A5)."""
    monkeypatch.setenv("READ_PORT", "9100")
    url = clean_read_url("thoreau-walden", ordinal=3, read_port=read_port())
    assert url.startswith(":9100/read/thoreau-walden")
    assert "8502" not in url
    monkeypatch.delenv("READ_PORT")
    assert clean_read_url("thoreau-walden", read_port=read_port()).startswith(":8502/read/")
