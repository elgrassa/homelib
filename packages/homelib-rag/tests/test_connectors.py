"""Behavioural tests for lawful catalog federation — specs/connectors.md.

Fixtures under ``tests/fixtures/connectors/``; no network in CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from homelib_rag.connectors import (
    ConnectorHit,
    ConnectorName,
    FixtureConnector,
    SlowConnector,
    federate_connectors,
    federate_hits,
    load_fixture_hits,
    refuse_banned_url,
)
from pydantic import ValidationError

_FIXTURES = Path(__file__).parent / "fixtures" / "connectors"


def test_dedup_keeps_attributions() -> None:
    ol = FixtureConnector(ConnectorName.OPEN_LIBRARY, _FIXTURES / "open_library.jsonl")
    gutenberg = FixtureConnector(ConnectorName.GUTENBERG, _FIXTURES / "gutenberg.jsonl")
    standard = FixtureConnector(ConnectorName.STANDARD_EBOOKS, _FIXTURES / "standard_ebooks.jsonl")

    result = federate_connectors([ol, gutenberg, standard], "meditations")

    assert result.unique_count == 1
    meditations = result.items[0]
    assert meditations.title == "Meditations"
    providers = {attr.provider for attr in meditations.attributions}
    assert providers == {
        ConnectorName.OPEN_LIBRARY,
        ConnectorName.GUTENBERG,
        ConnectorName.STANDARD_EBOOKS,
    }
    assert len(meditations.attributions) == 3


def test_timeout_degrades_not_fails() -> None:
    ol = FixtureConnector(ConnectorName.OPEN_LIBRARY, _FIXTURES / "open_library.jsonl")

    result = federate_connectors([SlowConnector(), ol], "republic")

    assert result.degraded is True
    assert result.unique_count >= 1
    assert result.items[0].title == "The Republic"
    assert "open_library" in result.approximate_provider_counts
    assert "standard_ebooks" not in result.approximate_provider_counts


def test_unique_count_not_provider_sum() -> None:
    ol_path = _FIXTURES / "open_library.jsonl"
    pg_path = _FIXTURES / "gutenberg.jsonl"
    ol_hits = load_fixture_hits(ol_path, provider=ConnectorName.OPEN_LIBRARY)
    pg_hits = load_fixture_hits(pg_path, provider=ConnectorName.GUTENBERG)
    assert len(ol_hits) == 3
    assert len(pg_hits) == 3

    items = federate_hits([*ol_hits, *pg_hits])

    assert len(items) == 4
    assert len(ol_hits) + len(pg_hits) == 6
    assert len(items) != len(ol_hits) + len(pg_hits)


def test_ambiguous_editions_never_merge() -> None:
    ambiguous_path = _FIXTURES / "ambiguous_editions.jsonl"
    hits = load_fixture_hits(ambiguous_path, provider=ConnectorName.OPEN_LIBRARY)

    merged = federate_hits(hits)

    assert len(merged) == 2
    assert all(item.title == "Principles of Economics" for item in merged)
    assert {item.work_key for item in merged} == {"/works/OL401W", "/works/OL402W"}
    assert all(len(item.attributions) == 1 for item in merged)


def test_refuse_banned_host_raises() -> None:
    with pytest.raises(ValueError, match="banned"):
        refuse_banned_url("https://annas-archive.org/search?q=test")


def test_fixture_connector_empty_query_returns_no_hits() -> None:
    connector = FixtureConnector(ConnectorName.OPEN_LIBRARY, _FIXTURES / "open_library.jsonl")
    assert connector.search("   ") == []


def test_connector_hit_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ConnectorHit(
            work_key="/works/OL1W",
            title="T",
            authors=["A"],
            provider=ConnectorName.OPEN_LIBRARY,
            provider_url="https://openlibrary.org/works/OL1W",
            full_text_available=False,
            rights_status="metadata_only",
            unexpected_field=True,  # type: ignore[call-arg]
        )
