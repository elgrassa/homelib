"""Red-first tests for `homelib_core.formats.txt` — see specs/formats.md.

Written before `formats/txt.py` exists and MUST fail (collection error /
ImportError) until it is implemented.
"""

import hashlib
from pathlib import Path

import pytest
from homelib_core.formats.txt import parse_txt
from homelib_core.models import make_block_id
from homelib_core.normalize import parse_file

_MARKDOWN_FIXTURE = """\
# Chapter One

Intro paragraph text here.
More intro text.

## Section A

Body of section A.

## Section B

Body of section B.

# Chapter Two

Second chapter text.
"""

_PLAINTEXT_FIXTURE = """\
INTRODUCTION

This is the intro paragraph.
It has two lines.

Body Section One

More body text here.
"""


def _assert_offsets_dense_and_stable(doc, book_id: str) -> None:  # type: ignore[no-untyped-def]
    for i, block in enumerate(doc.blocks):
        assert block.ordinal == i
        assert doc.canonical_text[block.char_start : block.char_end] == block.text
        assert block.block_id == make_block_id(book_id, block.section_path, block.ordinal)
        assert block.book_id == book_id


def test_parse_txt_markdown_heading_nesting_and_block_order(tmp_path: Path) -> None:
    path = tmp_path / "book.md"
    path.write_text(_MARKDOWN_FIXTURE, encoding="utf-8")

    doc, result = parse_txt(path, book_id="mybook")

    assert [b.section_path for b in doc.blocks] == [
        ["Chapter One"],
        ["Chapter One", "Section A"],
        ["Chapter One", "Section B"],
        ["Chapter Two"],
    ]
    assert [b.text for b in doc.blocks] == [
        "Intro paragraph text here.\nMore intro text.",
        "Body of section A.",
        "Body of section B.",
        "Second chapter text.",
    ]
    assert [b.ordinal for b in doc.blocks] == [0, 1, 2, 3]
    _assert_offsets_dense_and_stable(doc, "mybook")
    assert result.method == "native_text"


def test_parse_txt_plaintext_heading_heuristic(tmp_path: Path) -> None:
    path = tmp_path / "book.txt"
    path.write_text(_PLAINTEXT_FIXTURE, encoding="utf-8")

    doc, _result = parse_txt(path, book_id="mybook")

    assert [b.section_path for b in doc.blocks] == [
        ["INTRODUCTION"],
        ["Body Section One"],
    ]
    assert doc.blocks[0].text == "This is the intro paragraph.\nIt has two lines."
    assert doc.blocks[1].text == "More body text here."
    _assert_offsets_dense_and_stable(doc, "mybook")


def test_parse_txt_no_heading_is_single_block(tmp_path: Path) -> None:
    path = tmp_path / "flat.txt"
    path.write_text("just some plain body text\nacross two lines\n", encoding="utf-8")

    doc, _result = parse_txt(path, book_id="mybook")

    assert len(doc.blocks) == 1
    assert doc.blocks[0].section_path == []
    assert doc.blocks[0].provenance.anchor is None
    _assert_offsets_dense_and_stable(doc, "mybook")


def test_parse_txt_provenance_fields(tmp_path: Path) -> None:
    md_path = tmp_path / "book.md"
    md_path.write_text(_MARKDOWN_FIXTURE, encoding="utf-8")
    txt_path = tmp_path / "book.txt"
    txt_path.write_text(_PLAINTEXT_FIXTURE, encoding="utf-8")

    md_doc, _ = parse_txt(md_path, book_id="mybook")
    txt_doc, _ = parse_txt(txt_path, book_id="mybook")

    md_source_sha = hashlib.sha256(md_path.read_bytes()).hexdigest()
    txt_source_sha = hashlib.sha256(txt_path.read_bytes()).hexdigest()

    for block in md_doc.blocks:
        assert block.provenance.format == "md"
        assert block.provenance.page is None
        assert block.provenance.spine_index is None
        assert block.provenance.source_sha256 == md_source_sha

    for block in txt_doc.blocks:
        assert block.provenance.format == "txt"
        assert block.provenance.page is None
        assert block.provenance.spine_index is None
        assert block.provenance.source_sha256 == txt_source_sha

    assert md_doc.blocks[0].provenance.anchor == "chapter-one"
    assert md_doc.blocks[1].provenance.anchor == "section-a"
    assert txt_doc.blocks[0].provenance.anchor == "introduction"


