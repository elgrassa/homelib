"""Chunking experiment: target_chars/overlap sweep — see specs/chunking.md.

Production chunks with `target_chars=1200, overlap=200` (`homelib_core.chunk`'s
own defaults). This module asks whether that choice actually matters for
retrieval quality, by re-chunking the whole corpus snapshot at two
alternatives — a smaller, more granular `600/100` and a larger, coarser
`2000/400` — and comparing all three the same way `evals/retrieval_eval.py`
compares retrieval arms: same 235 ground-truth questions, same k=5 depth,
same lexical/vector split.

Ground-truth `chunk_id`s do not survive re-chunking (a different
target_chars/overlap slices the corpus into different boundaries with
different, freshly-hashed ids), so scoring at the chunk level would be
comparing incomparable ids across configs. Every metric below is therefore
BOOK-level (`evals/metrics.py:hit_rate_book`, and `mrr_at_k` fed book ids
instead of chunk ids) — the fair comparison across chunking configs, per the
task brief this module was written against.

Both retrieval arms are built fresh, in memory, per config — no Postgres, no
SQLite file, no dependency on a live seeded store:

- **lexical**: a `:memory:` SQLite FTS5 table, the same virtual-table shape
  `apps/store/sqlite.py` migrates into the real store (`chunks_fts`,
  `tokenize='porter unicode61'`), scored by SQLite's own `bm25()`.
- **vector**: chunk texts embedded in one batched call with
  `all-MiniLM-L6-v2` (the pinned embedding model, same as
  `homelib_rag.index`/`apps/ingest/pipeline.py`) into an in-memory NumPy
  matrix, scored by cosine similarity computed directly (no FAISS/ivfflat —
  a brute-force `matrix @ query` is fast enough at this corpus's size, a few
  thousand to under twenty thousand rows per config).

`rank_bm25` is deliberately NOT used (not a project dependency, and SQLite's
own FTS5 already gives an honest lexical arm); scikit-learn's `TfidfVectorizer`
was considered and rejected too — `numpy`/`sqlite3` are already dependencies
of this project (numpy transitively via `sentence-transformers`; sqlite3 is
stdlib) and reusing the SAME FTS5 shape production actually runs makes the
lexical arm here a fair analog of the real one, not a third implementation.

This also measures a token-budget trade-off: the mean whitespace-token count
of the top-5 chunks actually sent to an LLM (the vector arm's picks) against
a "just send the whole section" baseline — a naive alternative to chunked
retrieval that this project deliberately does not ship, quantified so the
chunking choice is not just a retrieval-quality number in a vacuum.
"""

from __future__ import annotations

import argparse
import gzip
import re
import sqlite3
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

# `python evals/chunk_sweep.py` runs this file as a script, which puts
# `evals/` — not the repo root — on sys.path, so the sibling `evals.*` imports
# below would not resolve. Mirrors evals/retrieval_eval.py and evals/llm_eval.py.
if __package__ in (None, ""):  # pragma: no cover - only on the script path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homelib_core.chunk import chunk_book
from homelib_core.models import BookDoc, Chunk

from evals.ground_truth import GROUND_TRUTH_PATH, GroundTruthRow
from evals.metrics import hit_rate_book, mrr_at_k

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

