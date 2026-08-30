"""LLM-generated retrieval ground truth — see specs/evals-retrieval.md.

Samples chunks from the committed corpus snapshot, asks a local LLM for
questions each sampled chunk (and no other chunk) could answer, and writes
`question -> chunk_id` pairs that `evals/retrieval_eval.py` scores every
retrieval arm against.

Sampling is stratified across all 18 books (round-robin, not proportional to
book length) so the largest book in the shelf cannot dominate the sample, and
seeded so a re-run reproduces the same chunk ids. Generation is one LLM call
per chunk, asking for several questions at once — batching questions within a
call is what keeps ~30-50 calls affordable instead of ~150-250 individual
round trips. A malformed or low-quality response for one chunk is dropped
with a warning; it never aborts the run.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import random
import re
import time
from collections.abc import Sequence
from pathlib import Path

from homelib_core.chunk import chunk_book
from homelib_core.models import BookDoc, Chunk
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

__all__ = [
    "GROUND_TRUTH_PATH",
    "SAMPLE_SEED",
    "SAMPLE_SIZE",
    "GroundTruthRow",
    "build_ground_truth",
    "generate_questions",
    "load_corpus_chunks",
    "sample_chunks",
    "write_ground_truth",
]

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / "data" / "corpus_snapshot.jsonl.gz"
GROUND_TRUTH_PATH = REPO_ROOT / "evals" / "ground_truth.jsonl"

# ~48 chunks * 5 questions/chunk lands comfortably inside the spec's
# 150-250 pair target even after filtering echoes/duplicates/short answers.
SAMPLE_SIZE = 48
SAMPLE_SEED = 0
QUESTIONS_PER_CHUNK = 5

_DEFAULT_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_API_KEY = "ollama"
_DEFAULT_MODEL = "qwen2.5:7b-instruct"
_TIMEOUT_SECONDS = 60.0

# A chunk below this many characters (or that looks like a table of contents:
# many short lines) rarely has enough substance to ask a specific question
# about, so it is excluded from the sampling pool entirely.
_MIN_CHUNK_CHARS = 400
_TOC_MIN_LINES = 4
_TOC_MAX_AVG_LINE_CHARS = 40

# A "question" shorter than this, or one that merely echoes the chunk's
# opening words, is not specific enough to be trustworthy ground truth.
_MIN_QUESTION_CHARS = 20
_ECHO_PREFIX_WORDS = 6

# How much of a chunk's text to send the LLM — plenty for a 7B model to
# ground a question in, without inflating prompt tokens (and latency) for no
# retrieval-quality benefit.
_MAX_CHUNK_CHARS_IN_PROMPT = 1800

_WORD_RE = re.compile(r"[a-z0-9]+")


class GroundTruthRow(BaseModel):
    """One `question -> chunk_id` ground-truth pair."""

    question: str
    chunk_id: str
    book_id: str


class _QuestionsResult(BaseModel):
    """Internal typed shape the LLM is asked to produce for one chunk."""

    model_config = ConfigDict(extra="allow")

    questions: list[str]


def load_corpus_chunks(path: Path = SNAPSHOT_PATH) -> list[Chunk]:
    """Recompute every chunk in the committed corpus snapshot.

    Deterministic given `chunk_book`'s defaults, so this matches what the
    ingest pipeline puts in the database — ground truth built from the
    snapshot points at real, retrievable chunk ids.
    """
    chunks: list[Chunk] = []
    with gzip.open(path, "rt", encoding="utf-8") as raw:
        for line in raw:
            line = line.strip()
            if not line:
                continue
            doc = BookDoc.model_validate_json(line)
            chunks.extend(chunk_book(doc))
    return chunks


def _normalize_words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _is_substantial(chunk: Chunk) -> bool:
    """Skip chunks too short, or too table-of-contents-like, to ask about."""
    text = chunk.text.strip()
    if len(text) < _MIN_CHUNK_CHARS:
        return False

    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= _TOC_MIN_LINES:
        avg_line_chars = sum(len(line) for line in lines) / len(lines)
        if avg_line_chars < _TOC_MAX_AVG_LINE_CHARS:
            return False
    return True


def sample_chunks(
    n: int,
    *,
    seed: int = SAMPLE_SEED,
    chunks: Sequence[Chunk] | None = None,
) -> list[Chunk]:
    """Stratified, seeded sample of up to `n` chunks spread across all books.

    Chunks are grouped by `book_id`, each book's substantial chunks are
    shuffled with a `random.Random(seed)` instance, and the sample is filled
    round-robin across books (in sorted `book_id` order) so a re-run with the
    same `seed` always yields the same chunk ids, and the longest book in the
    shelf cannot dominate the sample. `chunks` lets callers (tests) supply a
    fixture corpus instead of reading `SNAPSHOT_PATH`.
    """
    pool = chunks if chunks is not None else load_corpus_chunks()

    by_book: dict[str, list[Chunk]] = {}
    for chunk in pool:
        if _is_substantial(chunk):
            by_book.setdefault(chunk.book_id, []).append(chunk)

    books = sorted(by_book)
    if not books:
        return []

    rng = random.Random(seed)  # noqa: S311 - reproducible sampling, not security
    shuffled = {book: rng.sample(by_book[book], len(by_book[book])) for book in books}

    picks: list[Chunk] = []
    cursor = dict.fromkeys(books, 0)
    exhausted: set[str] = set()
    i = 0
    while len(picks) < n and len(exhausted) < len(books):
        book = books[i % len(books)]
        i += 1
        if book in exhausted:
            continue
        pos = cursor[book]
        book_chunks = shuffled[book]
        if pos >= len(book_chunks):
            exhausted.add(book)
            continue
        picks.append(book_chunks[pos])
        cursor[book] = pos + 1
    return picks


def _system_prompt(n: int) -> str:
    return (
        f"You write retrieval-eval questions for a search system over a library "
        f"of books. Given one passage, write {n} distinct questions that this "
        "exact passage -- and no other passage in the book -- could answer. "
        "Each question must be specific: name the people, events, claims, "
        "numbers, or terms the passage actually contains, so someone who has "
        "NOT read the passage could still tell, from the question alone, "
        "roughly what it discusses. Never ask a generic question like 'what is "
        "this passage about' or 'what does the author discuss'. Never restate "
        "the passage's opening sentence as a question. Crucially, never refer "
        "to the passage itself: phrases like 'according to the passage', 'in "
        "this text', 'the excerpt', or 'the author' are forbidden, because a "
        "search engine is given the question WITHOUT the passage and such "
        "wording carries no clue about which passage to find. Write each "
        "question as if asking someone who knows the whole library. Respond "
        "with ONLY a "
        'JSON object of the form {"questions": ["...", "..."]} and no other '
        "text."
    )


def _client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("LLM_BASE_URL", _DEFAULT_BASE_URL),
        api_key=os.environ.get("LLM_API_KEY", _DEFAULT_API_KEY),
        timeout=_TIMEOUT_SECONDS,
    )


def _model_name() -> str:
    return os.environ.get("LLM_MODEL", _DEFAULT_MODEL)


def _call_llm(chunk_text: str, n: int) -> str:
    """Call the configured LLM and return its raw response content.

    Raises on any transport/API failure (connection error, timeout, non-2xx
    response) or an empty/missing response body. Tests never reach this
    function with a live LLM — they stub `generate_questions` (or this
    function) directly.
    """
    passage = chunk_text[:_MAX_CHUNK_CHARS_IN_PROMPT]
    response = _client().chat.completions.create(
        model=_model_name(),
        messages=[
            {"role": "system", "content": _system_prompt(n)},
            {"role": "user", "content": passage},
        ],
        response_format={"type": "json_object"},
        timeout=_TIMEOUT_SECONDS,
    )
    if not response.choices:
        raise ValueError("empty LLM response: no choices returned")
    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty LLM response content")
    return content


def _echoes_opening(question: str, chunk_text: str) -> bool:
    """True if `question` just restates the chunk's opening words."""
    q_words = _normalize_words(question)[:_ECHO_PREFIX_WORDS]
    c_words = _normalize_words(chunk_text)[:_ECHO_PREFIX_WORDS]
    return bool(q_words) and q_words == c_words


