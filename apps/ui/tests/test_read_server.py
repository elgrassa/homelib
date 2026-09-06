"""Clean /read helpers — Safari Listen to Page companion on :8502."""

from __future__ import annotations

import httpx
import pytest
import respx

from apps.ui.read_html import ReadPage, build_read_article_html
from apps.ui.read_server import DEFAULT_API, _api_base, _fetch_block, _fetch_book_title


def test_api_base_prefers_read_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", "http://read-api:8000/")
    monkeypatch.delenv("API_URL", raising=False)
    assert _api_base() == "http://read-api:8000"


def test_api_base_falls_back_to_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("READ_API_URL", raising=False)
    monkeypatch.setenv("API_URL", "http://api:9000")
    assert _api_base() == "http://api:9000"


def test_read_html_includes_previous_when_ordinal_allows() -> None:
    doc = build_read_article_html(
        ReadPage(
            book_id="walden",
            title="Walden",
            authors="Thoreau",
            ordinal=2,
            text="page three",
            prev_ordinal=1,
            next_ordinal=None,
        )
    )
    assert 'href="/read/walden?ordinal=1"' in doc
    assert "Next" not in doc


@respx.mock
def test_fetch_block_returns_page_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books/walden/blocks").mock(
        return_value=httpx.Response(
            200,
            json={"block_id": "b0", "book_id": "walden", "ordinal": 0, "text": "woods"},
        )
    )
    assert _fetch_block("walden", 0)["text"] == "woods"


@respx.mock
def test_fetch_block_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books/missing/blocks").mock(
        return_value=httpx.Response(404, json={"detail": "missing@0"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        _fetch_block("missing", 0)


@respx.mock
def test_fetch_book_title_resolves_catalog_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books").mock(
        return_value=httpx.Response(
            200,
            json=[{"book_id": "walden", "title": "Walden", "authors": ["Thoreau"]}],
        )
    )
    assert _fetch_book_title("walden") == ("Walden", "Thoreau")


@respx.mock
def test_fetch_book_title_falls_back_when_catalog_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_API_URL", DEFAULT_API)
    respx.get(f"{DEFAULT_API}/v1/books").mock(return_value=httpx.Response(200, json=[]))
    assert _fetch_book_title("unknown") == ("unknown", "")
