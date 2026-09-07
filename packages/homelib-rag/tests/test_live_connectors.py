"""Live connector mapping tests — respx fixtures only; no network in CI."""

from __future__ import annotations

import httpx
import pytest
import respx
from homelib_rag.connectors import (
    GOOGLE_BOOKS_VOLUMES_URL,
    GUTENDEX_BOOKS_URL,
    HARDCOVER_GRAPHQL_URL,
    OPEN_LIBRARY_SEARCH_URL,
    ConnectorName,
    ConnectorTimeout,
    GoogleBooksLiveConnector,
    GutenbergLiveConnector,
    HardcoverLiveConnector,
    OpenLibraryLiveConnector,
    build_discover_connectors,
)


@respx.mock
def test_open_library_live_maps_metadata_only_never_full_text() -> None:
    respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "docs": [
                    {
                        "key": "/works/OL100W",
                        "title": "Meditations",
                        "author_name": ["Marcus Aurelius"],
                        "first_publish_year": 1800,
                        "isbn": ["9780140449334"],
                    }
                ]
            },
        )
    )
    hits = OpenLibraryLiveConnector().search("meditations")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider is ConnectorName.OPEN_LIBRARY
    assert hit.title == "Meditations"
    assert hit.authors == ["Marcus Aurelius"]
    assert hit.provider_url == "https://openlibrary.org/works/OL100W"
    assert hit.full_text_available is False
    assert hit.rights_status == "metadata_only"


@respx.mock
def test_gutenberg_live_maps_provider_url_and_full_text_when_plain_text() -> None:
    respx.get(GUTENDEX_BOOKS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 2680,
                        "title": "Meditations",
                        "authors": [{"name": "Marcus Aurelius"}],
                        "copyright": False,
                        "formats": {"text/plain; charset=utf-8": "https://example/pg2680.txt"},
                    }
                ]
            },
        )
    )
    hits = GutenbergLiveConnector().search("meditations")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.work_key == "pg-2680"
    assert hit.provider_url == "https://www.gutenberg.org/ebooks/2680"
    assert hit.full_text_available is True
    assert hit.rights_status == "public_domain"


@respx.mock
def test_google_books_live_maps_infolink_never_claims_full_text() -> None:
    respx.get(GOOGLE_BOOKS_VOLUMES_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "zyTCAlFPjgYC",
                        "volumeInfo": {
                            "title": "Meditations",
                            "authors": ["Marcus Aurelius"],
                            "publishedDate": "2006",
                            "infoLink": "https://books.google.com/books?id=zyTCAlFPjgYC",
                            "industryIdentifiers": [
                                {"type": "ISBN_13", "identifier": "9780140449334"}
                            ],
                        },
                        "accessInfo": {"viewability": "PARTIAL", "epub": {"isAvailable": True}},
                    }
                ]
            },
        )
    )
    hits = GoogleBooksLiveConnector(api_key="test-key").search("meditations")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider is ConnectorName.GOOGLE_BOOKS
    assert hit.provider_url.startswith("https://books.google.com/")
    assert hit.full_text_available is False
    assert hit.rights_status == "metadata_only"


@respx.mock
def test_hardcover_live_maps_slug_url_metadata_only() -> None:
    respx.post(HARDCOVER_GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "search": {
                        "results": [
                            {
                                "id": 42,
                                "title": "Dune",
                                "slug": "dune",
                                "author_names": ["Frank Herbert"],
                            }
                        ]
                    }
                }
            },
        )
    )
    hits = HardcoverLiveConnector(api_token="secret").search("dune")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider is ConnectorName.HARDCOVER
    assert hit.title == "Dune"
    assert hit.authors == ["Frank Herbert"]
    assert hit.provider_url == "https://hardcover.app/books/dune"
    assert hit.full_text_available is False


@respx.mock
def test_live_open_library_timeout_raises_connector_timeout() -> None:
    respx.get(OPEN_LIBRARY_SEARCH_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ConnectorTimeout):
        OpenLibraryLiveConnector(timeout_seconds=0.01).search("meditations")


def test_build_discover_connectors_omits_keyed_providers_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOMELIB_CONNECTOR_MODE", "live")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GOOGLE_BOOKS_API_KEY", raising=False)
    monkeypatch.delenv("HARDCOVER_API_TOKEN", raising=False)
    monkeypatch.delenv("HARDCOVER_API_KEY", raising=False)
    names = {c.name for c in build_discover_connectors()}
    assert ConnectorName.OPEN_LIBRARY in names
    assert ConnectorName.GUTENBERG in names
    assert ConnectorName.GOOGLE_BOOKS not in names
    assert ConnectorName.HARDCOVER not in names


def test_build_discover_connectors_fixture_mode_includes_all_fixture_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOMELIB_CONNECTOR_MODE", "fixture")
    names = {c.name for c in build_discover_connectors()}
    assert names >= {
        ConnectorName.OPEN_LIBRARY,
        ConnectorName.GUTENBERG,
        ConnectorName.STANDARD_EBOOKS,
        ConnectorName.GOOGLE_BOOKS,
        ConnectorName.HARDCOVER,
    }


def test_build_discover_connectors_ci_env_defaults_to_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HOMELIB_CONNECTOR_MODE", raising=False)
    monkeypatch.setenv("CI", "true")
    names = {c.name for c in build_discover_connectors()}
    assert ConnectorName.STANDARD_EBOOKS in names
    assert ConnectorName.OPEN_LIBRARY in names
