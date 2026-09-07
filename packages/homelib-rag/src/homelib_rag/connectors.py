"""Lawful catalog federation — see specs/connectors.md.

CI / ``HOMELIB_CONNECTOR_MODE=fixture`` reads JSONL fixtures (no network).
Default ``live`` mode hits Open Library + Gutendex (Gutenberg catalog) over
HTTP; Google Books and Hardcover join only when their API keys are set.
Timeouts and HTTP failures raise ``ConnectorTimeout`` so federation sets
``degraded=True`` without failing sibling providers.

Discovery connectors return metadata + lawful provider URLs only. They never
ingest remote full text into the Ask corpus (ADR-008). Open Library and
Google Books hits always set ``full_text_available=False`` even when a
preview exists — HomeLib does not claim those APIs as reading corpus.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BANNED_CONNECTOR_HOSTS",
    "CatalogConnector",
    "ConnectorHit",
    "ConnectorName",
    "ConnectorTimeout",
    "DiscoverResult",
    "FederatedItem",
    "FixtureConnector",
    "GoogleBooksLiveConnector",
    "GutenbergLiveConnector",
    "HardcoverLiveConnector",
    "OpenLibraryLiveConnector",
    "ProviderAttribution",
    "SlowConnector",
    "build_discover_connectors",
    "connector_user_agent",
    "federate_connectors",
    "federate_hits",
    "load_fixture_hits",
    "refuse_banned_url",
]

logger = logging.getLogger(__name__)

BANNED_CONNECTOR_HOSTS: frozenset[str] = frozenset(
    {
        "annas-archive.org",
        "annas-archive.se",
        "libgen.is",
        "libgen.rs",
        "sci-hub.se",
        "sci-hub.st",
    }
)

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
GUTENDEX_BOOKS_URL = "https://gutendex.com/books"
GOOGLE_BOOKS_VOLUMES_URL = "https://www.googleapis.com/books/v1/volumes"
HARDCOVER_GRAPHQL_URL = "https://api.hardcover.app/v1/graphql"
DEFAULT_LIVE_LIMIT = 10
DEFAULT_LIVE_TIMEOUT_SECONDS = 5.0

_HARDCOVER_SEARCH_QUERY = """
query Search($title: String!) {
  search(
    query: $title
    query_type: "books"
    per_page: 5
    page: 1
    sort: "activities_count:desc"
  ) {
    results
  }
}
""".strip()


class ConnectorName(StrEnum):
    OPEN_LIBRARY = "open_library"
    STANDARD_EBOOKS = "standard_ebooks"
    GUTENBERG = "gutenberg"
    GOOGLE_BOOKS = "google_books"
    HARDCOVER = "hardcover"


class ConnectorHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_key: str
    title: str
    authors: list[str]
    provider: ConnectorName
    provider_url: str
    full_text_available: bool
    rights_status: str
    approximate_count_member: bool = False
    publish_year: int | None = None
    isbn: str | None = None
    doi: str | None = None


class ProviderAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ConnectorName
    provider_url: str


class FederatedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_key: str | None
    title: str
    authors: list[str]
    attributions: list[ProviderAttribution] = Field(min_length=1)
    full_text_available: bool
    rights_status: str


class DiscoverResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FederatedItem]
    unique_count: int
    approximate_provider_counts: dict[str, int]
    degraded: bool


class ConnectorTimeout(Exception):
    """Raised by a connector when its deadline is exceeded or the call fails."""


class CatalogConnector(Protocol):
    name: ConnectorName

    def search(self, query: str) -> list[ConnectorHit]: ...


def connector_user_agent() -> str:
    contact = os.environ.get("HOMELIB_CONTACT", "").strip()
    if contact:
        return f"HomeLib/0.1 ({contact})"
    return "HomeLib/0.1 (+https://github.com/elgrassa/homelib)"


def refuse_banned_url(url: str) -> None:
    host = urlparse(url).hostname
    if host is None:
        return
    normalized = host.removeprefix("www.").lower()
    if normalized in BANNED_CONNECTOR_HOSTS:
        raise ValueError(f"banned connector host: {normalized}")


def load_fixture_hits(path: Path, *, provider: ConnectorName) -> list[ConnectorHit]:
    hits: list[ConnectorHit] = []
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith('{"_provenance"'):
                continue
            payload = json.loads(line)
            url = str(payload["provider_url"])
            refuse_banned_url(url)
            hits.append(
                ConnectorHit(
                    work_key=str(payload["work_key"]),
                    title=str(payload["title"]),
                    authors=[str(a) for a in payload["authors"]],
                    provider=provider,
                    provider_url=url,
                    full_text_available=bool(payload.get("full_text_available", False)),
                    rights_status=str(payload.get("rights_status", "metadata_only")),
                    approximate_count_member=bool(payload.get("approximate_count_member", False)),
                    publish_year=payload.get("publish_year"),
                    isbn=payload.get("isbn"),
                    doi=payload.get("doi"),
                )
            )
    return hits


def _edition_ambiguous(left: ConnectorHit, right: ConnectorHit) -> bool:
    same_title = left.title.strip().lower() == right.title.strip().lower()
    same_authors = sorted(a.lower() for a in left.authors) == sorted(
        a.lower() for a in right.authors
    )
    if not (same_title and same_authors):
        return False
    if left.publish_year is None or right.publish_year is None:
        return False
    if left.publish_year == right.publish_year:
        return False
    if left.doi and right.doi and left.doi.lower() == right.doi.lower():
        return False
    same_isbn = (
        left.isbn and right.isbn and left.isbn.replace("-", "") == right.isbn.replace("-", "")
    )
    return not same_isbn


def _can_merge(left: ConnectorHit, right: ConnectorHit) -> bool:
    if _edition_ambiguous(left, right):
        return False
    if left.doi and right.doi and left.doi.lower() == right.doi.lower():
        return True
    if left.isbn and right.isbn and left.isbn.replace("-", "") == right.isbn.replace("-", ""):
        return True
    if left.work_key and right.work_key and left.work_key == right.work_key:
        return True
    same_title = left.title.strip().lower() == right.title.strip().lower()
    same_authors = sorted(a.lower() for a in left.authors) == sorted(
        a.lower() for a in right.authors
    )
    return (
        same_title
        and same_authors
        and left.publish_year is not None
        and left.publish_year == right.publish_year
    )


def _merge_hits(group: Sequence[ConnectorHit]) -> FederatedItem:
    first = group[0]
    attributions = [
        ProviderAttribution(provider=hit.provider, provider_url=hit.provider_url) for hit in group
    ]
    work_key = first.work_key if len({h.work_key for h in group}) == 1 else None
    return FederatedItem(
        work_key=work_key,
        title=first.title,
        authors=list(first.authors),
        attributions=attributions,
        full_text_available=any(h.full_text_available for h in group),
        rights_status=first.rights_status,
    )


def federate_hits(hits: Sequence[ConnectorHit]) -> list[FederatedItem]:
    """Dedup with attribution preservation; ambiguous editions stay separate."""
    if not hits:
        return []

    groups: list[list[ConnectorHit]] = []
    for hit in hits:
        target: list[ConnectorHit] | None = None
        for group in groups:
            if any(_edition_ambiguous(hit, member) for member in group):
                continue
            if _can_merge(hit, group[0]):
                target = group
                break
        if target is None:
            groups.append([hit])
        else:
            target.append(hit)

    return [_merge_hits(group) for group in groups]


def federate_connectors(
    connectors: Sequence[CatalogConnector],
    query: str,
    *,
    timeout_seconds: float = 5.0,
) -> DiscoverResult:
    """Search all connectors; timeouts degrade without failing siblings."""
    _ = timeout_seconds
    degraded = False
    provider_counts: dict[str, int] = {}
    all_hits: list[ConnectorHit] = []

    for connector in connectors:
        try:
            hits = connector.search(query)
        except ConnectorTimeout:
            degraded = True
            logger.warning("connector %s timed out during discover", connector.name.value)
            continue
        provider_counts[connector.name.value] = len(hits)
        all_hits.extend(hits)

    items = federate_hits(all_hits)
    return DiscoverResult(
        items=items,
        unique_count=len(items),
        approximate_provider_counts=provider_counts,
        degraded=degraded,
    )


def _default_fixture_dir() -> Path:
    env = os.environ.get("HOMELIB_CONNECTOR_FIXTURE_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "connectors"


def build_discover_connectors(
    *,
    mode: str | None = None,
    client: httpx.Client | None = None,
) -> list[CatalogConnector]:
    """Assemble providers for Discover. Fixture mode is CI-safe (no network)."""
    if mode is not None:
        resolved = mode.strip().lower()
    else:
        explicit = os.environ.get("HOMELIB_CONNECTOR_MODE", "").strip().lower()
        if explicit:
            resolved = explicit
        elif os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}:
            # Forgejo/GHA set CI=true — never open live catalog sockets in CI.
            resolved = "fixture"
        else:
            resolved = "live"
    if resolved == "fixture":
        root = _default_fixture_dir()
        connectors: list[CatalogConnector] = [
            FixtureConnector(ConnectorName.OPEN_LIBRARY, root / "open_library.jsonl"),
            FixtureConnector(ConnectorName.GUTENBERG, root / "gutenberg.jsonl"),
            FixtureConnector(ConnectorName.STANDARD_EBOOKS, root / "standard_ebooks.jsonl"),
        ]
        google_path = root / "google_books.jsonl"
        if google_path.is_file():
            connectors.append(FixtureConnector(ConnectorName.GOOGLE_BOOKS, google_path))
        hardcover_path = root / "hardcover.jsonl"
        if hardcover_path.is_file():
            connectors.append(FixtureConnector(ConnectorName.HARDCOVER, hardcover_path))
        return connectors

    live: list[CatalogConnector] = [
        OpenLibraryLiveConnector(client=client),
        GutenbergLiveConnector(client=client),
    ]
    google_key = os.environ.get("GOOGLE_BOOKS_API_KEY", "").strip()
    if google_key:
        live.append(GoogleBooksLiveConnector(api_key=google_key, client=client))
    hardcover_token = (
        os.environ.get("HARDCOVER_API_TOKEN", "").strip()
        or os.environ.get("HARDCOVER_API_KEY", "").strip()
    )
    if hardcover_token:
        live.append(HardcoverLiveConnector(api_token=hardcover_token, client=client))
    return live


class FixtureConnector:
    """JSONL-backed connector for CI and offline Discover."""

    def __init__(self, name: ConnectorName, fixture_path: Path) -> None:
        self.name = name
        self._fixture_path = fixture_path
        self._hits = load_fixture_hits(fixture_path, provider=name)

    def search(self, query: str) -> list[ConnectorHit]:
        needle = query.strip().lower()
        if not needle:
            return []
        return [
            hit
            for hit in self._hits
            if needle in hit.title.lower()
            or any(needle in author.lower() for author in hit.authors)
        ]


class SlowConnector:
    """Test double that always times out."""

    name = ConnectorName.STANDARD_EBOOKS

    def search(self, query: str) -> list[ConnectorHit]:
        _ = query
        raise ConnectorTimeout("simulated timeout")


def _owned_or_shared_client(
    client: httpx.Client | None,
) -> tuple[httpx.Client, bool]:
    if client is not None:
        return client, False
    return httpx.Client(headers={"User-Agent": connector_user_agent()}), True


def _get_json(
    client: httpx.Client,
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float,
) -> Any:
    try:
        response = client.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise ConnectorTimeout(f"timeout fetching {url}") from exc
    except httpx.HTTPError as exc:
        raise ConnectorTimeout(f"http error fetching {url}: {exc}") from exc


def _post_json(
    client: httpx.Client,
    url: str,
    *,
    payload: Mapping[str, Any],
    headers: Mapping[str, str] | None = None,
    timeout: float,
) -> Any:
    try:
        response = client.post(url, json=dict(payload), headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise ConnectorTimeout(f"timeout posting {url}") from exc
    except httpx.HTTPError as exc:
        raise ConnectorTimeout(f"http error posting {url}: {exc}") from exc


class OpenLibraryLiveConnector:
    """Live Open Library ``search.json`` — metadata + work URL only."""

    name = ConnectorName.OPEN_LIBRARY

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_LIVE_TIMEOUT_SECONDS,
        limit: int = DEFAULT_LIVE_LIMIT,
    ) -> None:
        self._client = client
        self._timeout = timeout_seconds
        self._limit = limit

    def search(self, query: str) -> list[ConnectorHit]:
        needle = query.strip()
        if not needle:
            return []
        client, owned = _owned_or_shared_client(self._client)
        try:
            payload = _get_json(
                client,
                OPEN_LIBRARY_SEARCH_URL,
                params={
                    "q": needle,
                    "limit": self._limit,
                    "fields": "key,title,author_name,first_publish_year,isbn",
                },
                timeout=self._timeout,
            )
        finally:
            if owned:
                client.close()
        docs = payload.get("docs") if isinstance(payload, dict) else None
        if not isinstance(docs, list):
            return []
        hits: list[ConnectorHit] = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            key = doc.get("key")
            title = doc.get("title")
            if not key or not title:
                continue
            work_key = str(key)
            url = f"https://openlibrary.org{work_key}"
            refuse_banned_url(url)
            authors = [str(a) for a in (doc.get("author_name") or []) if a]
            isbn_raw = doc.get("isbn")
            isbn = None
            if isinstance(isbn_raw, list) and isbn_raw:
                isbn = str(isbn_raw[0])
            year = doc.get("first_publish_year")
            hits.append(
                ConnectorHit(
                    work_key=work_key,
                    title=str(title),
                    authors=authors,
                    provider=self.name,
                    provider_url=url,
                    full_text_available=False,
                    rights_status="metadata_only",
                    publish_year=int(year) if isinstance(year, int) else None,
                    isbn=isbn,
                )
            )
        return hits


class GutenbergLiveConnector:
    """Live Gutendex catalog search — links to Project Gutenberg ebook pages."""

    name = ConnectorName.GUTENBERG

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_LIVE_TIMEOUT_SECONDS,
        limit: int = DEFAULT_LIVE_LIMIT,
    ) -> None:
        self._client = client
        self._timeout = timeout_seconds
        self._limit = limit

    def search(self, query: str) -> list[ConnectorHit]:
        needle = query.strip()
        if not needle:
            return []
        client, owned = _owned_or_shared_client(self._client)
        try:
            payload = _get_json(
                client,
                GUTENDEX_BOOKS_URL,
                params={"search": needle},
                timeout=self._timeout,
            )
        finally:
            if owned:
                client.close()
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            return []
        hits: list[ConnectorHit] = []
        for book in results[: self._limit]:
            if not isinstance(book, dict):
                continue
            book_id = book.get("id")
            title = book.get("title")
            if book_id is None or not title:
                continue
            url = f"https://www.gutenberg.org/ebooks/{book_id}"
            refuse_banned_url(url)
            authors: list[str] = []
            for person in book.get("authors") or []:
                if isinstance(person, dict) and person.get("name"):
                    authors.append(str(person["name"]))
            formats = book.get("formats") if isinstance(book.get("formats"), dict) else {}
            has_text = any(
                isinstance(mime, str) and mime.startswith("text/plain") for mime in formats
            )
            copyrighted = book.get("copyright")
            rights = "public_domain" if copyrighted is False else "metadata_only"
            hits.append(
                ConnectorHit(
                    work_key=f"pg-{book_id}",
                    title=str(title),
                    authors=authors,
                    provider=self.name,
                    provider_url=url,
                    full_text_available=bool(has_text) and copyrighted is False,
                    rights_status=rights,
                )
            )
        return hits


class GoogleBooksLiveConnector:
    """Official Google Books volumes search — discovery links only, never RAG ingest."""

    name = ConnectorName.GOOGLE_BOOKS

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_LIVE_TIMEOUT_SECONDS,
        limit: int = DEFAULT_LIVE_LIMIT,
    ) -> None:
        self._api_key = api_key.strip()
        self._client = client
        self._timeout = timeout_seconds
        self._limit = limit

    def search(self, query: str) -> list[ConnectorHit]:
        needle = query.strip()
        if not needle:
            return []
        if not self._api_key:
            raise ConnectorTimeout("GOOGLE_BOOKS_API_KEY unset")
        client, owned = _owned_or_shared_client(self._client)
        try:
            payload = _get_json(
                client,
                GOOGLE_BOOKS_VOLUMES_URL,
                params={"q": needle, "maxResults": self._limit, "key": self._api_key},
                timeout=self._timeout,
            )
        finally:
            if owned:
                client.close()
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []
        hits: list[ConnectorHit] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            volume_id = item.get("id")
            info = item.get("volumeInfo") if isinstance(item.get("volumeInfo"), dict) else {}
            title = info.get("title")
            if not volume_id or not title:
                continue
            info_link = info.get("infoLink") or f"https://books.google.com/books?id={volume_id}"
            refuse_banned_url(str(info_link))
            authors = [str(a) for a in (info.get("authors") or []) if a]
            year_raw = str(info.get("publishedDate") or "")[:4]
            year = int(year_raw) if year_raw.isdigit() else None
            isbn = None
            for ident in info.get("industryIdentifiers") or []:
                if isinstance(ident, dict) and ident.get("type") in {"ISBN_13", "ISBN_10"}:
                    isbn = str(ident.get("identifier"))
                    break
            # Never claim Google preview/ebook as HomeLib full text.
            hits.append(
                ConnectorHit(
                    work_key=f"gbooks-{volume_id}",
                    title=str(title),
                    authors=authors,
                    provider=self.name,
                    provider_url=str(info_link),
                    full_text_available=False,
                    rights_status="metadata_only",
                    publish_year=year,
                    isbn=isbn,
                )
            )
        return hits


def _hardcover_authors(raw: Any) -> list[str]:
    authors: list[str] = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, str) and entry.strip():
                authors.append(entry.strip())
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("author")
                if isinstance(name, dict):
                    name = name.get("name")
                if isinstance(name, str) and name.strip():
                    authors.append(name.strip())
    return authors


def _hardcover_hits_from_results(results: Any, *, limit: int) -> list[ConnectorHit]:
    rows: list[Any]
    if isinstance(results, dict):
        maybe = results.get("hits") or results.get("books") or results.get("items")
        rows = maybe if isinstance(maybe, list) else []
        if not rows and results.get("title"):
            rows = [results]
    elif isinstance(results, list):
        rows = results
    else:
        return []

    hits: list[ConnectorHit] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        # Typesense-style hits nest document fields under "document".
        doc = row.get("document") if isinstance(row.get("document"), dict) else row
        title = doc.get("title")
        slug = doc.get("slug")
        book_id = doc.get("id")
        if not title or not slug:
            continue
        url = f"https://hardcover.app/books/{slug}"
        refuse_banned_url(url)
        authors = _hardcover_authors(
            doc.get("author_names")
            or doc.get("authors")
            or doc.get("cached_contributors")
            or doc.get("contributions")
        )
        work_key = f"hardcover-{book_id}" if book_id is not None else f"hardcover-{slug}"
        hits.append(
            ConnectorHit(
                work_key=str(work_key),
                title=str(title),
                authors=authors,
                provider=ConnectorName.HARDCOVER,
                provider_url=url,
                full_text_available=False,
                rights_status="metadata_only",
            )
        )
    return hits


class HardcoverLiveConnector:
    """Hardcover GraphQL book search — metadata + hardcover.app URL; no review ingest."""

    name = ConnectorName.HARDCOVER

    def __init__(
        self,
        *,
        api_token: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_LIVE_TIMEOUT_SECONDS,
        limit: int = 5,
    ) -> None:
        token = api_token.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        self._api_token = token
        self._client = client
        self._timeout = timeout_seconds
        self._limit = limit

    def search(self, query: str) -> list[ConnectorHit]:
        needle = query.strip()
        if not needle:
            return []
        if not self._api_token:
            raise ConnectorTimeout("HARDCOVER_API_TOKEN unset")
        client, owned = _owned_or_shared_client(self._client)
        headers = {
            "authorization": f"Bearer {self._api_token}",
            "content-type": "application/json",
            "User-Agent": connector_user_agent(),
        }
        try:
            payload = _post_json(
                client,
                HARDCOVER_GRAPHQL_URL,
                payload={
                    "query": _HARDCOVER_SEARCH_QUERY,
                    "variables": {"title": needle},
                },
                headers=headers,
                timeout=self._timeout,
            )
        finally:
            if owned:
                client.close()
        if not isinstance(payload, dict):
            return []
        if payload.get("errors"):
            raise ConnectorTimeout(f"hardcover graphql errors: {payload['errors']}")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        search = data.get("search") if isinstance(data.get("search"), dict) else {}
        return _hardcover_hits_from_results(search.get("results"), limit=self._limit)