# A question that points at "the passage" describes its own container rather
# than its subject. Retrieval is handed the question ALONE, so these carry no
# signal about which chunk to find and depress every arm equally — noise in the
# measurement dressed up as difficulty. The prompt forbids them; this rejects
# the ones a model emits anyway.
_SELF_REFERENTIAL_RE = re.compile(
    r"\b(?:according to|in|from|based on|per)\s+(?:this|the)\s+"
    r"(?:passage|text|excerpt|extract|paragraph|section|chapter)\b"
    # Verb-agnostic: "the passage implies", "does the passage imply", "the text
    # describes" are the same defect in different grammatical clothing.
    r"|\bthe\s+(?:passage|text|excerpt|extract|paragraph)\s+\w+s?\b"
    r"|\bas (?:described|mentioned|stated|discussed) (?:in|by) the (?:passage|text|author)\b",
    re.IGNORECASE,
)


def _is_self_referential(question: str) -> bool:
    """True when a question refers to its own source passage instead of its subject."""
    return _SELF_REFERENTIAL_RE.search(question) is not None


def _clean_questions(candidates: Sequence[str], chunk_text: str, n: int) -> list[str]:
    """Filter and dedupe raw LLM output down to at most `n` usable questions."""
    seen: set[tuple[str, ...]] = set()
    cleaned: list[str] = []
    for raw_question in candidates:
        question = raw_question.strip()
        if len(question) < _MIN_QUESTION_CHARS:
            continue
        if "?" not in question:
            continue
        if _echoes_opening(question, chunk_text):
            continue
        if _is_self_referential(question):
            continue

        key = tuple(_normalize_words(question))
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(question)
        if len(cleaned) >= n:
            break
    return cleaned


