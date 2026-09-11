"""Remap retrieval ground truth onto tip-seed passage text.

ID presence alone misses reseeds that keep ``chunk_id`` while changing text
(observed 115/235 drift). This module:

1. Loads tip SQLite chunks and asserts ``CANONICAL_COUNTS["chunks"]``.
2. Flags rows whose labelled passage no longer coheres with the question.
3. Remaps drifted rows to the best same-book (then global) tip chunk.
4. Writes an auditable old→new map and optionally the remapped JSONL.

Not run from CI. Offline: ``uv run python -m evals.remap_ground_truth``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from dataclasses import asdict, dataclass
from gzip import open as gzip_open
from pathlib import Path

from apps.ingest.sqlite_pipeline import CANONICAL_COUNTS
from evals.ground_truth import (
    GROUND_TRUTH_PATH,
    GroundTruthRow,
    distinctive_terms,
    passage_content_hash,
    row_passage_coherent,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_GZ = REPO_ROOT / "data" / "seed" / "homelib.sqlite.gz"
DEFAULT_MAP_PATH = REPO_ROOT / "evals" / "ground_truth_remap.jsonl"
CORPUS_REVISION = "seed-627-9119"


@dataclass(frozen=True)
class TipChunk:
    chunk_id: str
    book_id: str
    text: str


@dataclass(frozen=True)
class RemapRecord:
    question: str
    old_chunk_id: str
    new_chunk_id: str
    book_id: str
    method: str
    score: float


def inflate_seed(gz_path: Path = SEED_GZ) -> Path:
    """Gunzip the committed demo seed into a temp SQLite file."""
    tmp = tempfile.NamedTemporaryFile(prefix="homelib-remap-", suffix=".sqlite", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    with gzip_open(gz_path, "rb") as src, tmp_path.open("wb") as dst:
        dst.write(src.read())
    return tmp_path


def load_tip_chunks(sqlite_path: Path) -> dict[str, TipChunk]:
    """All tip chunks keyed by id; fail closed on count mismatch."""
    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute("SELECT chunk_id, book_id, text FROM chunks").fetchall()
    finally:
        conn.close()
    expected = CANONICAL_COUNTS["chunks"]
    if len(rows) != expected:
        raise SystemExit(
            f"tip seed has {len(rows)} chunks; expected CANONICAL_COUNTS={expected}"
        )
    return {
        str(chunk_id): TipChunk(chunk_id=str(chunk_id), book_id=str(book_id), text=str(text))
        for chunk_id, book_id, text in rows
    }


def _chunk_term_set(text: str) -> frozenset[str]:
    return frozenset(distinctive_terms(text, min_len=3))


@dataclass
class TipIndex:
    by_id: dict[str, TipChunk]
    terms_by_id: dict[str, frozenset[str]]
    ids_by_book: dict[str, list[str]]
    ids_by_term: dict[str, set[str]]

    @classmethod
    def build(cls, tip: dict[str, TipChunk]) -> TipIndex:
        terms_by_id: dict[str, frozenset[str]] = {}
        ids_by_book: dict[str, list[str]] = {}
        ids_by_term: dict[str, set[str]] = {}
        for chunk_id, chunk in tip.items():
            terms = _chunk_term_set(chunk.text)
            terms_by_id[chunk_id] = terms
            ids_by_book.setdefault(chunk.book_id, []).append(chunk_id)
            for term in terms:
                ids_by_term.setdefault(term, set()).add(chunk_id)
        return cls(
            by_id=tip,
            terms_by_id=terms_by_id,
            ids_by_book=ids_by_book,
            ids_by_term=ids_by_term,
        )


def load_ground_truth(path: Path = GROUND_TRUTH_PATH) -> list[GroundTruthRow]:
    rows: list[GroundTruthRow] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(GroundTruthRow.model_validate_json(stripped))
    return rows


def _score_terms(chunk_terms: frozenset[str], terms: list[str], *, book_bonus: bool) -> float:
    if not terms:
        return 0.0
    hits = sum(1 for term in terms if term in chunk_terms)
    score = hits / len(terms)
    if book_bonus:
        score += 0.15
    return score


def find_best_chunk(
    row: GroundTruthRow,
    index: TipIndex,
    *,
    min_score: float = 0.35,
    prefer_book: bool = True,
) -> tuple[TipChunk, float] | None:
    terms = distinctive_terms(row.question)
    if not terms:
        return None

    candidate_ids: set[str] = set()
    if prefer_book and row.book_id and row.book_id in index.ids_by_book:
        candidate_ids.update(index.ids_by_book[row.book_id])
        used_same_book = True
    else:
        # Union postings for question terms; rare terms keep the set small.
        for term in sorted(terms, key=lambda t: len(index.ids_by_term.get(t, ()))):
            posting = index.ids_by_term.get(term)
            if not posting:
                continue
            if not candidate_ids:
                candidate_ids = set(posting)
            else:
                candidate_ids |= posting
            if len(candidate_ids) > 400:
                break
        used_same_book = False

    best: tuple[float, TipChunk] | None = None
    for chunk_id in candidate_ids:
        chunk = index.by_id[chunk_id]
        score = _score_terms(
            index.terms_by_id[chunk_id],
            terms,
            book_bonus=chunk.book_id == row.book_id,
        )
        if best is None or score > best[0]:
            best = (score, chunk)

    if best is None:
        return None
    score, chunk = best
    if score < min_score and used_same_book:
        return find_best_chunk(row, index, min_score=min_score, prefer_book=False)
    if score < min_score:
        return None
    return chunk, score


def remap_rows(
    rows: list[GroundTruthRow], tip: dict[str, TipChunk]
) -> tuple[list[GroundTruthRow], list[RemapRecord], list[GroundTruthRow]]:
    """Return (new_rows, remap_records, unmapped_drifted)."""
    index = TipIndex.build(tip)
    new_rows: list[GroundTruthRow] = []
    records: list[RemapRecord] = []
    unmapped: list[GroundTruthRow] = []

    for row in rows:
        tip_chunk = tip.get(row.chunk_id)
        tip_text = tip_chunk.text if tip_chunk is not None else None
        if row_passage_coherent(row, tip_text) and tip_chunk is not None:
            new_rows.append(
                GroundTruthRow(
                    question=row.question,
                    chunk_id=tip_chunk.chunk_id,
                    book_id=tip_chunk.book_id,
                    passage_sha256=passage_content_hash(tip_chunk.text),
                    corpus_revision=CORPUS_REVISION,
                )
            )
            continue

        found = find_best_chunk(row, index)
        if found is None:
            unmapped.append(row)
            continue
        chunk, score = found
        new_rows.append(
            GroundTruthRow(
                question=row.question,
                chunk_id=chunk.chunk_id,
                book_id=chunk.book_id,
                passage_sha256=passage_content_hash(chunk.text),
                corpus_revision=CORPUS_REVISION,
            )
        )
        records.append(
            RemapRecord(
                question=row.question,
                old_chunk_id=row.chunk_id,
                new_chunk_id=chunk.chunk_id,
                book_id=chunk.book_id,
                method="term_overlap_prefer_book",
                score=round(score, 4),
            )
        )
    return new_rows, records, unmapped


def write_jsonl(path: Path, rows: list[GroundTruthRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.model_dump_json(exclude_none=True) + "\n")


def write_remap_map(path: Path, records: list[RemapRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=None, help="Tip SQLite path")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report coherence drift counts and exit non-zero if any drifted",
    )
    parser.add_argument("--out", type=Path, default=None, help="Write remapped ground_truth.jsonl")
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP_PATH, help="Audit remap map path")
    args = parser.parse_args(argv)

    sqlite_path = args.sqlite
    cleanup: Path | None = None
    if sqlite_path is None:
        cleanup = inflate_seed()
        sqlite_path = cleanup

    try:
        tip = load_tip_chunks(sqlite_path)
        rows = load_ground_truth()
        drifted = [
            row
            for row in rows
            if not row_passage_coherent(
                row, tip[row.chunk_id].text if row.chunk_id in tip else None
            )
        ]
        print(
            f"rows={len(rows)} tip_chunks={len(tip)} "
            f"coherent={len(rows) - len(drifted)} drifted={len(drifted)}"
        )
        if args.check_only:
            return 1 if drifted else 0

        new_rows, records, unmapped = remap_rows(rows, tip)
        print(
            f"remapped={len(records)} kept_or_bound={len(new_rows) - len(records)} "
            f"unmapped={len(unmapped)}"
        )
        for row in unmapped:
            records.append(
                RemapRecord(
                    question=row.question,
                    old_chunk_id=row.chunk_id,
                    new_chunk_id="",
                    book_id=row.book_id,
                    method="unmapped",
                    score=0.0,
                )
            )
            print(f"  unmapped: {row.chunk_id} {row.question[:80]!r}")

        if len(new_rows) < 150:
            print(f"refusing to write: only {len(new_rows)} rows (need >= 150)")
            return 2

        write_remap_map(args.map, records)
        print(f"wrote remap map {args.map} ({len(records)} rows)")
        if args.out is not None:
            write_jsonl(args.out, new_rows)
            print(f"wrote remapped ground truth {args.out} ({len(new_rows)} rows)")
        return 0 if not unmapped else 0
    finally:
        if cleanup is not None:
            cleanup.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
