# User flows

Sequence and flow diagrams for primary user journeys. **Implemented** flows note their evidence; **spec-level** flows describe product intent before full UI/API merge (WP06–WP08).

References: [`specs/product.md`](../../specs/product.md) §§2, 5; [`specs/principals.md`](../../specs/principals.md).

---

## Cold start / demo session

Public showcase: every browser gets an isolated session; seed corpus is shared read-only.

```mermaid
sequenceDiagram
    participant Browser
    participant Streamlit
    participant Store as SQLite seed
    participant LLM as Cloud LLM

    Browser->>Streamlit: Open app URL
    Streamlit->>Streamlit: Mint demo_session_id (Session State)
    Streamlit->>Store: Ensure principal + demo_session row
    Streamlit->>Browser: Banner "Public showcase — may reset"
    Note over Streamlit,Store: Seed books/chunks/wings readable without session

    Browser->>Streamlit: Ask question (first visit)
    Streamlit->>Store: Hybrid search (seed corpus)
    Streamlit->>LLM: Grounded answer generation
    LLM-->>Streamlit: Answer + citations
    Streamlit->>Store: INSERT query_log (principal_id)
    Streamlit-->>Browser: Answer + block_id citations
```

**Implemented:** v1 ask path on Postgres; v2 demo rehearsal = `APP_MODE=demo` + SQLite tests (WP02–WP04). Full `InProcessClient` — spec/WP08.

**Rules:** mutable rows FK `principal_id`; null-owner writes refused; uploads disabled in demo ([`specs/editions.md`](../../specs/editions.md)).

---

## Search → cited answer

Library-wide question with hybrid retrieval and citation validation.

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant API
    participant Index
    participant Hybrid
    participant Rerank
    participant Answer
    participant LLM

    User->>UI: Enter query
    UI->>API: POST /v1/ask {query, k, arm?}
    opt rewrite flag (default off)
        API->>Answer: rewrite_query(q)
        Answer-->>API: q or rewritten q
    end
    API->>Index: search_lexical + search_vector
    Index-->>API: Hit lists
    API->>Hybrid: hybrid_search (RRF k=60)
    Hybrid-->>API: fused hits, mode_used
    opt arm = hybrid_rerank
        API->>Rerank: rerank(q, hits)
        Rerank-->>API: reordered hits or None
    end
    API->>Answer: build prompt from hits
    Answer->>LLM: chat completion (JSON citations)
    LLM-->>Answer: raw structured output
    Answer->>Answer: Validate chunk_id + quote vs hits
    Answer-->>API: AskResponse + degraded flag
    API-->>UI: answer, citations (chunk_id + block_id)
    UI-->>User: Render + "open source" uses block_id
```

**Implemented:** v1 on Postgres (`POST /v1/ask`). v2 adds `POST /v1/search` with scene modes — WP06.

**Degradation:** vector down → lexical-only, `mode_used=lexical`; LLM down → 200 + `degraded: true`; rerank fail → keep fusion order ([Retrieval pipeline](retrieval-pipeline.md)).

---

## Scene anchor open

Within-book search → open reader at exact offsets.

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant API
    participant Scene as scene_search
    participant Blocks

    User->>UI: "Find the passage about…" (in reader)
    UI->>API: POST /v1/resources/{id}/search {mode, query}
    API->>Scene: Scope to resource (optional chapter)
    Scene->>Scene: Exact / Keyword / Semantic / Smart
    Scene-->>API: SceneHit[] with open_anchor=block_id
    API-->>UI: hits + char_start/end + quote
    User->>UI: Open hit
    UI->>API: GET /v1/blocks/{block_id}
    API->>Blocks: Load block text + section_path
    Blocks-->>UI: Full block for projection reader
    UI-->>User: Two-page view at offset
```

**Implemented:** WP04 scene search tests (`test_open_anchor_always_resolves`, scope leak reds). HTTP route — spec/WP06.

**Invariant:** `open_anchor` must always resolve; citing `chunk_id` to `/v1/blocks/` 404'd in v1 drill ([`docs/evidence.md`](../evidence.md)).

Modes: [`specs/scene-search.md`](../../specs/scene-search.md) — Exact→Keyword→Semantic→Smart work offline; Ask needs LLM.

---

