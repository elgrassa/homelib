"""Red-first tests for `homelib_core.formats.epub` — see specs/formats.md.

Written before `formats/epub.py` exists and MUST fail (collection error /
ImportError) until it is implemented.

EPUB fixtures are built in-memory here with `zipfile` plus a minimal OPF/NCX
written from scratch for this test — no EPUB-building code is borrowed from
anywhere else.
"""

import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from homelib_core.formats import epub as epub_module
from homelib_core.formats.epub import EPUB_MAX_UNCOMPRESSED_BYTES, parse_epub
from homelib_core.models import make_block_id
from homelib_core.normalize import parse_file

_MIMETYPE = b"application/epub+zip"

_CONTAINER_XML = b"""<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

_CHAPTER_ONE_XHTML = """<html xmlns="http://www.w3.org/1999/xhtml">
<body>
<h1 id="c1">Chapter One</h1>
<p>First paragraph of chapter one.</p>
<h2 id="c1s1">Section One</h2>
<p>Paragraph under section one.</p>
<ul><li>A list item.</li></ul>
<blockquote>A quoted line.</blockquote>
</body>
</html>
"""

_CHAPTER_TWO_XHTML = """<html xmlns="http://www.w3.org/1999/xhtml">
<body>
<h1 id="c2">Chapter Two</h1>
<p>Second chapter text.</p>
</body>
</html>
"""


def _opf(title: str, author: str, language: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>{language}</dc:language>
    <dc:identifier id="BookId">urn:uuid:test-book-0001</dc:identifier>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
  </spine>
</package>
"""


_NCX = """<?xml version="1.0"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head/>
  <docTitle><text>Test Book</text></docTitle>
  <navMap>
    <navPoint id="navp1"><navLabel><text>Chapter One</text></navLabel>
      <content src="ch1.xhtml#c1"/></navPoint>
    <navPoint id="navp2"><navLabel><text>Chapter Two</text></navLabel>
      <content src="ch2.xhtml#c2"/></navPoint>
  </navMap>
</ncx>
"""


def _build_epub_bytes(
    *, title: str = "Test Book", author: str = "Jane Doe", language: str = "en"
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", _MIMETYPE, compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", _CONTAINER_XML)
        zf.writestr("OEBPS/content.opf", _opf(title, author, language))
        zf.writestr("OEBPS/ch1.xhtml", _CHAPTER_ONE_XHTML)
        zf.writestr("OEBPS/ch2.xhtml", _CHAPTER_TWO_XHTML)
        zf.writestr("OEBPS/toc.ncx", _NCX)
    return buf.getvalue()


def _write_epub(tmp_path: Path, name: str = "book.epub", **kwargs: str) -> Path:
    path = tmp_path / name
    path.write_bytes(_build_epub_bytes(**kwargs))
    return path


def test_parse_epub_block_order_section_path_and_provenance(tmp_path: Path) -> None:
    path = _write_epub(tmp_path)

    doc, result = parse_epub(path, book_id="mybook")

    assert [b.section_path for b in doc.blocks] == [
        ["Chapter One"],
        ["Chapter One"],
        ["Chapter One", "Section One"],
        ["Chapter One", "Section One"],
        ["Chapter One", "Section One"],
        ["Chapter One", "Section One"],
        ["Chapter Two"],
        ["Chapter Two"],
    ]
    assert [b.text for b in doc.blocks] == [
        "Chapter One",
        "First paragraph of chapter one.",
        "Section One",
        "Paragraph under section one.",
        "A list item.",
        "A quoted line.",
        "Chapter Two",
        "Second chapter text.",
    ]
    assert [b.ordinal for b in doc.blocks] == list(range(8))

    # spine_index: first six blocks come from ch1 (spine position 0), last two
    # come from ch2 (spine position 1).
    assert [b.provenance.spine_index for b in doc.blocks] == [0, 0, 0, 0, 0, 0, 1, 1]

    # anchor: nearest heading id, including the heading block itself.
    assert [b.provenance.anchor for b in doc.blocks] == [
        "c1",
        "c1",
        "c1s1",
        "c1s1",
        "c1s1",
        "c1s1",
        "c2",
        "c2",
    ]

    for block in doc.blocks:
        assert block.provenance.page is None
        assert block.provenance.format == "epub"
        assert block.book_id == "mybook"
        assert block.block_id == make_block_id("mybook", block.section_path, block.ordinal)
        assert doc.canonical_text[block.char_start : block.char_end] == block.text

    assert result.method == "native_text"


def test_parse_epub_source_sha256_matches_original_file_bytes(tmp_path: Path) -> None:
    path = _write_epub(tmp_path)
    expected_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    doc, _result = parse_epub(path, book_id="mybook")

    for block in doc.blocks:
        assert block.provenance.source_sha256 == expected_sha


def test_parse_epub_metadata(tmp_path: Path) -> None:
    path = _write_epub(tmp_path, title="My Great Book", author="A. Writer", language="fr")

    doc, _result = parse_epub(path, book_id="mybook")

    assert doc.title == "My Great Book"
    assert doc.authors == ["A. Writer"]
    assert doc.language == "fr"


def test_parse_epub_extraction_result_fields(tmp_path: Path) -> None:
    path = _write_epub(tmp_path)

    doc, result = parse_epub(path, book_id="mybook")

    assert result.method == "native_text"
    assert result.extractor_name
    assert result.extractor_version
    assert result.ocr_engine is None
    assert result.warnings == []
    expected_sha256 = hashlib.sha256(doc.canonical_text.encode("utf-8")).hexdigest()
    assert result.extraction_sha256 == expected_sha256


def test_epub_zip_bomb_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A declared uncompressed size beyond the cap is refused before any member is read."""
    path = _write_epub(tmp_path, name="bomb.epub")

    class _FakeZipInfo:
        def __init__(self, file_size: int) -> None:
            self.file_size = file_size

    class _FakeZipFile:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "_FakeZipFile":
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

        def infolist(self) -> list[_FakeZipInfo]:
            return [_FakeZipInfo(EPUB_MAX_UNCOMPRESSED_BYTES + 1)]

    monkeypatch.setattr(epub_module.zipfile, "ZipFile", _FakeZipFile)

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ebooklib.epub.read_epub must not be called when the guard trips")

    monkeypatch.setattr(epub_module.ebooklib_epub, "read_epub", _fail_if_called)

    with pytest.raises(ValueError, match="exceeds size cap"):
        parse_epub(path, book_id="bomb")


def test_epub_within_size_cap_is_parsed_normally(tmp_path: Path) -> None:
    path = _write_epub(tmp_path)
    doc, _result = parse_epub(path, book_id="mybook")
    assert len(doc.blocks) > 0


def test_parse_file_dispatches_epub(tmp_path: Path) -> None:
    path = _write_epub(tmp_path, name="some book.epub")

    doc, result = parse_file(path)

    assert doc.book_id == "some-book"
    assert result.method == "native_text"
    assert doc.blocks[0].provenance.format == "epub"
