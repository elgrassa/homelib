"""Tests for apps/ingest/fetch_corpus.py — see specs/corpus.md named red tests."""

import hashlib
from pathlib import Path

import httpx
import pytest
import respx
import yaml

from apps.ingest.fetch_corpus import (
    ManifestEntry,
    fetch_one,
    load_manifest,
    main,
    run_fetch,
    run_verify,
    sha256_of_bytes,
    sha256_of_file,
    strip_gutenberg_boilerplate,
)

GUTENBERG_FIXTURE = """\
The Project Gutenberg eBook of Some Old Book
This ebook is for the use of anyone anywhere in the United States and
most other parts of the world at no cost and with almost no restrictions
whatsoever.

Title: Some Old Book
Author: A. N. Author

*** START OF THE PROJECT GUTENBERG EBOOK SOME OLD BOOK ***

CHAPTER I

This is the real body text of the book. It should survive stripping.

CHAPTER II

More real body text.

*** END OF THE PROJECT GUTENBERG EBOOK SOME OLD BOOK ***

*** END OF THIS PROJECT GUTENBERG EBOOK ***

This is licence boilerplate that must not survive stripping. Full terms at
gutenberg.org.
"""

EXPECTED_STRIPPED = """\
CHAPTER I

This is the real body text of the book. It should survive stripping.

CHAPTER II

More real body text.""".strip("\n")


def _entry(
    book_id: str, sha256: str, source_url: str = "https://example.org/book.txt"
) -> ManifestEntry:
    return ManifestEntry(
        book_id=book_id,
        title="Title",
        authors=["Author"],
        language="en",
        source_url=source_url,
        sha256=sha256,
        format="txt",
        license_note="Public domain",
    )


def test_gutenberg_boilerplate_stripped() -> None:
    stripped = strip_gutenberg_boilerplate(GUTENBERG_FIXTURE)
    assert stripped == EXPECTED_STRIPPED
    assert "licence boilerplate" not in stripped
    assert "This ebook is for the use of anyone" not in stripped


def test_strip_boilerplate_no_markers_returns_unchanged() -> None:
    text = "Just plain text with no Gutenberg markers at all."
    assert strip_gutenberg_boilerplate(text) == text


def test_manifest_shas_match_downloaded_files(tmp_path: Path) -> None:
    books_dir = tmp_path / "books"
    books_dir.mkdir()
    content = b"hello world, this is a fixture book file\n"
    real_sha = hashlib.sha256(content).hexdigest()
    (books_dir / "book-one.txt").write_bytes(content)

    entries = [_entry("book-one", real_sha)]
    results = run_verify(entries, books_dir)
    assert results[0].ok is True

    # tamper: flip a byte, sha must no longer match
    tampered = bytearray(content)
    tampered[0] ^= 0xFF
    (books_dir / "book-one.txt").write_bytes(bytes(tampered))

    results = run_verify(entries, books_dir)
    assert results[0].ok is False
    assert "mismatch" in results[0].detail

    exit_code = main(
        [
            "--verify-only",
            "--manifest",
            str(_write_manifest(tmp_path, entries)),
            "--books-dir",
            str(books_dir),
        ]
    )
    assert exit_code != 0


