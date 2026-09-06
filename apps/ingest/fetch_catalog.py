"""Open Library catalog fetcher — see specs/corpus.md.

Pulls curated subject slices from Open Library's ``search.json`` endpoint
into ``data/catalog.jsonl``: one ``CatalogEntry``-shaped JSON object per
line (plus a leading ``_provenance`` header line), deduped by Open Library
work key (``ol_key``). Metadata-only — no book text is fetched here, only
title/author/subject/year context for the roadmap feature.

BANNED — non-negotiable: the Kaggle "15K+ Books Across 100+ Categories"
dataset is never a source here, in any form, including a build-time
re-download. Its own dataset description states it was scraped from the
Google Books API, whose Terms of Service bar scraping, building a
derivative database, making permanent copies, and redistributing results —
the uploader's "CC0" badge on Kaggle cannot re-license data that was never
Google's, or the uploader's, to relicense. The Google Books API and the
UCSD Goodreads Book Graph are equally unusable here, for the same class of
redistribution restriction. This pipeline only ever talks to
openlibrary.org, whose search API is designed for exactly this kind of
programmatic, redistributable use.
"""

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from homelib_core.models import CatalogEntry
from pydantic import ValidationError

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "data" / "catalog.jsonl"

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
USER_AGENT = "homelib-ingest/0.1 (+https://github.com/elgrassa/homelib)"

# Roadmap-relevant subjects, each queried as search.json?q=subject:"<subject>".
# Never the 4 GB Open Library works dump.
CATALOG_SUBJECTS: list[str] = [
    "machine learning",
    "software engineering",
    "entrepreneurship",
    "management",
    "distributed systems",
    "deep learning",
    "data engineering",
    "product management",
    "technical writing",
    "system design",
    "algorithms",
    "data science",
    "personal finance",
    "statistics",
]

PAGE_SIZE = 100
MAX_PAGES_PER_SUBJECT = 3
MAX_ATTEMPTS = 3
REQUEST_SLEEP_SECONDS = 0.5
SEARCH_FIELDS = "key,title,author_name,subject,first_publish_year"


def _fetch_page(
    client: httpx.Client, subject: str, offset: int, *, page_size: int = PAGE_SIZE
) -> dict[str, Any]:
    """Fetch one page of results for ``subject``, retrying with backoff on failure."""
    params: dict[str, str | int] = {
        "q": f'subject:"{subject}"',
        "limit": page_size,
        "offset": offset,
        "fields": SEARCH_FIELDS,
    }
    last_exc: httpx.HTTPError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.get(OPEN_LIBRARY_SEARCH_URL, params=params, timeout=30.0)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning(
                "subject %r offset %d attempt %d/%d failed: %s",
                subject,
                offset,
                attempt,
                MAX_ATTEMPTS,
                exc,
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** (attempt - 1))
    assert last_exc is not None
    raise last_exc


def _doc_to_entry(doc: dict[str, Any], subject: str, fetched_at: str) -> CatalogEntry | None:
    key = doc.get("key")
    title = doc.get("title")
    if not key or not title:
        return None
    try:
        return CatalogEntry(
            ol_key=key,
            title=title,
            authors=doc.get("author_name") or [],
            subjects=doc.get("subject") or [],
            first_publish_year=doc.get("first_publish_year"),
            description=None,
            provenance_note=f'Open Library search.json, subject:"{subject}", fetched {fetched_at}',
        )
    except ValidationError as exc:
        logger.warning("skipping malformed Open Library doc %r: %s", key, exc)
        return None


def fetch_catalog_entries(
    client: httpx.Client,
    subjects: list[str] | None = None,
    *,
    max_pages_per_subject: int = MAX_PAGES_PER_SUBJECT,
    page_size: int = PAGE_SIZE,
    sleep_seconds: float = REQUEST_SLEEP_SECONDS,
) -> list[CatalogEntry]:
    """Fetch and dedupe (by ``ol_key``) catalog entries across every subject slice."""
    subjects = CATALOG_SUBJECTS if subjects is None else subjects
    fetched_at = datetime.now(UTC).date().isoformat()
    seen: dict[str, CatalogEntry] = {}

    for subject in subjects:
        offset = 0
        for _page in range(max_pages_per_subject):
            try:
                data = _fetch_page(client, subject, offset, page_size=page_size)
            except httpx.HTTPError as exc:
                logger.warning("giving up on subject %r after retries: %s", subject, exc)
                break

            docs = data.get("docs", [])
            if not docs:
                break

            for doc in docs:
                entry = _doc_to_entry(doc, subject, fetched_at)
                if entry is not None:
                    seen.setdefault(entry.ol_key, entry)

            offset += page_size
            if len(docs) < page_size:
                break
            time.sleep(sleep_seconds)

        time.sleep(sleep_seconds)

    return list(seen.values())


def write_catalog(entries: list[CatalogEntry], out_path: Path = CATALOG_PATH) -> None:
    """Write the provenance header line followed by one JSON line per entry."""
    fetched_at = datetime.now(UTC).date().isoformat()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        header = {
            "_provenance": (
                f"Open Library search.json, curated subject slices, fetched {fetched_at}"
            )
        }
        fh.write(json.dumps(header, ensure_ascii=False) + "\n")
        for entry in entries:
            fh.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=CATALOG_PATH)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        entries = fetch_catalog_entries(client)

    write_catalog(entries, args.out)
    print(f"wrote {len(entries)} catalog entries to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
