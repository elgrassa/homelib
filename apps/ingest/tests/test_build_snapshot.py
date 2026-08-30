"""Tests for the corpus snapshot builder.

The snapshot is the file reviewers actually ingest — `fetch_corpus.py` is the
provenance trail, but nobody re-downloads 18 books to try the project. So a
defect here reaches every reviewer, and this module shipped with no tests at
all until a coverage sweep caught it.
"""

import gzip
import json
import re
from pathlib import Path

import pytest
from homelib_core.models import BookDoc

from apps.ingest.build_snapshot import build_book, build_snapshot, main
from apps.ingest.fetch_corpus import ManifestEntry

_ENTRY = ManifestEntry(
    book_id="test-book",
    title="A Real Title, Not The Filename",
    authors=["Ada Lovelace", "Charles Babbage"],
    language="en",
    source_url="https://example.invalid/test.txt",
    sha256="0" * 64,
    format="txt",
    license_note="public domain",
)


def _write_clean_text(books_dir: Path, book_id: str = "test-book") -> Path:
    books_dir.mkdir(parents=True, exist_ok=True)
    path = books_dir / f"{book_id}.clean.txt"
    path.write_text(
        "CHAPTER I.\n\nThe first chapter says one thing.\n\n"
        "CHAPTER II.\n\nThe second chapter says another.\n",
        encoding="utf-8",
    )
    return path


def test_build_book_applies_manifest_metadata_over_parsed_guesses(tmp_path: Path) -> None:
    """The manifest is the authority for title and authors, not the filename.

    parse_file derives them by slugifying the file stem, which is fine for an
    ad-hoc file and wrong for a catalogued book. A citation that names the wrong
    author is worse than one that names none, and the answer path was already
    observed inventing an author when metadata was thin.
    """
    _write_clean_text(tmp_path)

    doc = build_book(_ENTRY, books_dir=tmp_path)

    assert doc.title == "A Real Title, Not The Filename"
    assert doc.authors == ["Ada Lovelace", "Charles Babbage"]
    assert doc.book_id == "test-book"
    assert doc.source_url == "https://example.invalid/test.txt"
    assert doc.license_note == "public domain"


def test_build_book_preserves_parsed_structure(tmp_path: Path) -> None:
    """Overriding metadata must not disturb blocks or the offset invariant."""
    _write_clean_text(tmp_path)

    doc = build_book(_ENTRY, books_dir=tmp_path)

    assert len(doc.blocks) == 2
    assert [b.section_path for b in doc.blocks] == [["CHAPTER I."], ["CHAPTER II."]]
    for block in doc.blocks:
        assert doc.canonical_text[block.char_start : block.char_end] == block.text


def test_build_book_missing_file_names_the_fix(tmp_path: Path) -> None:
    """A missing download must say how to get it, not raise a bare OSError."""
    with pytest.raises(FileNotFoundError, match=re.escape("fetch_corpus.py --fetch")):
        build_book(_ENTRY, books_dir=tmp_path)


def test_snapshot_round_trips_through_gzipped_jsonl(tmp_path: Path, monkeypatch) -> None:
    """Every line must reload as a BookDoc — the ingest side does exactly this."""
    books = tmp_path / "books"
    _write_clean_text(books)
    monkeypatch.setattr("apps.ingest.build_snapshot.load_manifest", lambda *a, **k: [_ENTRY])

    out = tmp_path / "snapshot.jsonl.gz"
    count = build_snapshot(books_dir=books, out_path=out)

    assert count == 1
    with gzip.open(out, "rt", encoding="utf-8") as fh:
        docs = [BookDoc.model_validate(json.loads(line)) for line in fh]
    assert len(docs) == 1
    assert docs[0].title == "A Real Title, Not The Filename"
    assert docs[0].blocks[0].section_path == ["CHAPTER I."]


def test_snapshot_is_byte_stable_across_rebuilds(tmp_path: Path, monkeypatch) -> None:
    """Rebuilding an unchanged corpus must produce an identical file.

    gzip stamps mtime by default, so without mtime=0 every rebuild would show
    as a 6 MB diff and the committed snapshot would churn on every run.
    """
    books = tmp_path / "books"
    _write_clean_text(books)
    monkeypatch.setattr("apps.ingest.build_snapshot.load_manifest", lambda *a, **k: [_ENTRY])

    first = tmp_path / "a.jsonl.gz"
    second = tmp_path / "b.jsonl.gz"
    build_snapshot(books_dir=books, out_path=first)
    build_snapshot(books_dir=books, out_path=second)

    assert first.read_bytes() == second.read_bytes()


def test_main_reports_and_exits_zero(tmp_path: Path, monkeypatch, capsys) -> None:
    books = tmp_path / "books"
    _write_clean_text(books)
    monkeypatch.setattr("apps.ingest.build_snapshot.load_manifest", lambda *a, **k: [_ENTRY])
    monkeypatch.setattr("apps.ingest.build_snapshot.BOOKS_DIR", books)

    out = tmp_path / "out.jsonl.gz"
    assert main(["--out", str(out)]) == 0
    assert "1 books ->" in capsys.readouterr().out