## Coffee Table playlist (spec-level)

Persistent reading stack with acceptance gate — schema WP02, business logic WP07.

```mermaid
flowchart TD
    A[Mentor proposes path] --> B{User accepts?}
    B -->|whole stack| C[Items → queued]
    B -->|per item| D[Selected items → queued]
    B -->|reject| E[Items stay proposed or removed]
    C --> F[Coffee Table UI]
    D --> F
    G[Manual add from Shelf/Discover] --> F
    F --> H{Regenerate from Mentor?}
    H --> I[Update proposed rows only]
    I --> J[manual=true items kept]
    I --> K[completed/removed not reinserted]
    F --> L[Reorder ordinals]
    L --> M[Persist last_opened_item_id]
```

Item lifecycle as the store enforces it (`apps/store/coffee_table.py`):

```mermaid
stateDiagram-v2
    [*] --> proposed: Mentor proposes (origin=mentor)
    [*] --> queued: manual add from Shelf / Ask (manual=true)
    proposed --> queued: accept (whole stack or per item) — accepted_at set
    proposed --> removed: reject
    proposed --> proposed: Mentor regen replaces proposed rows only
    queued --> completed: PATCH /v1/playlists/current/items status=completed
    queued --> listening: status=listening — stored, audio is Coming soon per ADR-009
    listening --> completed
    queued --> removed: DELETE item — resource row kept
    completed --> [*]
    removed --> [*]
    note right of queued
        manual=true items survive regeneration;
        user ordinals survive Mentor updates
    end note
    note right of completed
        completed / removed are never
        silently re-inserted by regen
    end note
```

**Rules** ([`specs/coffee-table.md`](../../specs/coffee-table.md)):

1. AI proposals require acceptance before `queued`.
2. Manual items survive regeneration.
3. User order preserved across regen.
4. Remove ≠ delete resource.

**Demo vs home:** demo playlist wiped on reset; selfhosted survives restart (`test_restart_persists`).

---

## Ingest pipeline run

Offline seed load: snapshot → chunks → embeddings → store.

```mermaid
sequenceDiagram
    participant Op as Operator
    participant Build as build_snapshot
    participant Pipe as dlt pipeline
    participant Staging
    participant Canon as Canonical DB
    participant Rights

    Op->>Build: corpus files → JSONL.gz (optional refresh)
    Op->>Pipe: run_pipeline(snapshot)
    Pipe->>Pipe: Parse BookDoc → chunk_book()
    Pipe->>Pipe: embed_texts (MiniLM-L6-v2)
    Pipe->>Staging: dlt merge books/blocks/chunks
    Pipe->>Rights: Check rights_status per book
    Rights-->>Pipe: can_index_text false → skip FTS/embed
    Pipe->>Canon: Ordered sync (FK-safe transaction)
    Canon-->>Op: LoadInfo counts
    Op->>Op: Second run → zero new rows (idempotent)
```

**Implemented:**

- v1: Postgres — 37 tests, 18/729/9168/9168 ([`docs/evidence.md`](../evidence.md) WP-09).
- v2: SQLite — WP03, same counts, chunk IDs match v1.

**Entry points:**

```bash
just seed                                    # v1 compose ingest profile
uv run python -m apps.ingest.pipeline        # direct
uv run python -m apps.ingest.build_snapshot  # rebuild snapshot from books/
```

---

## Demo reset

Wipe mutable state; restore seed checksums.

```mermaid
sequenceDiagram
    participant Admin as Process restart / TTL job
    participant Store
    participant Seed

    Admin->>Store: CASCADE delete mutable principal rows
    Note over Store: playlist, progress, conversations, bookmarks, user areas
    Admin->>Store: Increment reset_generation (demo sessions)
    Admin->>Seed: Verify book/chunk/wing counts + logical checksums
    Seed-->>Admin: Match canonical seed
    Admin-->>Admin: New visitors mint fresh demo_session_id
```

**Triggers:** `APP_MODE=demo` process restart; expired session TTL; explicit reset API (WP02).

**Test:** `test_demo_reset_restores_seed` — seed unchanged, private tables empty.

---

## Related pages

- [Architecture overview](architecture-overview.md)
- [Data model and schemas](data-model-and-schemas.md)
- [Local development](local-development.md)
