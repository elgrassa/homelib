"""Universal in-memory book representation — see specs/core-models.md.

One data model for a book, whatever format it arrived in, such that any
retrieved passage can be traced back to a page or chapter anchor in the
original file.

Every model below opts in to allowing unrecognized fields (see each model's
`model_config`) — the single most important behavior in this file. Metadata
callers did not anticipate must survive a round trip through construction,
`model_dump`, and JSON(L) (de)serialization rather than being silently
dropped at the boundary.
"""

import hashlib
import json
from collections.abc import Sequence
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "Block",
    "BookDoc",
    "CatalogEntry",
    "Chunk",
    "ExtractionResult",
    "Provenance",
    "make_block_id",
]


def make_block_id(book_id: str, section_path: Sequence[str], ordinal: int) -> str:
    """Compute a `Block.block_id`.

    Stable across runs and processes: same `(book_id, section_path, ordinal)`
    always yields the same id, so citations survive re-ingestion.
    """
    raw = f"{book_id}|{'/'.join(section_path)}|{ordinal}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class Provenance(BaseModel):
    """Where a `Block` came from in the original source file."""

    model_config = ConfigDict(extra="allow")

    format: Literal["epub", "pdf", "txt", "md", "djvu"]
    page: int | None = None
    spine_index: int | None = None
    anchor: str | None = None
    source_sha256: str


class Block(BaseModel):
    """A contiguous span of `BookDoc.canonical_text`, with its own provenance."""

    model_config = ConfigDict(extra="allow")

    block_id: str
    book_id: str
    ordinal: int
    section_path: list[str]
    text: str
    char_start: int
    char_end: int
    provenance: Provenance


class BookDoc(BaseModel):
    """A whole book: metadata, its blocks, and their concatenated canonical text."""

    model_config = ConfigDict(extra="allow")

    book_id: str
    title: str
    authors: list[str]
    language: str
    source_url: str
    license_note: str
    blocks: list[Block]
    canonical_text: str

    def to_jsonl(self) -> str:
        """Serialize to JSON Lines: a header line, then one line per block."""
        header = self.model_dump(mode="json", exclude={"blocks"})
        lines = [json.dumps(header, ensure_ascii=False)]
        lines.extend(
            json.dumps(block.model_dump(mode="json"), ensure_ascii=False) for block in self.blocks
        )
        return "\n".join(lines) + "\n"

    @classmethod
    def from_jsonl(cls, text: str) -> Self:
        """Deserialize from `to_jsonl` output.

        Raises `ValueError` naming the offending 1-based line number on any
        malformed line (bad JSON or a value that fails model validation).
        Never returns a partially populated `BookDoc`: the object is only
        constructed once every line has been parsed and validated.
        """
        lines = text.splitlines()
        if not lines:
            raise ValueError("malformed input on line 1: no header line")

        header_data = _load_json_line(lines[0], line_no=1)
        if not isinstance(header_data, dict):
            raise ValueError("malformed input on line 1: header is not a JSON object")

        blocks: list[Block] = []
        for line_no, line in enumerate(lines[1:], start=2):
            block_data = _load_json_line(line, line_no=line_no)
            try:
                blocks.append(Block.model_validate(block_data))
            except ValidationError as exc:
                raise ValueError(f"malformed input on line {line_no}: {exc}") from exc

        try:
            return cls.model_validate({**header_data, "blocks": blocks})
        except ValidationError as exc:
            raise ValueError(f"malformed input on line 1: {exc}") from exc


class Chunk(BaseModel):
    """A retrieval unit spanning one or more `Block`s, possibly across blocks."""

    model_config = ConfigDict(extra="allow")

    chunk_id: str
    book_id: str
    block_ids: list[str] = Field(min_length=1)
    section_path: list[str]
    text: str
    char_start: int
    char_end: int


class ExtractionResult(BaseModel):
    """How `BookDoc.canonical_text` was produced from the original file."""

    model_config = ConfigDict(extra="allow")

    method: Literal["native_text", "ocr_fallback", "mixed", "extraction_failed"]
    extractor_name: str
    extractor_version: str
    extraction_sha256: str
    ocr_engine: str | None = None
    warnings: list[str] = Field(default_factory=list)


class CatalogEntry(BaseModel):
    """A catalog record (e.g. Open Library) used to enrich, never to replace, our copy."""

    model_config = ConfigDict(extra="allow")

    ol_key: str
    title: str
    authors: list[str]
    subjects: list[str]
    first_publish_year: int | None = None
    description: str | None = None
    provenance_note: str


def _load_json_line(line: str, *, line_no: int) -> object:
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed input on line {line_no}: {exc}") from exc