def test_verify_only_needs_no_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--verify-only only re-hashes local files; it must never construct an httpx client."""
    books_dir = tmp_path / "books"
    books_dir.mkdir()
    content = b"network-free verification fixture\n"
    real_sha = hashlib.sha256(content).hexdigest()
    (books_dir / "book-one.txt").write_bytes(content)
    entries = [_entry("book-one", real_sha)]

    def _boom(*args: object, **kwargs: object) -> httpx.Client:
        raise AssertionError("run_verify must not touch the network")

    monkeypatch.setattr(httpx, "Client", _boom)

    results = run_verify(entries, books_dir)
    assert results[0].ok is True


def test_verify_missing_file_fails(tmp_path: Path) -> None:
    entries = [_entry("missing-book", "0" * 64)]
    results = run_verify(entries, tmp_path / "books")
    assert results[0].ok is False
    assert results[0].detail == "not downloaded"


@respx.mock
def test_fetch_download_verify_and_strip(tmp_path: Path) -> None:
    content = GUTENBERG_FIXTURE.encode("utf-8")
    real_sha = sha256_of_bytes(content)
    entry = _entry("good-book", real_sha, source_url="https://example.org/good-book.txt")
    respx.get(entry.source_url).mock(return_value=httpx.Response(200, content=content))

    books_dir = tmp_path / "books"
    results = run_fetch([entry], books_dir)

    assert results[0].ok is True
    raw_path = books_dir / "good-book.txt"
    clean_path = books_dir / "good-book.clean.txt"
    assert raw_path.read_bytes() == content
    assert sha256_of_file(raw_path) == real_sha
    assert clean_path.read_text(encoding="utf-8") == EXPECTED_STRIPPED


@respx.mock
def test_fetch_sha_mismatch_continues_to_next_entry(tmp_path: Path) -> None:
    bad_entry = _entry("bad-book", "f" * 64, source_url="https://example.org/bad-book.txt")
    good_content = b"good content matches its hash\n"
    good_sha = sha256_of_bytes(good_content)
    good_entry = _entry("good-book2", good_sha, source_url="https://example.org/good-book2.txt")

    respx.get(bad_entry.source_url).mock(return_value=httpx.Response(200, content=b"wrong bytes"))
    respx.get(good_entry.source_url).mock(return_value=httpx.Response(200, content=good_content))

    books_dir = tmp_path / "books"
    results = run_fetch([bad_entry, good_entry], books_dir)

    assert results[0].ok is False
    assert "mismatch" in results[0].detail
    assert not (books_dir / "bad-book.txt").exists()

    assert results[1].ok is True
    assert (books_dir / "good-book2.txt").exists()


@respx.mock
def test_fetch_http_error_is_reported_not_raised(tmp_path: Path) -> None:
    entry = _entry("unreachable-book", "0" * 64, source_url="https://example.org/nope.txt")
    respx.get(entry.source_url).mock(return_value=httpx.Response(404))

    results = run_fetch([entry], tmp_path / "books")
    assert results[0].ok is False
    assert "download failed" in results[0].detail


@respx.mock
def test_fetch_one_with_shared_client(tmp_path: Path) -> None:
    content = b"shared client content\n"
    sha = sha256_of_bytes(content)
    entry = _entry("shared-client-book", sha, source_url="https://example.org/shared.txt")
    respx.get(entry.source_url).mock(return_value=httpx.Response(200, content=content))

    with httpx.Client() as client:
        outcome = fetch_one(client, entry, tmp_path / "books")
    assert outcome.ok is True


def test_load_manifest_round_trip(tmp_path: Path) -> None:
    entries = [_entry("book-a", "a" * 64), _entry("book-b", "b" * 64)]
    manifest_path = _write_manifest(tmp_path, entries)
    loaded = load_manifest(manifest_path)
    assert [e.book_id for e in loaded] == ["book-a", "book-b"]


def test_load_manifest_accepts_rights_status_used_by_committed_manifest(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, [_entry("book-a", "a" * 64)])
    rows = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    rows[0]["rights_status"] = "public_domain"
    manifest_path.write_text(yaml.safe_dump(rows), encoding="utf-8")

    loaded = load_manifest(manifest_path)

    assert loaded[0].rights_status == "public_domain"


def test_main_requires_a_mode(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--manifest", str(tmp_path / "manifest.yaml")])


def _write_manifest(tmp_path: Path, entries: list[ManifestEntry]) -> Path:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump([e.__dict__ for e in entries], sort_keys=False), encoding="utf-8"
    )
    return manifest_path
