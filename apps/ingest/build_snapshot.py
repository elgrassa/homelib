"""Build the committed corpus snapshot — see specs/corpus.md.

Parses every manifest entry's boilerplate-stripped text into a `BookDoc` and
writes them all to `data/corpus_snapshot.jsonl.gz`, one book per line.

The snapshot is committed so a reviewer never has to re-download 18 books from
Project Gutenberg to run this project: `docker compose run --rm ingest` reads
the snapshot and loads Postgres, entirely offline. `fetch_corpus.py` remains
the provenance trail — the snapshot is derived from it, not a substitute.
"""

import argparse
import gzip
import json
from pathlib import Path

from homelib_core.models import BookDoc
from homelib_core.normalize import parse_file

from apps.ingest.fetch_corpus import BOOKS_DIR, ManifestEntry, load_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "data" / "corpus_snapshot.jsonl.gz"


def _clean_text_path(entry: ManifestEntry, books_dir: Path) -> Path:
    """Path to the boilerplate-stripped text `fetch_corpus.py --fetch` wrote."""
    return books_dir / f"{entry.book_id}.clean.txt"


def build_book(entry: ManifestEntry, books_dir: Path | None = None) -> BookDoc:
    """Parse one manifest entry into a `BookDoc` carrying its manifest metadata.

    `parse_file` derives title and authors from the filename, which is wrong for
    a real book — the manifest is the authority for those, so they are applied
    over the parsed result rather than guessed from a slug.
    """
    # Resolved at call time, not bound as a default: a default argument is
    # captured at import, which silently ignores any later reconfiguration and
    # makes the function untestable without touching the real data directory.
    path = _clean_text_path(entry, books_dir if books_dir is not None else BOOKS_DIR)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing — run `uv run python apps/ingest/fetch_corpus.py --fetch` first"
        )

    doc, _extraction = parse_file(path)
    return doc.model_copy(
        update={
            "book_id": entry.book_id,
            "title": entry.title,
            "authors": entry.authors,
            "language": entry.language,
            "source_url": entry.source_url,
            "license_note": entry.license_note,
        }
    )


def build_snapshot(
    manifest_path: Path | None = None,
    books_dir: Path | None = None,
    out_path: Path | None = None,
) -> int:
    """Parse every manifest entry and write the gzipped snapshot. Returns book count."""
    out_path = out_path if out_path is not None else SNAPSHOT_PATH
    entries = load_manifest() if manifest_path is None else load_manifest(manifest_path)

    docs: list[BookDoc] = []
    for entry in entries:
        doc = build_book(entry, books_dir)
        docs.append(doc)
        print(f"[OK] {entry.book_id}: {len(doc.blocks)} blocks, {len(doc.canonical_text)} chars")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # The snapshot is committed, so its bytes must depend on the corpus and
    # nothing else. gzip stamps BOTH an mtime and the output filename into its
    # header, either of which would make an unchanged corpus show up as a 6 MB
    # diff — so mtime is zeroed and the filename is left empty deliberately.
    with (
        out_path.open("wb") as fh,
        gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as raw,
    ):
        for doc in docs:
            line = json.dumps(doc.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            raw.write(line.encode("utf-8") + b"\n")
    return len(docs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the committed corpus snapshot.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    count = build_snapshot(out_path=args.out)
    args.out = args.out if args.out is not None else SNAPSHOT_PATH
    size_mb = args.out.stat().st_size / 1_000_000
    print(f"{count} books -> {args.out} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
