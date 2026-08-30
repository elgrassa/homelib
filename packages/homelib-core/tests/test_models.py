"""Red-first tests for `homelib_core.models` — see specs/core-models.md.

These tests are written before the implementation exists and MUST fail
(collection error / ImportError) until packages/homelib-core/src/homelib_core/models.py
is written.
"""

import json

import pytest
from homelib_core.models import (
    Block,
    BookDoc,
    CatalogEntry,
    Chunk,
    ExtractionResult,
    Provenance,
    make_block_id,
)
from pydantic import ValidationError


def _make_provenance(**overrides: object) -> Provenance:
    data: dict[str, object] = {
        "format": "epub",
        "page": None,
        "spine_index": 3,
        "anchor": "chap03",
        "source_sha256": "a" * 64,
    }
    data.update(overrides)
    return Provenance(**data)  # type: ignore[arg-type]


def _make_block(
    book_id: str, ordinal: int, section_path: list[str], text: str, char_start: int
) -> Block:
    return Block(
        block_id=make_block_id(book_id, section_path, ordinal),
        book_id=book_id,
        ordinal=ordinal,
        section_path=section_path,
        text=text,
        char_start=char_start,
        char_end=char_start + len(text),
        provenance=_make_provenance(),
    )


def _make_book_doc() -> BookDoc:
    book_id = "moby-dick"
    section_path = ["Chapter 1", "Loomings"]
    texts = ["Call me Ishmael. ", "Some years ago... ", "There is nothing surprising here."]
    blocks = []
    canonical_text = ""
    for ordinal, text in enumerate(texts):
        char_start = len(canonical_text)
        canonical_text += text
        blocks.append(_make_block(book_id, ordinal, section_path, text, char_start))
    return BookDoc(
        book_id=book_id,
        title="Moby-Dick",
        authors=["Herman Melville"],
        language="en",
        source_url="https://example.org/moby-dick",
        license_note="public domain",
        blocks=blocks,
        canonical_text=canonical_text,
    )


def test_extra_metadata_survives_roundtrip() -> None:
    """A field nobody anticipated must survive a full serialize/deserialize cycle."""
    block = _make_block("book-1", 0, ["Intro"], "hello world", 0)
    block_with_extra = Block(**block.model_dump(), reading_level="grade-8")

    assert block_with_extra.model_extra == {"reading_level": "grade-8"}

    dumped = block_with_extra.model_dump(mode="json")
    assert dumped["reading_level"] == "grade-8"

    # Round trip through actual JSON text (not just the python dict) to prove
    # this survives the real serialization boundary, not merely construction.
    reloaded = Block.model_validate(json.loads(json.dumps(dumped)))
    assert reloaded.model_extra == {"reading_level": "grade-8"}
    assert reloaded.reading_level == "grade-8"  # type: ignore[attr-defined]


def test_block_offsets_index_into_canonical_text() -> None:
    doc = _make_book_doc()
    assert len(doc.blocks) == 3
    for block in doc.blocks:
        assert doc.canonical_text[block.char_start : block.char_end] == block.text


def test_jsonl_roundtrip_stable_ids() -> None:
    doc = _make_book_doc()
    jsonl = doc.to_jsonl()
    reloaded = BookDoc.from_jsonl(jsonl)

    assert reloaded.book_id == doc.book_id
    assert reloaded.canonical_text == doc.canonical_text
    assert [b.block_id for b in reloaded.blocks] == [b.block_id for b in doc.blocks]

    for block in reloaded.blocks:
        recomputed = make_block_id(block.book_id, block.section_path, block.ordinal)
        assert recomputed == block.block_id


def test_jsonl_roundtrip_preserves_extra_fields_on_header_and_blocks() -> None:
    doc = _make_book_doc()
    doc_with_extra = BookDoc(**doc.model_dump(), curator_note="hand-checked")
    blocks = list(doc_with_extra.blocks)
    blocks[0] = Block(**blocks[0].model_dump(), reading_level="grade-8")
    doc_with_extra = BookDoc(**{**doc_with_extra.model_dump(exclude={"blocks"}), "blocks": blocks})

    reloaded = BookDoc.from_jsonl(doc_with_extra.to_jsonl())

    assert reloaded.model_extra == {"curator_note": "hand-checked"}
    assert reloaded.blocks[0].model_extra == {"reading_level": "grade-8"}


def test_from_jsonl_malformed_line_raises_value_error_with_line_number() -> None:
    doc = _make_book_doc()
    lines = doc.to_jsonl().splitlines()
    lines[2] = "{not valid json"
    broken = "\n".join(lines)

    with pytest.raises(ValueError, match="line 3"):
        BookDoc.from_jsonl(broken)

    # Confirm it truly never returns a partial object: nothing to inspect
    # because the call must raise, verified above by pytest.raises.


def test_from_jsonl_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="line 1"):
        BookDoc.from_jsonl("")


def test_make_block_id_is_stable_and_deterministic() -> None:
    a = make_block_id("book-1", ["Ch1", "Sub"], 2)
    b = make_block_id("book-1", ["Ch1", "Sub"], 2)
    c = make_block_id("book-1", ["Ch1", "Sub"], 3)
    assert a == b
    assert a != c
    assert len(a) == 16


def test_chunk_requires_non_empty_block_ids() -> None:
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="chunk-1",
            book_id="book-1",
            block_ids=[],
            section_path=["Ch1"],
            text="hello",
            char_start=0,
            char_end=5,
        )


def test_chunk_extra_allowed() -> None:
    chunk = Chunk(
        chunk_id="chunk-1",
        book_id="book-1",
        block_ids=["deadbeef00000001"],
        section_path=["Ch1"],
        text="hello",
        char_start=0,
        char_end=5,
        embedding_model="bge-small",
    )
    assert chunk.model_extra == {"embedding_model": "bge-small"}


def test_extraction_result_defaults() -> None:
    result = ExtractionResult(
        method="native_text",
        extractor_name="pypdf",
        extractor_version="6.16.2",
        extraction_sha256="b" * 64,
    )
    assert result.ocr_engine is None
    assert result.warnings == []


def test_extraction_result_rejects_unknown_method() -> None:
    with pytest.raises(ValidationError):
        ExtractionResult(
            method="teleported",  # type: ignore[arg-type]
            extractor_name="pypdf",
            extractor_version="6.16.2",
            extraction_sha256="b" * 64,
        )


def test_catalog_entry_extra_allowed() -> None:
    entry = CatalogEntry(
        ol_key="/works/OL27448W",
        title="Moby-Dick",
        authors=["Herman Melville"],
        subjects=["Whaling"],
        first_publish_year=1851,
        description=None,
        provenance_note="Open Library",
        cover_id=12345,
    )
    assert entry.model_extra == {"cover_id": 12345}


def test_provenance_extra_allowed() -> None:
    prov = _make_provenance(scan_dpi=300)
    assert prov.model_extra == {"scan_dpi": 300}