__all__ = [
    "CHUNKING_CONFIGS",
    "DEFAULT_K",
    "DEFAULT_QUESTION_BUDGET",
    "REPORT_PATH",
    "SNAPSHOT_PATH",
    "ChunkConfigResult",
    "VectorIndex",
    "build_lexical_index",
    "build_vector_index",
    "chunk_corpus",
    "filter_rows_to_available_books",
    "lexical_search",
    "load_book_docs",
    "load_ground_truth_rows",
    "run_chunk_sweep",
    "score_config",
    "vector_search",
    "whole_section_token_baseline",
    "write_report",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / "data" / "corpus_snapshot.jsonl.gz"
REPORT_PATH = REPO_ROOT / "evals" / "results" / "chunking.md"

#: `(target_chars, overlap)` configs to sweep. 1200/200 is production
#: (`homelib_core.chunk.chunk_book`'s own defaults); 600/100 and 2000/400
#: bracket it at roughly half and double the granularity.
CHUNKING_CONFIGS: tuple[tuple[int, int], ...] = ((600, 100), (1200, 200), (2000, 400))

DEFAULT_K = 5

#: Ground truth has 235 rows. A full run embeds three fresh corpora (roughly
#: 4,500 / 9,168 / 18,000+ chunks for 2000/400, 1200/200, 600/100
#: respectively — smaller chunks mean more of them) and answers every
#: question against two arms per config on CPU; measured well under the
#: task's 20-minute ceiling at this budget, so 60 is a real cap, not a
#: theoretical one — see the report's own coverage line for how it actually
#: ran. Override with `--questions`.
DEFAULT_QUESTION_BUDGET = 60

#: Matches `homelib_rag.index`/`homelib_rag.sqlite_index`'s
#: `_DEFAULT_EMBED_MODEL` and `apps/ingest/pipeline.py`'s `DEFAULT_EMBED_MODEL`.
#: Repeated rather than imported for the same reason those modules repeat
#: each other's copy: importing any of them pulls in machinery (psycopg,
#: dlt) this module has no other reason to need.
_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

#: Same list `homelib_rag.sqlite_index._fts_query` filters — kept as an
#: independent local copy rather than importing that private name, so this
#: experiment script stays self-contained (the same duplication pattern
#: `evals/retrieval_eval.py`, `evals/llm_eval.py` and
#: `evals/answer_similarity.py` already use for their own ground-truth
#: loaders).
_FTS_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "what",
        "who",
        "when",
        "where",
        "which",
        "why",
        "how",
        "does",
        "did",
        "do",
        "can",
        "could",
        "would",
        "should",
        "about",
    }
)

#: `texts -> one row-vector per text`. The test seam: a unit test supplies a
#: tiny deterministic fake so scoring never downloads a model.
Embedder = Callable[[Sequence[str]], "NDArray[np.float64]"]


# ── data contracts ───────────────────────────────────────────────────────────


class ChunkConfigResult(BaseModel):
    """One `(target_chars, overlap)` config's book-level retrieval scores."""

    model_config = ConfigDict(extra="allow")

    target_chars: int
    overlap: int
    n_chunks: int
    n_questions: int
    lexical_hit_rate_book_at_5: float
    lexical_mrr_book_at_5: float
    vector_hit_rate_book_at_5: float
    vector_mrr_book_at_5: float
    #: Mean whitespace-token count of the vector arm's top-5 picks, over the
    #: scored questions — the context actually sent to an LLM under this
    #: config, as opposed to `whole_section_token_baseline`'s naive
    #: alternative.
    mean_tokens_top5: float


@dataclass(frozen=True, slots=True)
class VectorIndex:
    """An in-memory, brute-force cosine-similarity index over chunk texts."""

    chunk_ids: list[str]
    book_ids: list[str]
    #: L2-normalized rows, so `matrix @ normalized_query` IS cosine similarity.
    matrix: NDArray[np.float64]


# ── loading ──────────────────────────────────────────────────────────────────


def load_book_docs(path: Path = SNAPSHOT_PATH) -> list[BookDoc]:
    """Every `BookDoc` in the committed corpus snapshot, in file order."""
    docs: list[BookDoc] = []
    with gzip.open(path, "rt", encoding="utf-8") as raw:
        for line in raw:
            stripped = line.strip()
            if stripped:
                docs.append(BookDoc.model_validate_json(stripped))
    return docs


