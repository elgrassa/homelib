"""Red-first tests for `homelib_core.formats.djvu` — see specs/formats.md.

Written before `formats/djvu.py` is implemented and MUST fail (collection
error / `NotImplementedError`) until it is.

Two fixture strategies are used:

- Most tests monkeypatch `shutil.which` and `subprocess.run` so the parsing
  logic (S-expression page/text extraction, escape decoding, provenance,
  error handling) is exercised on *every* machine, with or without
  djvulibre installed.
- A handful of tests build a real, tiny multi-page DJVU file at test time
  using `cjb2`/`djvm`/`djvused` (djvulibre CLI tools) and run the real
  `djvutxt` binary end-to-end. These are guarded by
  `pytest.mark.skipif(shutil.which("djvutxt") is None, ...)` so the suite
  still passes in full on a machine without djvulibre.
"""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from homelib_core.formats import djvu as djvu_module
from homelib_core.formats.djvu import djvu_available, parse_djvu
from homelib_core.models import make_block_id
from homelib_core.normalize import parse_file

_VERSION_BANNER = "DDJVU --- DjVuLibre-3.5.30\nDjVu text extraction utility\n\nUsage: djvutxt ...\n"

_TWO_PAGE_DETAIL_OUTPUT = (
    '(page 0 0 100 100 "Hello page one text.")\n(page 0 0 100 100 "Second page content here.")\n'
)

# 4 pages: text, text, blank (no hidden text layer), text — exercises page
# numbering surviving a skipped blank page, plus escaped quotes/backslash/
# newline inside a single page's merged text.
_FOUR_PAGE_DETAIL_OUTPUT = (
    '(page 0 0 100 100 "Hello page one text.")\n'
    "(page 0 0 100 100 \n"
    '  "Line one.\\nLine two, with \\"quotes\\" and a backslash \\\\ here.\\n" )\n'
    "()\n"
    '(page 0 0 100 100 "Fourth page.")\n'
)

_ALL_BLANK_DETAIL_OUTPUT = "()\n()\n"


class _FakeWhich:
    """Monkeypatch target for `shutil.which` returning a fixed fake binary path."""

    def __init__(self, path: str | None) -> None:
        self.path = path

    def __call__(self, name: str) -> str | None:
        return self.path if name == "djvutxt" else None


def _fake_run(detail_stdout: str, *, detail_returncode: int = 0, detail_stderr: str = "") -> object:
    """Build a fake `subprocess.run` replacement.

    The real code calls `subprocess.run` twice: once with just `[binary]` to
    read the version banner, once with `[binary, "--detail=page", path]` to
    extract text. Dispatch on argument count to return the right canned
    response for each.
    """

    def _run(
        cmd: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert check is False
        if len(cmd) == 1:
            return subprocess.CompletedProcess(
                cmd, returncode=10, stdout="", stderr=_VERSION_BANNER
            )
        return subprocess.CompletedProcess(
            cmd, returncode=detail_returncode, stdout=detail_stdout, stderr=detail_stderr
        )

    return _run


def test_djvu_available_reflects_shutil_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))
    assert djvu_available() is True

    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich(None))
    assert djvu_available() is False


