"""TXT/Markdown format handler — see specs/formats.md.

Heading inference: a Markdown ATX heading (`#` through `######`), or a
plain-TXT heading heuristic (an all-caps or Title-Case line under 80 chars
immediately followed by a blank line), opens a new `section_path` level.
Body text between headings accumulates into a single `Block` for that
section, until the next heading or EOF.

Both heuristics are applied regardless of whether the file is `.txt` or
`.md` — a `.txt` file that happens to use ATX headings still gets nested
`section_path`s from them.

Line endings are normalised to `\n` first: CRLF and lone-CR files would
otherwise defeat the "followed by a blank line" test and yield one block
for the entire book.
"""

import hashlib
import re
from pathlib import Path
from typing import Literal

from homelib_core.models import Block, BookDoc, ExtractionResult, Provenance, make_block_id

EXTRACTOR_NAME = "homelib-core.formats.txt"
EXTRACTOR_VERSION = "1.0.0"

_MAX_HEADING_LEN = 80

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug or "section"


def _markdown_heading(line: str) -> tuple[int, str] | None:
    match = _MD_HEADING_RE.match(line)
    if match is None:
        return None
    return len(match.group(1)), match.group(2)


def _plaintext_heading(line: str, next_line: str | None) -> str | None:
    """An all-caps / Title-Case line under 80 chars, followed by a blank line."""
    stripped = line.strip()
    if not stripped or len(stripped) >= _MAX_HEADING_LEN:
        return None
    if next_line != "":
        return None
    if not any(char.isalpha() for char in stripped):
        return None
    if stripped.upper() == stripped or stripped.istitle():
        return stripped
    return None


def parse_txt(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]:
    """Extract a `BookDoc` from a plain-text or Markdown file."""
    warnings: list[str] = []
    raw_bytes = path.read_bytes()
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        warnings.append("file is not valid UTF-8; decoded with errors replaced")

    fmt: Literal["txt", "md"] = "md" if path.suffix.lower() == ".md" else "txt"

    # Normalise line endings before anything looks at line structure. Project
    # Gutenberg ships CRLF, and the heading heuristic tests whether the NEXT
    # line is blank — against "", which a CRLF file never yields because the
    # line still holds "\r". Without this, every heading in every real book
    # goes undetected and the whole book collapses into one block. Offsets
    # index into canonical_text, which is built from this normalised text, so
    # the char_start/char_end invariant is unaffected.
    raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw_text.split("\n")

    stack: list[tuple[int, str]] = []
    body_lines: list[str] = []
    blocks: list[Block] = []
    canonical_text = ""
    ordinal = 0

    def flush() -> None:
        nonlocal ordinal, canonical_text
        text = "\n".join(body_lines).strip("\n")
        body_lines.clear()
        if not text:
            return

        section_path = [title for _, title in stack]
        anchor = _slugify(stack[-1][1]) if stack else None

        if canonical_text:
            canonical_text += "\n\n"
        char_start = len(canonical_text)
        canonical_text += text
        char_end = len(canonical_text)

        blocks.append(
            Block(
                block_id=make_block_id(book_id, section_path, ordinal),
                book_id=book_id,
                ordinal=ordinal,
                section_path=section_path,
                text=text,
                char_start=char_start,
                char_end=char_end,
                provenance=Provenance(
                    format=fmt,
                    page=None,
                    spine_index=None,
                    anchor=anchor,
                    source_sha256=source_sha256,
                ),
            )
        )
        ordinal += 1

    line_count = len(lines)
    index = 0
    while index < line_count:
        line = lines[index]
        next_line = lines[index + 1] if index + 1 < line_count else None

        heading = _markdown_heading(line)
        if heading is None:
            plaintext_title = _plaintext_heading(line, next_line)
            heading = (1, plaintext_title) if plaintext_title is not None else None

        if heading is not None:
            level, title = heading
            flush()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            index += 1
            continue

        body_lines.append(line)
        index += 1

    flush()

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
        extractor_version=EXTRACTOR_VERSION,
        extraction_sha256=extraction_sha256,
        ocr_engine=None,
        warnings=warnings,
    )
    return doc, result
