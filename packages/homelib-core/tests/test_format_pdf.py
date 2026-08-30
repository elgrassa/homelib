"""Red-first tests for `homelib_core.formats.pdf` — see specs/formats.md.

Written before `formats/pdf.py`'s real body exists and MUST fail (the stub
raises `NotImplementedError`) until it is implemented.

PDF fixtures are built in-memory here with `pypdf`'s own writer and/or
PyMuPDF — no PDF-building code is borrowed from anywhere else:

- a "native" page gets real PDF text operators via PyMuPDF's
  `Page.insert_text`, so `pypdf.extract_text()` reads it back directly.
- a "scanned" page has its text rendered into a raster image with Pillow,
  then that image (and *only* that image — no text layer) is embedded via
  PyMuPDF's `Page.insert_image`, so `pypdf.extract_text()` reads back
  nothing and PyMuPDF's `get_textpage_ocr` (backed by the Tesseract binary
  on this machine) is the only way to recover the text.
- an encrypted fixture goes through `pypdf.PdfWriter.encrypt`.
"""

import hashlib
import io
import shutil
from pathlib import Path

import pymupdf
import pytest
from homelib_core.formats import pdf as pdf_module
from homelib_core.formats.pdf import (
    _SCANNED_CHARS_PER_PAGE_THRESHOLD,
    _is_likely_scanned,
    parse_pdf,
)
from homelib_core.models import make_block_id
from homelib_core.normalize import parse_file
from PIL import Image, ImageDraw

_TESSERACT_MISSING = shutil.which("tesseract") is None


def _render_text_image(text: str, *, width: int = 900, height: int = 220) -> bytes:
    """Rasterize `text` onto a white background — no PDF text layer involved."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, height // 2 - 20), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_pdf_bytes(pages: list[tuple[str, bool]]) -> bytes:
    """Build a PDF from `(text, is_scanned)` pairs, one per page.

    `is_scanned=False` inserts real PDF text (native, pypdf-extractable).
    `is_scanned=True` rasterizes the text into an image and embeds only the
    image (no text layer at all — pypdf sees an empty page).
    """
    doc = pymupdf.open()
    for text, is_scanned in pages:
        page = doc.new_page(width=900, height=220)
        if is_scanned:
            page.insert_image(pymupdf.Rect(0, 0, 900, 220), stream=_render_text_image(text))
        else:
            page.insert_text((40, 100), text)
    pdf_bytes: bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _write_pdf(tmp_path: Path, pages: list[tuple[str, bool]], name: str = "book.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(_build_pdf_bytes(pages))
    return path


def _build_encrypted_pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password="secret")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------
# native text
# --------------------------------------------------------------------------


def test_parse_pdf_native_text_page_provenance_and_offsets(tmp_path: Path) -> None:
    path = _write_pdf(
        tmp_path,
        [
            ("First page of native text.", False),
            ("Second page of native text.", False),
            ("Third page of native text.", False),
        ],
    )

    doc, result = parse_pdf(path, book_id="mybook")

    assert result.method == "native_text"
    assert result.ocr_engine is None
    assert [b.ordinal for b in doc.blocks] == [0, 1, 2]
    assert [b.provenance.page for b in doc.blocks] == [1, 2, 3]
    assert [b.text for b in doc.blocks] == [
        "First page of native text.",
        "Second page of native text.",
        "Third page of native text.",
    ]

    for block in doc.blocks:
        assert block.book_id == "mybook"
        assert block.section_path == []
        assert block.provenance.format == "pdf"
        assert block.provenance.spine_index is None
        assert block.provenance.anchor is None
        assert block.block_id == make_block_id("mybook", block.section_path, block.ordinal)
        # Binding invariant: every block's text is exactly the canonical_text
        # slice its own char_start/char_end name.
        assert doc.canonical_text[block.char_start : block.char_end] == block.text

    # block ordering matches page order, and offsets are monotonically
    # increasing with no overlap.
    for prev, nxt in zip(doc.blocks, doc.blocks[1:], strict=False):
        assert prev.char_end <= nxt.char_start


def test_parse_pdf_source_sha256_matches_original_file_bytes(tmp_path: Path) -> None:
    path = _write_pdf(tmp_path, [("Some perfectly ordinary native page text.", False)])
    expected_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    doc, _result = parse_pdf(path, book_id="mybook")

    for block in doc.blocks:
        assert block.provenance.source_sha256 == expected_sha


def test_parse_pdf_extraction_result_fields(tmp_path: Path) -> None:
    path = _write_pdf(tmp_path, [("Some perfectly ordinary native page text.", False)])

    doc, result = parse_pdf(path, book_id="mybook")

    assert result.method == "native_text"
    assert result.extractor_name
    assert result.extractor_version
    assert result.ocr_engine is None
    assert result.warnings == []
    expected_sha256 = hashlib.sha256(doc.canonical_text.encode("utf-8")).hexdigest()
    assert result.extraction_sha256 == expected_sha256


def test_parse_file_dispatches_pdf(tmp_path: Path) -> None:
    path = _write_pdf(
        tmp_path, [("Dispatch me through the normal dispatcher.", False)], name="some book.pdf"
    )

    doc, result = parse_file(path)

    assert doc.book_id == "some-book"
    assert result.method == "native_text"
    assert doc.blocks[0].provenance.format == "pdf"


# --------------------------------------------------------------------------
# scanned / OCR
# --------------------------------------------------------------------------


@pytest.mark.skipif(_TESSERACT_MISSING, reason="tesseract binary not found on PATH")
def test_scanned_pdf_triggers_ocr_path(tmp_path: Path) -> None:
    """A genuinely image-only PDF takes the real OCR branch (Tesseract, not mocked)."""
    path = _write_pdf(tmp_path, [("SCANNED PAGE CONTENT", True)])

    doc, result = parse_pdf(path, book_id="mybook")

    assert result.method == "ocr_fallback"
    assert result.ocr_engine == pdf_module.OCR_ENGINE
    assert len(doc.blocks) == 1
    assert "SCANNED" in doc.blocks[0].text.upper()
    assert doc.blocks[0].provenance.page == 1
    assert doc.canonical_text[doc.blocks[0].char_start : doc.blocks[0].char_end] == (
        doc.blocks[0].text
    )


@pytest.mark.skipif(_TESSERACT_MISSING, reason="tesseract binary not found on PATH")
def test_mixed_pdf_some_pages_native_some_ocr(tmp_path: Path) -> None:
    """A document with mostly-scanned pages but one real text page is 'mixed'."""
    long_native_paragraph = (
        "This page carries a long, perfectly ordinary native text layer that "
        "pypdf can read directly without any OCR at all."
    )
    path = _write_pdf(
        tmp_path,
        [
            (long_native_paragraph, False),
            ("PAGE TWO SCANNED CONTENT", True),
            ("PAGE THREE SCANNED CONTENT", True),
        ],
    )

    doc, result = parse_pdf(path, book_id="mybook")

    assert result.method == "mixed"
    assert result.ocr_engine == pdf_module.OCR_ENGINE
    assert len(doc.blocks) == 3
    assert doc.blocks[0].text == long_native_paragraph
    assert "PAGE TWO" in doc.blocks[1].text.upper()
    assert "PAGE THREE" in doc.blocks[2].text.upper()
    assert [b.provenance.page for b in doc.blocks] == [1, 2, 3]

    for block in doc.blocks:
        assert doc.canonical_text[block.char_start : block.char_end] == block.text


def test_scanned_pdf_triggers_ocr_path_monkeypatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same branch, proven without depending on the real Tesseract binary.

    Complements the real-OCR test above: this one monkeypatches `pymupdf`
    itself so the OCR branch's control flow (and `method == "ocr_fallback"`)
    is verified even in an environment without Tesseract installed.
    """
    path = _write_pdf(tmp_path, [("irrelevant, native text is stubbed below", True)])

    class _FakeTextPage:
        pass

    class _FakePage:
        def get_textpage_ocr(self, *, flags: int, dpi: int, full: bool) -> _FakeTextPage:
            return _FakeTextPage()

        def get_text(self, *, textpage: _FakeTextPage) -> str:
            return "fake ocr text"

    class _FakeDoc:
        def __getitem__(self, index: int) -> _FakePage:
            return _FakePage()

        def close(self) -> None:
            pass

    class _FakePyMuPDF:
        Rect = pymupdf.Rect

        @staticmethod
        def open(_path: Path) -> _FakeDoc:
            return _FakeDoc()

    monkeypatch.setattr(pdf_module, "pymupdf", _FakePyMuPDF())

    doc, result = parse_pdf(path, book_id="mybook")

    assert result.method == "ocr_fallback"
    assert result.ocr_engine == pdf_module.OCR_ENGINE
    assert doc.blocks[0].text == "fake ocr text"


