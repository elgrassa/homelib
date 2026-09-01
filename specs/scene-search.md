# spec: scene-search — within-book exact/keyword/semantic/smart/ask

**Implemented by:** WP04 (retrieval arms + anchors), WP06 (Ask mode).
**Consumed by:** `POST /v1/resources/{id}/search`, reader “open the scene”.
**Product:** §5.7. Eval extras: exact-offset accuracy, scope-leak count.

## Purpose

Find a remembered scene and open it at the original character offsets. Every
result carries `open_anchor` that `GET /v1/blocks/{id}` can resolve. A
chapter- or book-scoped query must never leak hits from another scope after
rewrite.

## Public interface

```python
class SceneMode(StrEnum):
    EXACT = "exact"         # normalized phrase; original offsets; no LLM
    KEYWORD = "keyword"     # FTS5/BM25; no LLM
    SEMANTIC = "semantic"   # vector; no LLM
    SMART = "smart"         # hybrid + optional rerank; no LLM
    ASK = "ask"             # Smart then cited synthesis; LLM required

class SceneHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_id: str
    chapter_id: str | None
    block_id: str
    chunk_id: str | None
    char_start: int
    char_end: int
    quote: str
    prev_context: str
    next_context: str
    open_anchor: str        # opaque; GET /v1/blocks/{block_id} must 200
```

Library-wide search is `POST /v1/search` (`specs/api.md`); this spec is
**within one resource**. Modes Exact/Keyword/Semantic/Smart work with the
LLM offline (`test_search_with_llm_unreachable`).

## Data contracts (field-level)

Normalization maps to **original** `canonical_text` offsets (v1 chunker
invariant: `canonical_text[start:end] == text`). `open_anchor` is the
block_id (v1 lesson: citing a chunk_id and resolving `/v1/blocks/{chunk_id}`
404s).

Scope:

- default: the path `{id}` resource only
- optional `chapter_id`: that chapter's blocks only
- rewrite (Ask/Smart) must re-apply the same scope after expansion

## Error/degradation behavior

- Unknown resource → **404**.
- Metadata-only / `can_index_text=false` → **409** with rights explanation
  (not an empty hit list pretending to have searched).
- Vector down → Keyword/Exact still run; `degraded: true` if Smart/Semantic
  was requested (`test_vector_down_degrades_flagged`).
- Ask + LLM unreachable → 200 + `degraded: true` + Smart hits, no synthesis.
- `open_anchor` that does not resolve is a product bug; never return it.

## Named red tests

- `test_exact_offsets_map_to_original_text`.
- `test_chapter_scope_never_leaks`.
- `test_book_scope_survives_rewrite`.
- `test_open_anchor_always_resolves`.
- `test_search_with_llm_unreachable`.

## Verify

```
uv run pytest -k 'scene or open_anchor or scope_never_leaks' -v
```
