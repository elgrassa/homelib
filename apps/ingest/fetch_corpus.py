"""Shelf fetcher — see specs/corpus.md.

Downloads the public-domain books listed in ``data/manifest.yaml`` into
``data/books/`` (git-ignored), verifies each download's sha256 against the
pinned manifest value, and strips Project Gutenberg's license boilerplate
so it never pollutes retrieval.

Scope note (WP-08): this script stops at hash-verified, boilerplate-stripped
text sitting on disk. It does NOT build ``data/corpus_snapshot.jsonl.gz`` —
that lands in a later work package, once every format parser
(epub/pdf/txt/djvu) is final and ``homelib_core.normalize.parse_file`` can be
trusted to run over the whole shelf.
"""

import argparse
import hashlib
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.yaml"
BOOKS_DIR = REPO_ROOT / "data" / "books"

GUTENBERG_START_MARKER = "*** START OF THE PROJECT GUTENBERG EBOOK"
GUTENBERG_END_MARKER = "*** END OF THE PROJECT GUTENBERG EBOOK"

USER_AGENT = "homelib-ingest/0.1 (+https://github.com/elgrassa/homelib)"


@dataclass(frozen=True)
class ManifestEntry:
    """One row of ``data/manifest.yaml``."""

    book_id: str
    title: str
    authors: list[str]
    language: str
    source_url: str
    sha256: str
    format: str
    license_note: str


@dataclass(frozen=True)
class FetchOutcome:
    """Result of fetching or verifying a single manifest entry."""

    book_id: str
    ok: bool
    detail: str


def load_manifest(path: Path = MANIFEST_PATH) -> list[ManifestEntry]:
    """Parse ``data/manifest.yaml`` into typed entries."""
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [ManifestEntry(**row) for row in raw]


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strip_gutenberg_boilerplate(raw_text: str) -> str:
    """Cut everything before the START marker line and after the END marker line.

    Markers are matched case-insensitively. A side with no marker present is
    left untouched (some very old Project Gutenberg texts, and any non-PG
    source, don't carry them).
    """
    text = raw_text
    lower = text.lower()
    start_idx = lower.find(GUTENBERG_START_MARKER.lower())
    if start_idx != -1:
        line_end = text.find("\n", start_idx)
        text = text[line_end + 1 :] if line_end != -1 else ""

    lower = text.lower()
    end_idx = lower.find(GUTENBERG_END_MARKER.lower())
    if end_idx != -1:
        text = text[:end_idx]

    return text.strip("\n")


def fetch_one(client: httpx.Client, entry: ManifestEntry, books_dir: Path) -> FetchOutcome:
    """Download, hash-verify, and (for txt) boilerplate-strip one manifest entry.

    On a sha256 mismatch nothing is written to ``books_dir`` — one bad mirror
    must not block the rest of the shelf, and a half-verified file on disk is
    worse than none.
    """
    try:
        response = client.get(entry.source_url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("download failed for %s: %s", entry.book_id, exc)
        return FetchOutcome(entry.book_id, ok=False, detail=f"download failed: {exc}")

    content = response.content
    actual_sha = sha256_of_bytes(content)
    if actual_sha != entry.sha256:
        logger.warning(
            "sha256 mismatch for %s: expected %s, got %s",
            entry.book_id,
            entry.sha256,
            actual_sha,
        )
        return FetchOutcome(
            entry.book_id,
            ok=False,
            detail=f"sha256 mismatch: expected {entry.sha256}, got {actual_sha}",
        )

    books_dir.mkdir(parents=True, exist_ok=True)
    dest = books_dir / f"{entry.book_id}.{entry.format}"
    dest.write_bytes(content)

    if entry.format == "txt":
        clean_dest = books_dir / f"{entry.book_id}.clean.txt"
        clean_dest.write_text(strip_gutenberg_boilerplate(response.text), encoding="utf-8")

    return FetchOutcome(entry.book_id, ok=True, detail=f"saved {dest.name}")


def run_fetch(
    entries: list[ManifestEntry],
    books_dir: Path = BOOKS_DIR,
    client: httpx.Client | None = None,
) -> list[FetchOutcome]:
    """Fetch every manifest entry, continuing past individual failures."""
    owns_client = client is None
    active_client = client or httpx.Client(headers={"User-Agent": USER_AGENT})
    try:
        return [fetch_one(active_client, entry, books_dir) for entry in entries]
    finally:
        if owns_client:
            active_client.close()


def run_verify(entries: list[ManifestEntry], books_dir: Path = BOOKS_DIR) -> list[FetchOutcome]:
    """Re-hash whatever is already on disk against the manifest. Touches no network."""
    results: list[FetchOutcome] = []
    for entry in entries:
        dest = books_dir / f"{entry.book_id}.{entry.format}"
        if not dest.exists():
            results.append(FetchOutcome(entry.book_id, ok=False, detail="not downloaded"))
            continue
        actual = sha256_of_file(dest)
        if actual != entry.sha256:
            results.append(
                FetchOutcome(
                    entry.book_id,
                    ok=False,
                    detail=f"sha256 mismatch: expected {entry.sha256}, got {actual}",
                )
            )
        else:
            results.append(FetchOutcome(entry.book_id, ok=True, detail="ok"))
    return results


def _report(results: list[FetchOutcome]) -> int:
    failures = [r for r in results if not r.ok]
    for r in results:
        status = "OK" if r.ok else "FAIL"
        print(f"[{status}] {r.book_id}: {r.detail}")
    print(f"{len(results) - len(failures)}/{len(results)} verified")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--books-dir", type=Path, default=BOOKS_DIR)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fetch", action="store_true", help="download every manifest entry")
    group.add_argument("--verify-only", action="store_true", help="re-hash what is already on disk")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    entries = load_manifest(args.manifest)

    if args.fetch:
        results = run_fetch(entries, args.books_dir)
    else:
        results = run_verify(entries, args.books_dir)

    return _report(results)


if __name__ == "__main__":
    sys.exit(main())