def test_ocr_missing_dependency_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `pymupdf` unavailable, a page that needs OCR raises loudly."""
    path = _write_pdf(tmp_path, [("this page has no text layer", True)])

    monkeypatch.setattr(pdf_module, "pymupdf", None)

    with pytest.raises(RuntimeError, match=r"homelib-core\[ocr\]"):
        parse_pdf(path, book_id="mybook")


# --------------------------------------------------------------------------
# encrypted
# --------------------------------------------------------------------------


def test_encrypted_pdf_raises_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    path.write_bytes(_build_encrypted_pdf_bytes())

    with pytest.raises(ValueError, match="encrypted"):
        parse_pdf(path, book_id="mybook")


def test_parse_file_dispatches_encrypted_pdf_and_raises(tmp_path: Path) -> None:
    """The dispatcher doesn't swallow the encrypted-PDF refusal either."""
    path = tmp_path / "encrypted.pdf"
    path.write_bytes(_build_encrypted_pdf_bytes())

    with pytest.raises(ValueError, match="encrypted"):
        parse_file(path)


# --------------------------------------------------------------------------
# `_is_likely_scanned` heuristic, tested directly
# --------------------------------------------------------------------------


def test_is_likely_scanned_empty_document_is_false() -> None:
    assert _is_likely_scanned([], 0) is False


def test_is_likely_scanned_dense_native_pages_is_false() -> None:
    dense_page = "word " * 200  # far above the 20-char/page threshold
    assert _is_likely_scanned([dense_page, dense_page], 2) is False


def test_is_likely_scanned_low_mean_chars_is_true() -> None:
    # Mean chars/page well under the threshold across every page.
    assert _is_likely_scanned(["", "", "hi"], 3) is True


def test_is_likely_scanned_majority_empty_pages_is_true() -> None:
    # A handful of pages just at/under the threshold pull the ratio over 50%,
    # even though one dense page keeps the mean misleadingly high.
    dense_page = "word " * 200
    sparse = "x" * (_SCANNED_CHARS_PER_PAGE_THRESHOLD - 1)
    assert _is_likely_scanned([dense_page, sparse, sparse, sparse], 4) is True


def test_is_likely_scanned_boundary_ratio_exactly_half_is_false() -> None:
    # Exactly 50% sparse pages does not exceed the ">50%" threshold, and the
    # mean (dominated by two dense pages) stays well above 20 too.
    dense_page = "word " * 200
    sparse = ""
    assert _is_likely_scanned([dense_page, dense_page, sparse, sparse], 4) is False
