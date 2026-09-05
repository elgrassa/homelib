# spec: answer — `homelib_rag.answer`

**Implemented by:** WP-14 · **Consumed by:** `apps/api` (`POST /v1/ask`), `homelib_rag.agent`.

## Purpose

Synthesize an `AskResponse`-shaped answer from a question and a set of
already-retrieved hits, with block-level citations (`book · section_path ·
page`). The binding contract this spec exists to enforce: every
`Citation.chunk_id` in the response must resolve to a chunk that actually
exists in `hits`, and every `Citation.quote` must be genuinely present,
verbatim, in that chunk's text. An answer that cites something it was not
given is the primary defect this spec prevents — it is never passed through
as if trustworthy. Also specifies the degradation contract: an unreachable
LLM yields a `200` with `degraded: true`, never a `500`, and a degraded
answer is never persisted or presented as a normal one.

## Public interface

```python
def answer(
    question: str,
    hits: list[Hit],              # specs/indexing.md
    *,
    client: OpenAICompatibleClient,
    arm_used: str,
) -> AskResponse                   # specs/api.md — request_id, answer, citations,
                                    # arm_used, degraded, latency_ms, tokens

class CitationValidationError(Exception): ...

def _validate_citations(citations: list[Citation], hits: list[Hit]) -> None   # raises CitationValidationError
def _degraded_response(arm_used: str, reason: str) -> AskResponse
```

## Data contracts (field-level)

`AskResponse`, `Citation` — defined in `specs/api.md`; not redefined here.
`Hit` — defined in `specs/indexing.md`; not redefined here.

Contract added by this spec, on top of the field list in `specs/api.md`:

```
Citation.chunk_id   MUST equal the chunk_id of one of the `hits` passed into
                    this call — the model is only shown `hits`, so a
                    citation outside that set could not have come from a
                    real retrieval
Citation.quote      MUST be an exact substring of the matching hit's `text`
                    field — paraphrase is not a quote; the model is
                    instructed to quote verbatim and the output is checked,
                    not trusted
```

## Error and degradation behavior

- **LLM unreachable** (connection error/timeout): caught inside `answer()`
  and turned into `_degraded_response(arm_used, reason)` — `AskResponse`
  with `degraded=True`, a generic fallback `answer`, `citations=[]`,
  `tokens={"prompt": 0, "completion": 0}`. This is returned as a normal
  `200`; `answer()` never raises for connectivity failure, so `apps/api`
  never needs to translate an exception into the degradation contract here.
- **Hallucinated or malformed citation**: after the LLM responds,
  `_validate_citations` checks every citation against `hits` per the
  contract above. If any citation's `chunk_id` is absent from `hits`, or its
  `quote` is not a verbatim substring of the matching hit's text,
  `_validate_citations` raises `CitationValidationError`. `answer()` catches
  this specific error and returns `_degraded_response(...)` — the untrustworthy
  answer is never forwarded to the caller as if it were normal. This is the
  primary defect this spec exists to prevent.
- **Persistence contract**: any `AskResponse` with `degraded=True` must be
  recorded as degraded wherever it is logged or shown (query_log `degraded`
  flag, UI degraded marker) — `answer()`'s responsibility is limited to
  setting `degraded` accurately on every path; downstream consumers rely on
  that field being correct, not inferred.

## Named red tests

- `test_citations_resolve` — for a normal (non-degraded) response, every
  `Citation.chunk_id` corresponds to one of the input `hits`' `chunk_id`
  values.
- `test_citation_quote_present_verbatim_in_chunk` — for each citation,
  `quote` is a substring of the matching hit's `text`; a scripted fake LLM
  that returns a fabricated quote not present in the chunk text causes a
  degraded fallback instead of being passed through unchecked.
- `test_llm_unreachable_returns_degraded_200` — the client raises a
  connection error; assert `answer()` returns an `AskResponse` with
  `degraded is True` rather than raising or producing a `500`.
- `test_hallucinated_citation_triggers_degradation` — a scripted fake LLM
  cites a `chunk_id` absent from `hits`; assert `result.degraded is True`
  and `result.citations == []`, i.e. the fabricated citation is never
  surfaced as trustworthy.

## Verify

```
uv run pytest packages/homelib-rag/tests/test_answer.py evals/tests/test_citations.py -v
uv run pytest packages/homelib-rag/tests/test_answer.py -k "citations_resolve or quote_present or unreachable or hallucinated" -v
uv run mypy --strict packages/homelib-rag/src/homelib_rag/answer.py
```

## Store dispatch (2026-09-05)

`_book_metadata(book_ids)` — the title/authors lookup that fills `Citation.book_title`
and the prompt context — dispatches on the same predicate as `homelib_rag.index`
(ADR-004): when `HOMELIB_SQLITE_PATH` is non-empty it reads the SQLite `books`
table via `homelib_rag.sqlite_index.book_metadata` (JSON `authors` decoded, malformed
→ `[]`); otherwise Postgres. Before this, a SQLite-only host degraded **every** answer
after a successful retrieval. Pinned by
`test_answer_end_to_end_not_degraded_on_sqlite_only_host` (scripted LLM, no Postgres).