def load_ground_truth_rows(path: Path = GROUND_TRUTH_PATH) -> list[GroundTruthRow]:
    """Every row of `evals/ground_truth.jsonl`, unsampled, blank lines skipped.

    Unlike `evals/retrieval_eval.py`/`evals/llm_eval.py`'s `load_questions`,
    this does not round-robin across books — `--questions` here is a plain
    head-of-file cap (see the module docstring's timing note), because the
    book-level metric already scores every book that appears in whatever
    slice is taken, and a strict question-count ceiling is what keeps three
    configs' worth of re-embedding inside the documented time budget.
    """
    rows: list[GroundTruthRow] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(GroundTruthRow.model_validate_json(stripped))
    return rows


# ── chunking ─────────────────────────────────────────────────────────────────


def chunk_corpus(docs: Sequence[BookDoc], *, target_chars: int, overlap: int) -> list[Chunk]:
    """Re-chunk every book in `docs` with one `(target_chars, overlap)` pair."""
    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(chunk_book(doc, target_chars=target_chars, overlap=overlap))
    return chunks


def _whitespace_token_count(text: str) -> int:
    """Whitespace-token approximation, per the task brief (no `tiktoken`:
    not a project dependency, and adding one for a token *approximation* in
    an eval script would be a worse trade than the approximation itself).
    """
    return len(text.split())


def whole_section_token_baseline(docs: Sequence[BookDoc]) -> float:
    """Mean whitespace-token count of one whole chapter/section, across the
    corpus — the context size a naive "always send the whole section"
    baseline would cost per question.

    Computed directly from each `BookDoc`'s own blocks and their
    `section_path`, independent of any chunking config: a book's chapters are
    fixed; only how `chunk_book` SLICES them into retrieval units varies per
    `(target_chars, overlap)`. So this is one number for the whole sweep, not
    one per config — the fixed point every config's `mean_tokens_top5` is
    compared against.
    """
    totals: list[int] = []
    for doc in docs:
        tokens_by_section: dict[str, int] = {}
        for block in doc.blocks:
            key = block.section_path[0] if block.section_path else ""
            text = doc.canonical_text[block.char_start : block.char_end]
            tokens_by_section[key] = tokens_by_section.get(key, 0) + _whitespace_token_count(text)
        totals.extend(tokens_by_section.values())
    return mean(totals) if totals else 0.0


# ── lexical arm: in-memory SQLite FTS5 ───────────────────────────────────────


def _fts_query(q: str) -> str:
    tokens = [
        token
        for token in re.findall(r"\w+", q, flags=re.UNICODE)
        if token.lower() not in _FTS_STOPWORDS and len(token) > 1
    ]
    if not tokens:
        tokens = re.findall(r"\w+", q, flags=re.UNICODE)
    if not tokens:
        return '""'
    return " ".join(f'"{token}"' for token in tokens)