def test_djvu_skips_cleanly_without_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`shutil.which` monkeypatched to `None` -> a specific, actionable `RuntimeError`."""
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich(None))
    path = tmp_path / "book.djvu"
    path.write_bytes(b"not a real djvu file")

    with pytest.raises(RuntimeError, match="djvutxt not found on PATH") as exc_info:
        parse_djvu(path, book_id="mybook")

    message = str(exc_info.value)
    assert "brew install djvulibre" in message
    assert "apt install djvulibre-bin" in message


def test_parse_djvu_nonzero_exit_raises_with_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))
    monkeypatch.setattr(
        djvu_module.subprocess,
        "run",
        _fake_run("", detail_returncode=1, detail_stderr="corrupt djvu structure"),
    )
    path = tmp_path / "broken.djvu"
    path.write_bytes(b"garbage")

    with pytest.raises(RuntimeError, match="djvutxt failed") as exc_info:
        parse_djvu(path, book_id="mybook")

    assert "corrupt djvu structure" in str(exc_info.value)


def test_parse_djvu_timeout_raises_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))

    def _wedged_run(
        cmd: list[str], *, capture_output: bool, text: bool, timeout: float, check: bool
    ) -> subprocess.CompletedProcess[str]:
        if len(cmd) == 1:
            return subprocess.CompletedProcess(
                cmd, returncode=10, stdout="", stderr=_VERSION_BANNER
            )
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(djvu_module.subprocess, "run", _wedged_run)
    path = tmp_path / "wedged.djvu"
    path.write_bytes(b"garbage")

    with pytest.raises(RuntimeError, match="timed out"):
        parse_djvu(path, book_id="mybook")


def test_parse_djvu_parses_pages_and_skips_blank_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))
    monkeypatch.setattr(djvu_module.subprocess, "run", _fake_run(_FOUR_PAGE_DETAIL_OUTPUT))

    path = tmp_path / "book.djvu"
    raw_bytes = b"fake djvu bytes for hashing"
    path.write_bytes(raw_bytes)
    expected_sha = hashlib.sha256(raw_bytes).hexdigest()

    doc, result = parse_djvu(path, book_id="mybook")

    assert [b.text for b in doc.blocks] == [
        "Hello page one text.",
        'Line one.\nLine two, with "quotes" and a backslash \\ here.',
        "Fourth page.",
    ]
    # page 3 (blank, no hidden text layer) is skipped entirely, but page
    # numbering for the remaining blocks still reflects true page position.
    assert [b.provenance.page for b in doc.blocks] == [1, 2, 4]
    assert [b.ordinal for b in doc.blocks] == [0, 1, 2]

    for block in doc.blocks:
        assert block.provenance.format == "djvu"
        assert block.provenance.spine_index is None
        assert block.provenance.anchor is None
        assert block.provenance.source_sha256 == expected_sha
        assert block.book_id == "mybook"
        assert block.section_path == []
        assert block.block_id == make_block_id("mybook", [], block.ordinal)
        assert doc.canonical_text[block.char_start : block.char_end] == block.text

    assert result.method == "native_text"
    assert result.warnings == []


def test_parse_djvu_extraction_result_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))
    monkeypatch.setattr(djvu_module.subprocess, "run", _fake_run(_TWO_PAGE_DETAIL_OUTPUT))

    path = tmp_path / "book.djvu"
    path.write_bytes(b"fake djvu bytes")

    doc, result = parse_djvu(path, book_id="mybook")

    assert result.method == "native_text"
    assert result.extractor_name
    assert result.extractor_version == "3.5.30"
    assert result.ocr_engine is None
    assert result.warnings == []
    expected_extraction_sha = hashlib.sha256(doc.canonical_text.encode("utf-8")).hexdigest()
    assert result.extraction_sha256 == expected_extraction_sha


def test_parse_djvu_version_probe_failure_falls_back_to_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the `djvutxt` version-banner probe itself blows up, extraction still succeeds."""
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))

    def _run(
        cmd: list[str], *, capture_output: bool, text: bool, timeout: float, check: bool
    ) -> subprocess.CompletedProcess[str]:
        if len(cmd) == 1:
            raise OSError("exec failed")
        return subprocess.CompletedProcess(
            cmd, returncode=0, stdout=_TWO_PAGE_DETAIL_OUTPUT, stderr=""
        )

    monkeypatch.setattr(djvu_module.subprocess, "run", _run)
    path = tmp_path / "book.djvu"
    path.write_bytes(b"fake djvu bytes")

    doc, result = parse_djvu(path, book_id="mybook")

    assert result.extractor_version == "unknown"
    assert len(doc.blocks) == 2


@pytest.mark.parametrize(
    ("raw", "decoded"),
    [
        ("plain text", "plain text"),
        ("a\\nb", "a\nb"),
        ('a\\"b', 'a"b'),
        ("a\\\\b", "a\\b"),
        ("trailing backslash\\", "trailing backslash"),
        ("\\101\\102\\103", "ABC"),  # octal escapes: 0o101='A', 0o102='B', 0o103='C'
        ("\\9weird", "9weird"),  # unrecognized escape: backslash dropped, char kept
    ],
)
def test_decode_djvu_string_escapes(raw: str, decoded: str) -> None:
    assert djvu_module._decode_djvu_string(raw) == decoded


def test_iter_top_level_forms_and_first_quoted_string_handle_nesting() -> None:
    """`--detail=page` output is flat, but the parser must not choke on nested lists."""
    text = '(page 0 0 1 1 (line 0 0 1 1 "nested text") "trailer")\n(page 0 0 1 1 "second")\n'

    forms = list(djvu_module._iter_top_level_forms(text))

    assert len(forms) == 2
    assert djvu_module._first_quoted_string(forms[0]) == "nested text"
    assert djvu_module._first_quoted_string(forms[1]) == "second"


def test_first_quoted_string_returns_none_when_absent() -> None:
    assert djvu_module._first_quoted_string("()") is None


def test_parse_djvu_all_blank_pages_yields_no_blocks_and_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))
    monkeypatch.setattr(djvu_module.subprocess, "run", _fake_run(_ALL_BLANK_DETAIL_OUTPUT))

    path = tmp_path / "blank.djvu"
    path.write_bytes(b"fake djvu bytes")

    doc, result = parse_djvu(path, book_id="mybook")

    assert doc.blocks == []
    assert doc.canonical_text == ""
    assert result.warnings != []
    assert "no hidden text layer" in result.warnings[0]


def test_parse_file_dispatches_djvu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))
    monkeypatch.setattr(djvu_module.subprocess, "run", _fake_run(_TWO_PAGE_DETAIL_OUTPUT))

    path = tmp_path / "some book.djvu"
    path.write_bytes(b"fake djvu bytes")

    doc, result = parse_file(path)

    assert doc.book_id == "some-book"
    assert result.method == "native_text"
    assert doc.blocks[0].provenance.format == "djvu"
    assert doc.blocks[0].provenance.page == 1


