"""EPUB format handler — see specs/formats.md.

Block granularity: each `h1`-`h6`, `p`, `li`, and `blockquote` element in a
spine item's XHTML, in document order, becomes one `Block`. A heading
element both opens a new `section_path` level (nesting/un-nesting by its
`h`-level, mirroring the Markdown TXT heading rule) and is itself recorded
as a block — chapter/section titles are citable content, not just metadata.
`Provenance.anchor` is the nearest heading's `id` attribute (the NCX/nav
fragment target), or `None` before any heading has been seen.

Uses the stdlib `xml.etree.ElementTree` rather than `lxml` for XHTML body
parsing: EPUB content documents are required to be well-formed XML, and
sticking to the stdlib keeps this module free of `lxml`'s untyped-import
mypy friction (`lxml` ships no inline types or stub package here).
"""

import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import ebooklib
from ebooklib import epub as ebooklib_epub

from homelib_core.models import Block, BookDoc, ExtractionResult, Provenance, make_block_id

EXTRACTOR_NAME = "ebooklib"
EXTRACTOR_VERSION = ".".join(str(part) for part in ebooklib.VERSION)

# Refuse to decompress an EPUB whose declared uncompressed size exceeds this,
# checked from the zip central directory before ebooklib ever opens the
# archive (see specs/formats.md, "EPUB zip-bomb guard").
EPUB_MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024

_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_TEXT_TAGS = frozenset({"p", "li", "blockquote"})
_WHITESPACE_RE = re.compile(r"\s+")


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _element_text(el: ET.Element) -> str:
    return _WHITESPACE_RE.sub(" ", "".join(el.itertext())).strip()


def _check_not_zip_bomb(path: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        total_uncompressed = sum(info.file_size for info in zf.infolist())
    if total_uncompressed > EPUB_MAX_UNCOMPRESSED_BYTES:
        raise ValueError(f"epub exceeds size cap: {path}")


def parse_epub(path: Path, *, book_id: str) -> tuple[BookDoc, ExtractionResult]:
    """Extract a `BookDoc` from an EPUB file."""
    _check_not_zip_bomb(path)

    raw_bytes = path.read_bytes()
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    book = ebooklib_epub.read_epub(str(path))

    title_meta = book.get_metadata("DC", "title")
    title = str(title_meta[0][0]) if title_meta else path.stem
    authors = [str(value) for value, _attrs in book.get_metadata("DC", "creator")]
    language_meta = book.get_metadata("DC", "language")
    language = str(language_meta[0][0]) if language_meta else "en"

    warnings: list[str] = []
    blocks: list[Block] = []
    canonical_text = ""
    ordinal = 0
    stack: list[tuple[int, str, str | None]] = []

    for spine_index, (idref, _linear) in enumerate(book.spine):
        item = book.get_item_with_id(idref)
        if item is None:
            warnings.append(f"spine item {idref!r} not found in manifest; skipped")
            continue

        try:
            # EPUB content documents are XML but their trust boundary is bounded by the
            # zip-bomb size guard above; pulling in defusedxml is a dependency change out
            # of scope for this work package. noqa: S314 accepted for stdlib ElementTree.
            tree = ET.fromstring(item.get_content())  # noqa: S314
        except ET.ParseError as exc:
            warnings.append(f"failed to parse spine item {idref!r}: {exc}")
            continue

        for el in tree.iter():
            tag = el.tag
            if not isinstance(tag, str):
                continue
            local = _localname(tag)
            if local not in _HEADING_TAGS and local not in _TEXT_TAGS:
                continue

            text = _element_text(el)
            if not text:
                continue

            if local in _HEADING_TAGS:
                level = int(local[1])
                while stack and stack[-1][0] >= level:
                    stack.pop()
                el_id = el.get("id")
                stack.append((level, text, el_id))
                anchor = el_id
            else:
                anchor = stack[-1][2] if stack else None

            section_path = [heading_title for _, heading_title, _ in stack]

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
                        format="epub",
                        page=None,
                        spine_index=spine_index,
                        anchor=anchor,
                        source_sha256=source_sha256,
                    ),
                )
            )
            ordinal += 1

    extraction_sha256 = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    doc = BookDoc(
        book_id=book_id,
        title=title,
        authors=authors,
        language=language,
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
