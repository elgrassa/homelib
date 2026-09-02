"""Lawful catalog federation — see specs/connectors.md.

Fixtures-first: production wiring may call live Open Library outside CI;
in tests every provider reads JSONL fixtures under ``data/`` or test dirs.
Provider timeouts degrade the Discover payload (``degraded=True``) without
failing the whole federation.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BANNED_CONNECTOR_HOSTS",
    "ConnectorHit",
    "ConnectorName",
    "ConnectorTimeout",
    "DiscoverResult",
    "FederatedItem",
    "ProviderAttribution",
    "federate_connectors",
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


class ConnectorName(StrEnum):
    OPEN_LIBRARY = "open_library"
    STANDARD_EBOOKS = "standard_ebooks"
    GUTENBERG = "gutenberg"


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
    """Raised by a connector when its deadline is exceeded."""


class CatalogConnector(Protocol):
    name: ConnectorName

    def search(self, query: str) -> list[ConnectorHit]: ...


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