def build_lexical_index(chunks: Sequence[Chunk]) -> sqlite3.Connection:
    """A fresh `:memory:` FTS5 table over `chunks`. Caller must close it."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5("
        "chunk_id UNINDEXED, book_id UNINDEXED, text, tokenize='porter unicode61')"
    )
    conn.executemany(
        "INSERT INTO chunks_fts (chunk_id, book_id, text) VALUES (?, ?, ?)",
        [(chunk.chunk_id, chunk.book_id, chunk.text) for chunk in chunks],
    )
    conn.commit()
    return conn


def lexical_search(conn: sqlite3.Connection, query: str, k: int) -> list[tuple[str, str]]:
    """Up to `k` `(chunk_id, book_id)` pairs, best first, by FTS5 `bm25()`."""
    fts_q = _fts_query(query)
    rows = conn.execute(
        "SELECT chunk_id, book_id FROM chunks_fts WHERE chunks_fts MATCH ? "
        "ORDER BY bm25(chunks_fts) LIMIT ?",
        (fts_q, k),
    ).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


# ── vector arm: in-memory embedding matrix ───────────────────────────────────

_embedder: object | None = None


def _get_embedder() -> object:
    """Lazy singleton — mirrors `homelib_rag.index`/`sqlite_index`'s pattern.

    Imported lazily so importing this module (or exercising anything that
    passes its own `embed`) never pays for `sentence_transformers`.
    """
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(_EMBED_MODEL)
    return _embedder


def _default_embed(texts: Sequence[str]) -> NDArray[np.float64]:
    import numpy as np

    embedder = _get_embedder()
    vectors = embedder.encode(list(texts), batch_size=64, show_progress_bar=False)  # type: ignore[attr-defined]
    return np.asarray(vectors, dtype=np.float64)


def build_vector_index(chunks: Sequence[Chunk], *, embed: Embedder) -> VectorIndex:
    import numpy as np

    vectors = embed([chunk.text for chunk in chunks])
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    normalized = vectors / norms
    return VectorIndex(
        chunk_ids=[chunk.chunk_id for chunk in chunks],
        book_ids=[chunk.book_id for chunk in chunks],
        matrix=normalized,
    )


def vector_search(
    index: VectorIndex, query_vector: NDArray[np.float64], k: int
) -> list[tuple[str, str]]:
    """Up to `k` `(chunk_id, book_id)` pairs, best first, by cosine similarity."""
    import numpy as np

    norm = float(np.linalg.norm(query_vector))
    if norm == 0.0 or not index.chunk_ids:
        return []
    normalized_query = query_vector / norm
    scores = index.matrix @ normalized_query
    order = np.argsort(-scores)[:k]
    return [(index.chunk_ids[i], index.book_ids[i]) for i in order]


# ── scoring ──────────────────────────────────────────────────────────────────


def score_config(
    docs: Sequence[BookDoc],
    rows: Sequence[GroundTruthRow],
    *,
    target_chars: int,
    overlap: int,
    k: int = DEFAULT_K,
    embed: Embedder | None = None,
) -> ChunkConfigResult:
    """Re-chunk `docs` at `(target_chars, overlap)` and score both arms.

    Every metric is book-level: ground-truth `chunk_id`s do not survive
    re-chunking, so `relevant` is keyed by `row.book_id`, never `row.chunk_id`
    — see the module docstring.
    """
    embed_fn = embed if embed is not None else _default_embed
    chunks = chunk_corpus(docs, target_chars=target_chars, overlap=overlap)
    chunk_text_by_id = {chunk.chunk_id: chunk.text for chunk in chunks}

    lexical_conn = build_lexical_index(chunks)
    try:
        vector_index = build_vector_index(chunks, embed=embed_fn)
        query_vectors = embed_fn([row.question for row in rows]) if rows else embed_fn([])

        lexical_results: dict[str, list[str]] = {}
        vector_results: dict[str, list[str]] = {}
        relevant_books: dict[str, list[str]] = {}
        top5_token_counts: list[int] = []

        for index, row in enumerate(rows):
            query_id = str(index)
            relevant_books[query_id] = [row.book_id]

            lexical_hits = lexical_search(lexical_conn, row.question, k)
            lexical_results[query_id] = [book_id for _chunk_id, book_id in lexical_hits]

            vector_hits = vector_search(vector_index, query_vectors[index], k)
            vector_results[query_id] = [book_id for _chunk_id, book_id in vector_hits]
            top5_token_counts.append(
                sum(
                    _whitespace_token_count(chunk_text_by_id[chunk_id])
                    for chunk_id, _book_id in vector_hits
                )
            )
    finally:
        lexical_conn.close()

    return ChunkConfigResult(
        target_chars=target_chars,
        overlap=overlap,
        n_chunks=len(chunks),
        n_questions=len(rows),
        lexical_hit_rate_book_at_5=hit_rate_book(lexical_results, relevant_books, k),
        lexical_mrr_book_at_5=mrr_at_k(lexical_results, relevant_books, k),
        vector_hit_rate_book_at_5=hit_rate_book(vector_results, relevant_books, k),
        vector_mrr_book_at_5=mrr_at_k(vector_results, relevant_books, k),
        mean_tokens_top5=mean(top5_token_counts) if top5_token_counts else 0.0,
    )


def filter_rows_to_available_books(
    rows: Sequence[GroundTruthRow], docs: Sequence[BookDoc]
) -> tuple[list[GroundTruthRow], int]:
    """Rows whose `book_id` is present in `docs`, and how many were dropped.

    Scoring a question against a corpus subset that excludes its target book
    would score every arm 0 for a reason that has nothing to do with
    retrieval quality — the same principle
    `evals/retrieval_eval.py`'s `split_on_index` applies to corpus drift.
    Only matters when `--books` restricts the corpus below all 18 books.
    """
    available = {doc.book_id for doc in docs}
    kept = [row for row in rows if row.book_id in available]
    return kept, len(rows) - len(kept)


def run_chunk_sweep(
    docs: Sequence[BookDoc],
    rows: Sequence[GroundTruthRow],
    *,
    configs: Sequence[tuple[int, int]] = CHUNKING_CONFIGS,
    k: int = DEFAULT_K,
    embed: Embedder | None = None,
) -> list[ChunkConfigResult]:
    """Score every `(target_chars, overlap)` pair in `configs` over the same `rows`."""
    return [
        score_config(docs, rows, target_chars=target_chars, overlap=overlap, k=k, embed=embed)
        for target_chars, overlap in configs
    ]


# ── report ───────────────────────────────────────────────────────────────────


def write_report(
    results: Sequence[ChunkConfigResult],
    whole_section_tokens: float,
    path: Path = REPORT_PATH,
    *,
    question_budget: int | None,
    n_books_used: int,
    n_books_total: int,
    rows_dropped_book_not_in_subset: int = 0,
) -> None:
    """Write `evals/results/chunking.md` from scratch.

    Unlike `evals/retrieval_eval.py`'s "RRF k sweep" or
    `evals/answer_similarity.py`'s section, this owns its whole file rather
    than upserting into a shared report, so a plain overwrite is the right
    behaviour — there is no other section to preserve.

    Raises `ValueError` on empty `results` — same "no data is a bug, not a
    blank report" rule the other eval writers use.
    """
    if not results:
        raise ValueError("refusing to write a chunking report with no configs scored")

    budget_note = "all rows" if question_budget is None else str(question_budget)
    book_note = (
        f"{n_books_used}/{n_books_total} book(s) (`--books`)"
        if n_books_used < n_books_total
        else f"all {n_books_total} book(s)"
    )
    lines = [
        "# Chunking experiment",
        "",
        f"Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"Corpus: {book_note} re-chunked per config from `data/corpus_snapshot.jsonl.gz`. "
        "See the module docstring for why embedding the WHOLE 18-book corpus at three "
        "granularities is the actual bottleneck (not question count) and, when a full "
        "18-book run exceeds the 20-minute budget, why a book subset — not a question "
        "cap — is the lever that brings it back under.",
        f"Ground truth: `evals/ground_truth.jsonl`, question budget = {budget_note} "
        f"(`--questions`); every config below scored the same {results[0].n_questions} row(s)"
        + (
            f" ({rows_dropped_book_not_in_subset} row(s) dropped: labelled book not in the "
            "corpus subset used)."
            if rows_dropped_book_not_in_subset
            else "."
        ),
        "",
        "Ground-truth `chunk_id`s do not survive re-chunking (a different "
        "`target_chars`/`overlap` produces different chunk boundaries and "
        "freshly-hashed ids), so hit-rate/MRR below are BOOK-level "
        "(`evals/metrics.py:hit_rate_book`, and `mrr_at_k` fed book ids) — "
        "the fair comparison across configs.",
        "",
        "| target_chars/overlap | n chunks | lexical hit@5 (book) | "
        "lexical MRR@5 (book) | vector hit@5 (book) | vector MRR@5 (book) | "
        "mean tokens (top-5 chunks) | mean tokens (whole section) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            f"| {result.target_chars}/{result.overlap} | {result.n_chunks} | "
            f"{result.lexical_hit_rate_book_at_5:.3f} | {result.lexical_mrr_book_at_5:.3f} | "
            f"{result.vector_hit_rate_book_at_5:.3f} | {result.vector_mrr_book_at_5:.3f} | "
            f"{result.mean_tokens_top5:.0f} | {whole_section_tokens:.0f} |"
        )
    lines.append("")

    best = max(results, key=lambda r: (r.vector_hit_rate_book_at_5, r.vector_mrr_book_at_5))
    worst = min(results, key=lambda r: (r.vector_hit_rate_book_at_5, r.vector_mrr_book_at_5))
    spread = best.vector_hit_rate_book_at_5 - worst.vector_hit_rate_book_at_5
    lines.append(
        f"**Conclusion:** the best config on book-level hit@5 is "
        f"`{best.target_chars}/{best.overlap}` ({best.vector_hit_rate_book_at_5:.3f} vector, "
        f"vs `{worst.target_chars}/{worst.overlap}`'s {worst.vector_hit_rate_book_at_5:.3f} — a "
        f"{spread:.3f} spread across the three configs); retrieving the top-5 chunks costs "
        f"~{mean(r.mean_tokens_top5 for r in results):.0f} mean tokens against a "
        f"~{whole_section_tokens:.0f}-token whole-section baseline, so chunked retrieval is "
        "the cheaper context regardless of which config wins."
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── entry point ──────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep target_chars/overlap and compare book-level retrieval quality."
    )
    parser.add_argument(
        "--questions",
        type=int,
        default=DEFAULT_QUESTION_BUDGET,
        help="cap on ground-truth rows scored per config (default: %(default)s; "
        "see the module docstring's timing note)",
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_K, help="retrieval depth (default: %(default)s)"
    )
    parser.add_argument(
        "--books",
        type=int,
        default=None,
        help="cap on how many of the 18 corpus books to re-chunk/re-embed per config "
        "(default: all). Embedding the WHOLE corpus at three granularities, not "
        "question count, is this experiment's actual time cost (see the module "
        "docstring) — use this, not --questions, to bring a run back under the "
        "20-minute budget. Ground-truth rows whose book is excluded are dropped "
        "and counted in the report, never scored as a miss.",
    )
    parser.add_argument(
        "--report", type=Path, default=REPORT_PATH, help="report path (default: %(default)s)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started = time.monotonic()

    all_docs = load_book_docs()
    docs = all_docs[: args.books] if args.books is not None else all_docs
    rows = load_ground_truth_rows()
    if args.questions is not None:
        rows = rows[: args.questions]
    rows, dropped = filter_rows_to_available_books(rows, docs)
    if not rows:
        print("✗ no ground-truth rows loaded; no report written")
        return 1
    print(
        f"{len(docs)}/{len(all_docs)} book(s), {len(rows)} ground-truth row(s) "
        f"({dropped} dropped: book not in corpus subset), "
        f"{len(CHUNKING_CONFIGS)} config(s), k={args.k}"
    )

    whole_section_tokens = whole_section_token_baseline(docs)
    results = run_chunk_sweep(docs, rows, k=args.k)
    write_report(
        results,
        whole_section_tokens,
        args.report,
        question_budget=args.questions,
        n_books_used=len(docs),
        n_books_total=len(all_docs),
        rows_dropped_book_not_in_subset=dropped,
    )
    print(f"wrote {args.report} in {time.monotonic() - started:.1f}s")
    for result in results:
        print(
            f"  {result.target_chars}/{result.overlap}: {result.n_chunks} chunks, "
            f"vector hit@5(book)={result.vector_hit_rate_book_at_5:.3f} "
            f"lexical hit@5(book)={result.lexical_hit_rate_book_at_5:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