def test_parse_file_dispatches_djv_suffix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(djvu_module.shutil, "which", _FakeWhich("/usr/bin/djvutxt"))
    monkeypatch.setattr(djvu_module.subprocess, "run", _fake_run(_TWO_PAGE_DETAIL_OUTPUT))

    path = tmp_path / "book.djv"
    path.write_bytes(b"fake djvu bytes")

    doc, _result = parse_file(path)

    assert doc.blocks[0].provenance.format == "djvu"


# --------------------------------------------------------------------------
# Real-binary fixture: builds a genuine tiny multi-page DJVU with a real
# hidden text layer via cjb2 + djvm + djvused, then runs the real djvutxt.
# --------------------------------------------------------------------------

_REAL_FIXTURE_TOOLS = ("djvutxt", "cjb2", "djvm", "djvused")


def _real_fixture_tools_available() -> bool:
    return all(shutil.which(tool) is not None for tool in _REAL_FIXTURE_TOOLS)


def _tiny_bitonal_pbm(*, width: int = 16, height: int = 16) -> bytes:
    """A minimal valid P4 (raw bitonal) PBM image, entirely white."""
    row_bytes = (width + 7) // 8
    header = f"P4\n{width} {height}\n".encode("ascii")
    return header + bytes([0xFF]) * (row_bytes * height)


def _attach_page_text(book_path: Path, script_dir: Path, *, page: int, text: str) -> None:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    script_path = script_dir / f"page{page}.djvused"
    script_path.write_text(f'(page 0 0 100 100 "{escaped}")\n')
    subprocess.run(
        [
            shutil.which("djvused") or "djvused",
            str(book_path),
            "-e",
            f"select {page}; set-txt {script_path}",
            "-s",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


def _build_real_djvu_fixture(tmp_path: Path) -> Path:
    """3 pages: text, blank (no text layer attached), text."""
    page_paths = []
    for index in range(1, 4):
        pbm_path = tmp_path / f"page{index}.pbm"
        pbm_path.write_bytes(_tiny_bitonal_pbm())
        page_djvu = tmp_path / f"page{index}.djvu"
        subprocess.run(
            [shutil.which("cjb2") or "cjb2", str(pbm_path), str(page_djvu)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        page_paths.append(page_djvu)

    book_path = tmp_path / "fixture.djvu"
    subprocess.run(
        [shutil.which("djvm") or "djvm", "-c", str(book_path), *(str(p) for p in page_paths)],
        check=True,
        capture_output=True,
        timeout=30,
    )

    _attach_page_text(book_path, tmp_path, page=1, text="Hello page one text.")
    _attach_page_text(book_path, tmp_path, page=3, text="Third page content.")
    # Page 2 deliberately left without a set-txt call: no hidden text layer.
    return book_path


@pytest.mark.skipif(shutil.which("djvutxt") is None, reason="djvulibre (djvutxt) not installed")
def test_parse_djvu_real_binary_extracts_pages_and_skips_blank(tmp_path: Path) -> None:
    if not _real_fixture_tools_available():
        pytest.skip("djvulibre helper tools (cjb2/djvm/djvused) not installed")

    path = _build_real_djvu_fixture(tmp_path)
    expected_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    doc, result = parse_djvu(path, book_id="mybook")

    assert [b.text for b in doc.blocks] == ["Hello page one text.", "Third page content."]
    assert [b.provenance.page for b in doc.blocks] == [1, 3]

    for block in doc.blocks:
        assert block.provenance.format == "djvu"
        assert block.provenance.source_sha256 == expected_sha
        assert block.provenance.spine_index is None
        assert block.book_id == "mybook"
        assert block.block_id == make_block_id("mybook", [], block.ordinal)
        assert doc.canonical_text[block.char_start : block.char_end] == block.text

    assert result.method == "native_text"
    assert result.extractor_name
    assert re.match(r"\d+\.\d+", result.extractor_version)
    assert result.ocr_engine is None
    expected_extraction_sha = hashlib.sha256(doc.canonical_text.encode("utf-8")).hexdigest()
    assert result.extraction_sha256 == expected_extraction_sha


@pytest.mark.skipif(shutil.which("djvutxt") is None, reason="djvulibre (djvutxt) not installed")
def test_parse_file_dispatches_djvu_real_binary(tmp_path: Path) -> None:
    if not _real_fixture_tools_available():
        pytest.skip("djvulibre helper tools (cjb2/djvm/djvused) not installed")

    src_path = _build_real_djvu_fixture(tmp_path)
    dest_path = tmp_path / "My Real Book.djvu"
    dest_path.write_bytes(src_path.read_bytes())

    doc, result = parse_file(dest_path)

    assert doc.book_id == "my-real-book"
    assert result.method == "native_text"
    assert [b.provenance.page for b in doc.blocks] == [1, 3]
