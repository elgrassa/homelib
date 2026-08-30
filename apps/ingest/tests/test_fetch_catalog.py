"""Tests for apps/ingest/fetch_catalog.py — see specs/corpus.md named red tests."""

import json
import re
from pathlib import Path

import httpx
import pytest
import respx

from apps.ingest.fetch_catalog import (
    OPEN_LIBRARY_SEARCH_URL,
    fetch_catalog_entries,
    main,
    write_catalog,
)

INGEST_DIR = Path(__file__).resolve().parents[1]


def _ol_page(docs: list[dict[str, object]]) -> dict[str, object]:
    return {"numFound": len(docs), "start": 0, "docs": docs}


def _doc(key: str, title: str, subject: list[str] | None = None) -> dict[str, object]:
    return {
        "key": key,
        "title": title,
        "author_name": ["Some Author"],
        "subject": subject if subject is not None else ["general"],
        "first_publish_year": 2001,
    }


@respx.mock
def test_catalog_dedupes_by_ol_key() -> None:
    """Two subject slices returning the same ol_key must collapse to one entry."""
    shared_doc = _doc("/works/OL123W", "Deep Learning", subject=["machine learning"])
    route = respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=_ol_page([shared_doc]))
    )

    with httpx.Client() as client:
        entries = fetch_catalog_entries(
            client,
            subjects=["machine learning", "deep learning"],
            max_pages_per_subject=1,
            sleep_seconds=0,
        )

    assert route.call_count == 2
    assert len(entries) == 1
    assert entries[0].ol_key == "/works/OL123W"
    assert entries[0].title == "Deep Learning"
    assert entries[0].provenance_note


@respx.mock
def test_fetch_paginates_until_short_page() -> None:
    full_page = _ol_page([_doc(f"/works/OL{i}W", f"Book {i}") for i in range(100)])
    short_page = _ol_page([_doc("/works/OL999W", "Last Book")])

    respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json=full_page),
            httpx.Response(200, json=short_page),
        ]
    )

    with httpx.Client() as client:
        entries = fetch_catalog_entries(
            client, subjects=["management"], max_pages_per_subject=3, page_size=100, sleep_seconds=0
        )

    assert len(entries) == 101


@respx.mock
def test_fetch_stops_at_max_pages_per_subject() -> None:
    # Two distinct full pages: if the cap didn't apply, fetch_catalog_entries would
    # request a 3rd page from a route with no more queued responses and raise.
    page_one = _ol_page([_doc(f"/works/OL{i}W", f"Book {i}") for i in range(100)])
    page_two = _ol_page([_doc(f"/works/OL{i}W", f"Book {i}") for i in range(100, 200)])
    respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json=page_one),
            httpx.Response(200, json=page_two),
        ]
    )

    with httpx.Client() as client:
        entries = fetch_catalog_entries(
            client, subjects=["management"], max_pages_per_subject=2, page_size=100, sleep_seconds=0
        )

    assert len(entries) == 200


@respx.mock
def test_subject_failure_degrades_not_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A subject that exhausts retries is skipped; other subjects still get fetched."""
    import apps.ingest.fetch_catalog as fetch_catalog_module

    monkeypatch.setattr(fetch_catalog_module.time, "sleep", lambda _seconds: None)

    good_doc = _doc("/works/OL1W", "Good Book")
    respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.ConnectError("boom"),
            httpx.ConnectError("boom"),
            httpx.Response(200, json=_ol_page([good_doc])),
        ]
    )

    with httpx.Client() as client:
        entries = fetch_catalog_entries(
            client,
            subjects=["broken subject", "good subject"],
            max_pages_per_subject=1,
            sleep_seconds=0,
        )

    assert len(entries) == 1
    assert entries[0].ol_key == "/works/OL1W"


@respx.mock
def test_doc_missing_key_or_title_is_skipped() -> None:
    docs = [
        {"key": "/works/OL1W", "title": "Has Title", "author_name": [], "subject": []},
        {"key": None, "title": "No Key", "author_name": [], "subject": []},
        {"key": "/works/OL2W", "title": "", "author_name": [], "subject": []},
    ]
    respx.get(OPEN_LIBRARY_SEARCH_URL).mock(return_value=httpx.Response(200, json=_ol_page(docs)))

    with httpx.Client() as client:
        entries = fetch_catalog_entries(
            client, subjects=["x"], max_pages_per_subject=1, sleep_seconds=0
        )

    assert len(entries) == 1
    assert entries[0].ol_key == "/works/OL1W"


def test_write_catalog_header_and_lines(tmp_path: Path) -> None:
    with httpx.Client() as client, respx.mock:
        respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=_ol_page([_doc("/works/OL1W", "A Book")]))
        )
        entries = fetch_catalog_entries(
            client, subjects=["x"], max_pages_per_subject=1, sleep_seconds=0
        )

    out = tmp_path / "catalog.jsonl"
    write_catalog(entries, out)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    header = json.loads(lines[0])
    assert "_provenance" in header
    row = json.loads(lines[1])
    assert row["ol_key"] == "/works/OL1W"
    assert row["title"] == "A Book"
    assert row["description"] is None


@respx.mock
def test_main_writes_catalog_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.ingest.fetch_catalog as fetch_catalog_module

    monkeypatch.setattr(fetch_catalog_module, "CATALOG_SUBJECTS", ["x", "y"])
    respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=_ol_page([_doc("/works/OL1W", "A Book")]))
    )

    out_path = tmp_path / "catalog.jsonl"
    exit_code = main(["--out", str(out_path)])

    assert exit_code == 0
    assert out_path.exists()
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_kaggle_source_absent_from_pipeline() -> None:
    """No import, URL, or filename in apps/ingest may reference Kaggle as a data source.

    fetch_catalog.py's module docstring necessarily contains the word "Kaggle" to
    explain *why* it's banned — specs/corpus.md scopes this guard to actual usage
    (import / URL / filename), not to that explanatory prose, so this test flags
    only functional footprints of a real Kaggle dependency.
    """
    offenders: list[str] = []
    usage_patterns = (
        re.compile(r"\bimport\s+kaggle\b"),
        re.compile(r"\bfrom\s+kaggle\b"),
        re.compile(r"kaggle\.com"),
        re.compile(r"kagglehub"),
    )

    for path in INGEST_DIR.rglob("*.py"):
        if "tests" in path.relative_to(INGEST_DIR).parts:
            continue
        if "kaggle" in path.name.lower():
            offenders.append(f"filename: {path}")
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lowered = line.lower()
            if "kaggle" not in lowered:
                continue
            if any(pattern.search(lowered) for pattern in usage_patterns):
                offenders.append(f"{path}:{line_no}: {line.strip()}")

    assert not offenders, f"kaggle usage found: {offenders}"