def generate_questions(chunk: Chunk, *, n: int = QUESTIONS_PER_CHUNK) -> list[str]:
    """One LLM call generating up to `n` specific, retrieval-shaped questions.

    Returns between 0 and `n` non-empty, deduplicated questions grounded in
    `chunk`. Never raises: a transport failure, empty response, or malformed
    JSON all result in an empty list, logged as a warning rather than
    aborting the caller's run.
    """
    try:
        raw = _call_llm(chunk.text, n)
    except Exception:
        logger.warning("question generation LLM call failed for chunk %s", chunk.chunk_id)
        return []

    try:
        parsed = _QuestionsResult.model_validate_json(raw)
    except ValidationError:
        logger.warning(
            "question generation returned unparseable output for chunk %s", chunk.chunk_id
        )
        return []

    return _clean_questions(parsed.questions, chunk.text, n)


def build_ground_truth(
    chunks: list[Chunk], *, questions_per_chunk: int = QUESTIONS_PER_CHUNK
) -> list[GroundTruthRow]:
    """Generate ground-truth rows for `chunks`, one LLM call per chunk.

    A chunk that returns fewer than `questions_per_chunk` usable questions
    (after one retry) is logged as a warning naming the actual count, not
    silently under-counted. Questions are deduplicated globally (not just
    within one chunk) so the committed file never has two rows sharing the
    same normalized question text.
    """
    rows: list[GroundTruthRow] = []
    seen_questions: set[tuple[str, ...]] = set()

    for chunk in chunks:
        questions = generate_questions(chunk, n=questions_per_chunk)
        if len(questions) < questions_per_chunk:
            retry = generate_questions(chunk, n=questions_per_chunk)
            for q in retry:
                if q not in questions:
                    questions.append(q)
            questions = questions[:questions_per_chunk]

        if len(questions) < questions_per_chunk:
            logger.warning(
                "chunk %s produced %d/%d usable questions after retry",
                chunk.chunk_id,
                len(questions),
                questions_per_chunk,
            )

        for question in questions:
            key = tuple(_normalize_words(question))
            if key in seen_questions:
                continue
            seen_questions.add(key)
            rows.append(
                GroundTruthRow(question=question, chunk_id=chunk.chunk_id, book_id=chunk.book_id)
            )

    return rows


def write_ground_truth(rows: list[GroundTruthRow], path: Path) -> None:
    """Write `rows` to `path` as JSON Lines, one `GroundTruthRow` per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row.model_dump(), ensure_ascii=False) + "\n")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    started = time.monotonic()

    chunks = sample_chunks(SAMPLE_SIZE, seed=SAMPLE_SEED)
    print(f"sampled {len(chunks)} chunks across {len({c.book_id for c in chunks})} books")

    rows = build_ground_truth(chunks)
    write_ground_truth(rows, GROUND_TRUTH_PATH)

    elapsed = time.monotonic() - started
    print(f"wrote {len(rows)} ground-truth pairs -> {GROUND_TRUTH_PATH} in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
