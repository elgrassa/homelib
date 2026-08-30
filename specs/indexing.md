# spec: indexing — `homelib_rag.index`

**Implemented by:** WP-10. **Consumed by:** `homelib_rag.hybrid` (WP-11), `homelib_rag.rerank` (WP-13), `apps/api` `/v1/ask` (WP-14).

## Purpose

Two independent retrieval arms over the same Postgres store — lexical (full-text
search) and semantic (vector similarity) — each returning a ranked list of
chunks a caller can cite back to a page. This is the floor both `hybrid_search`
and the eval harness are built on: if either arm is wrong, everything above it
is wrong for a reason nobody will see until the eval table looks strange.

## Public interface

```python
class Hit(BaseModel):
    chunk_id: str
    book_id: str
    score: float
    rank: int              # 1-based position in THIS arm's ranking
    text: str
    section_path: list[str]
    page: int | None

def search_lexical(q: str, k: int) -> list[Hit]: ...
def search_vector(q: str, k: int) -> list[Hit]: ...
```

`Hit` is defined once, here. `hybrid.md`, `rerank.md`, and `rewrite.md` reference
it by name — they do not redefine its fields.

## Data contracts (field-level)

Schema created by `docker/initdb/*.sql`, read by both search functions:

```sql
books             (book_id text PRIMARY KEY, title text, authors text[],
                   language text, source_url text, license_note text)

blocks            (block_id text PRIMARY KEY, book_id text REFERENCES books,
                   ordinal int, section_path text[], text text,
                   char_start int, char_end int,
                   format text, page int, spine_index int, anchor text)

chunks            (chunk_id text PRIMARY KEY, book_id text REFERENCES books,
                   block_ids text[], section_path text[], text text,
                   char_start int, char_end int,
                   tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED)
INDEX             ix_chunks_tsv ON chunks USING GIN (tsv)

chunk_embeddings  (chunk_id text PRIMARY KEY REFERENCES chunks,
                   embedding vector(384))          -- all-MiniLM-L6-v2, 384-dim
INDEX             ix_chunk_embeddings_cosine ON chunk_embeddings
                   USING ivfflat (embedding vector_cosine_ops)

catalog           (ol_key text PRIMARY KEY, title text, authors text[],
                   subjects text[], first_publish_year int,
                   description text, provenance_note text)

query_log         (request_id text PRIMARY KEY, ts timestamptz, latency_ms int,
                   arm text, k int, rerank boolean, rewrite boolean,
                   model text, tokens_prompt int, tokens_completion int,
                   query_sha256_prefix text,     -- 16-char sha256 prefix, never plaintext by default
                   degraded boolean NOT NULL DEFAULT false,  -- answer served from a fallback path
                   feedback text)                -- "up"|"down"|NULL
```

- `search_lexical(q, k)`: `plainto_tsquery('english', q)` against `chunks.tsv`,
  ranked by `ts_rank_cd(tsv, query)`. `Hit.score` is the raw `ts_rank_cd` value
  (not normalized across arms — normalization is `hybrid.md`'s job).
- `search_vector(q, k)`: embed `q` with the pinned `all-MiniLM-L6-v2` model
  (same model used at ingest, `EMBED_MODEL` env var), cosine distance against
  `chunk_embeddings.embedding` (`<=>` operator), `Hit.score = 1 - distance`.
- `page` is `blocks.page` for the first block in `chunk.block_ids` that has one,
  else `None` (EPUB-only chunks carry no page).
- Both functions return **at most `k`** hits, ordered best-first, `rank` starting
  at 1 with no gaps.

## Error/degradation behavior

- Empty `q` (after strip) raises `ValueError` — never silently returns `[]`
  masquerading as "no results" when the real cause is a bad call.
- `k <= 0` raises `ValueError`.
- A Postgres connection failure raises the underlying `psycopg` error — `index.py`
  does not swallow it. Degradation to a working arm is `hybrid.md`'s
  responsibility, not this module's; `search_lexical`/`search_vector` are
  honest about their own backend being down.
- No embedding model loaded (misconfigured `EMBED_MODEL`) raises at import/first
  call, not silently returning zero vectors.

## Named red tests (write before the code)

- `test_search_lexical_ranks_exact_phrase_above_scattered_terms` — seeded
  mini-corpus, a chunk containing the exact query phrase outranks a chunk
  containing the same terms scattered across unrelated sentences.
- `test_search_vector_finds_semantic_match_without_shared_terms` — a query and
  a chunk share no lexical terms but are semantically related (paraphrase
  fixture); `search_vector` returns it in the top-k, `search_lexical` does not.
- `test_hit_rank_is_dense_1_based_and_matches_score_order` — for both arms,
  `rank` values are `1..len(hits)` with no gaps and non-increasing `score`.
- `test_search_lexical_empty_query_raises`.
- `test_page_is_none_for_epub_only_chunk`.

## Verify

```
uv run pytest packages/homelib-rag/tests/test_index.py -v
docker compose -f docker/docker-compose.yml exec postgres psql -U homelib -c "\d chunks" | grep -i tsv
docker compose -f docker/docker-compose.yml exec postgres psql -U homelib -c "\d chunk_embeddings" | grep -i vector
```