def test_parse_txt_extraction_result_fields(tmp_path: Path) -> None:
    path = tmp_path / "book.md"
    path.write_text(_MARKDOWN_FIXTURE, encoding="utf-8")

    doc, result = parse_txt(path, book_id="mybook")

    assert result.method == "native_text"
    assert result.extractor_name
    assert result.extractor_version
    assert result.ocr_engine is None
    assert result.warnings == []
    expected_sha256 = hashlib.sha256(doc.canonical_text.encode("utf-8")).hexdigest()
    assert result.extraction_sha256 == expected_sha256


def test_parse_txt_non_utf8_bytes_decoded_with_warning(tmp_path: Path) -> None:
    path = tmp_path / "latin1.txt"
    path.write_bytes("café résumé\n".encode("latin-1"))

    doc, result = parse_txt(path, book_id="mybook")

    assert result.warnings
    assert "utf-8" in result.warnings[0].lower()
    _assert_offsets_dense_and_stable(doc, "mybook")


def test_parse_file_dispatches_txt_and_md(tmp_path: Path) -> None:
    md_path = tmp_path / "some book.md"
    md_path.write_text(_MARKDOWN_FIXTURE, encoding="utf-8")
    txt_path = tmp_path / "some book.txt"
    txt_path.write_text(_PLAINTEXT_FIXTURE, encoding="utf-8")

    md_doc, md_result = parse_file(md_path)
    txt_doc, txt_result = parse_file(txt_path)

    assert md_doc.book_id == "some-book"
    assert txt_doc.book_id == "some-book"
    assert md_result.method == "native_text"
    assert txt_result.method == "native_text"
    assert md_doc.blocks[0].provenance.format == "md"
    assert txt_doc.blocks[0].provenance.format == "txt"


def test_parse_file_unknown_extension_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "book.docx"
    path.write_text("irrelevant", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported"):
        parse_file(path)


def test_crlf_file_still_detects_headings(tmp_path: Path) -> None:
    """Real-world regression: Project Gutenberg ships CRLF, and every book
    collapsed into a single block because the blank-line check compared the
    next line against "" while it actually held "\\r".

    Found by running the parser over the real 18-book shelf, where all 18 books
    produced exactly one block each — synthetic LF fixtures had never exercised
    this path.
    """
    content = "CHAPTER I.\r\n\r\nCall me Ishmael.\r\n\r\nCHAPTER II.\r\n\r\nSome years ago.\r\n"
    path = tmp_path / "crlf.txt"
    path.write_bytes(content.encode("utf-8"))

    doc, _extraction = parse_txt(path, book_id="crlf")

    assert len(doc.blocks) == 2, f"expected one block per chapter, got {len(doc.blocks)}"
    assert doc.blocks[0].section_path == ["CHAPTER I."]
    assert doc.blocks[1].section_path == ["CHAPTER II."]
    # No stray carriage returns should survive into the canonical text.
    assert "\r" not in doc.canonical_text
    for block in doc.blocks:
        assert doc.canonical_text[block.char_start : block.char_end] == block.text


def test_lone_cr_line_endings_are_normalised(tmp_path: Path) -> None:
    """Classic-Mac CR-only files must not silently become one giant block either."""
    path = tmp_path / "cr.txt"
    path.write_bytes(b"HEADING ONE\r\rBody text.\r\rHEADING TWO\r\rMore body.\r")

    doc, _extraction = parse_txt(path, book_id="cr")

    assert len(doc.blocks) == 2
    assert "\r" not in doc.canonical_text
