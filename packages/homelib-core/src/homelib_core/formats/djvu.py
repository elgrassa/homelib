"""DJVU format handler — see specs/formats.md.

Extracts the hidden text layer via the `djvutxt` CLI (part of `djvulibre`),
which must be present on the host — DJVU support is conditional, never a
silent no-op (see `djvu_available` / the `RuntimeError` in `parse_djvu`).

`djvutxt --detail=page <file>` prints one S-expression per page, in page
order:

    (page xmin ymin xmax ymax "escaped page text")
    (page xmin ymin xmax ymax "escaped page text")
    ()

A page with no hidden text at all (no OCR text layer attached) prints as a
bare `()` with no string — that page contributes no `Block`, but it still
occupies a position in the sequence, which is how 1-based `Provenance.page`
numbers are recovered even when earlier or later pages are blank.
"""

import hashlib
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

from homelib_core.models import Block, BookDoc, ExtractionResult, Provenance, make_block_id

EXTRACTOR_NAME = "homelib-core.formats.djvu (djvutxt)"

_UNKNOWN_VERSION = "unknown"
_TIMEOUT_SECONDS = 60

_MISSING_BINARY_MESSAGE = (
    "djvutxt not found on PATH; install djvulibre to parse DJVU files "
    "(macOS: `brew install djvulibre`; Debian/Ubuntu: `apt install djvulibre-bin`), "
    "or skip DJVU ingestion"
)

# djvutxt prints its usage banner (including a version string) to stderr when
# invoked with no arguments, e.g. "DDJVU --- DjVuLibre-3.5.30".
_VERSION_RE = re.compile(r"DjVuLibre-(\S+)")

# djvused hidden-text-syntax string escapes (see `man djvused`, "Hidden text
# syntax"): a backslash followed by one of these letters stands for the named
# control character; a backslash followed by 1-3 octal digits stands for the
# byte with that code.
_ESCAPE_MAP: dict[str, str] = {
    "a": "\a",
    "b": "\b",
    "t": "\t",
    "n": "\n",
    "v": "\v",
    "f": "\f",
    "r": "\r",
    "\\": "\\",
    '"': '"',
}

_OCTAL_DIGITS = frozenset("01234567")


def djvu_available() -> bool:
    """Whether the `djvutxt` binary is on PATH."""
    return shutil.which("djvutxt") is not None


def _require_djvutxt() -> str:
    binary = shutil.which("djvutxt")
    if binary is None:
        raise RuntimeError(_MISSING_BINARY_MESSAGE)
    return binary


def _djvutxt_version(binary: str) -> str:
    """Best-effort `djvutxt` version, parsed from its no-args usage banner.

    `djvutxt` has no `--version` flag; invoking it with no arguments prints a
    usage banner (to stderr, with a non-zero exit) whose first line names the
    djvulibre version. Never raises: a probe failure just yields "unknown".
    """
    try:
        # binary is a resolved absolute path from shutil.which(), and the
        # argument list is fixed (no shell, no untrusted input).
        proc = subprocess.run(  # noqa: S603
            [binary],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _UNKNOWN_VERSION
    match = _VERSION_RE.search(proc.stdout + proc.stderr)
    return match.group(1) if match else _UNKNOWN_VERSION


def _decode_djvu_string(raw: str) -> str:
    """Decode the backslash escapes in a djvused quoted-string body."""
    out: list[str] = []
    index = 0
    length = len(raw)
    while index < length:
        char = raw[index]
        if char != "\\":
            out.append(char)
            index += 1
            continue
        index += 1
        if index >= length:
            break
        escaped = raw[index]
        mapped = _ESCAPE_MAP.get(escaped)
        if mapped is not None:
            out.append(mapped)
            index += 1
            continue
        if escaped in _OCTAL_DIGITS:
            octal_digits = ""
            while len(octal_digits) < 3 and index < length and raw[index] in _OCTAL_DIGITS:
                octal_digits += raw[index]
                index += 1
            out.append(chr(int(octal_digits, 8)))
            continue
        # Unknown escape sequence: keep the escaped character literally.
        out.append(escaped)
        index += 1
    return "".join(out)


def _iter_top_level_forms(text: str) -> Iterator[str]:
    """Yield each top-level parenthesized S-expression in `text`, in order."""
    depth = 0
    in_string = False
    escape = False
    start: int | None = None
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "(":
            if depth == 0:
                start = index
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start : index + 1]
                start = None


def _first_quoted_string(form: str) -> str | None:
    """Return the raw (still-escaped) body of the first quoted string in `form`."""
    in_string = False
    escape = False
    chars: list[str] = []
    for char in form:
        if in_string:
            if escape:
                chars.append(char)
                escape = False
                continue
            if char == "\\":
                chars.append(char)
                escape = True
                continue
            if char == '"':
                return "".join(chars)
            chars.append(char)
            continue
        if char == '"':
            in_string = True
    return None


def _extract_page_texts(binary: str, path: Path) -> list[str]:
    """Run `djvutxt --detail=page` and return one text string per page, in order."""
    try:
        # binary is a resolved absolute path from shutil.which(); path is the
        # caller-supplied file to parse (no shell involved).
        proc = subprocess.run(  # noqa: S603
            [binary, "--detail=page", str(path)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"djvutxt timed out after {_TIMEOUT_SECONDS}s extracting text from {path}"
        ) from exc

    if proc.returncode != 0:
        raise RuntimeError(
            f"djvutxt failed on {path} (exit code {proc.returncode}): {proc.stderr.strip()}"
        )

    page_texts: list[str] = []
    for form in _iter_top_level_forms(proc.stdout):
        raw_string = _first_quoted_string(form)
        page_texts.append(_decode_djvu_string(raw_string) if raw_string is not None else "")
    return page_texts


def parse_djvu(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]:
    """Extract a `BookDoc` from a DJVU file via `djvutxt`.

    Raises `RuntimeError` (never a silent skip) if `djvutxt` is not on PATH,
    if the subprocess exits non-zero, or if it times out.
    """
    binary = _require_djvutxt()

    raw_bytes = path.read_bytes()
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    page_texts = _extract_page_texts(binary, path)

    blocks: list[Block] = []
    canonical_text = ""
    ordinal = 0
    for page_number, page_text in enumerate(page_texts, start=1):
        text = page_text.strip()
        if not text:
            continue

        if canonical_text:
            canonical_text += "\n\n"
        char_start = len(canonical_text)
        canonical_text += text
        char_end = len(canonical_text)

        blocks.append(
            Block(
                block_id=make_block_id(book_id, [], ordinal),
                book_id=book_id,
                ordinal=ordinal,
                section_path=[],
                text=text,
                char_start=char_start,
                char_end=char_end,
                provenance=Provenance(
                    format="djvu",
                    page=page_number,
                    spine_index=None,
                    anchor=None,
                    source_sha256=source_sha256,
                ),
            )
        )
        ordinal += 1

    warnings: list[str] = []
    if not blocks:
        warnings.append(f"no hidden text layer found on any page of {path}")

    extraction_sha256 = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    doc = BookDoc(
        book_id=book_id,
        title=path.stem,
        authors=[],
        language="en",
        source_url="",
        license_note="",
        blocks=blocks,
        canonical_text=canonical_text,
    )
    result = ExtractionResult(
        method="native_text",
        extractor_name=EXTRACTOR_NAME,
        extractor_version=_djvutxt_version(binary),
        extraction_sha256=extraction_sha256,
        ocr_engine=None,
        warnings=warnings,
    )
    return doc, result
