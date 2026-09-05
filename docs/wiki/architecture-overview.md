# Architecture overview

HomeLib is a local-first personal knowledge library: ingest books in multiple formats, search with hybrid retrieval, and answer questions with block-level citations. v2 extends v1 from a career-roadmap demo into a universal library product with demo and home editions from one codebase.

See [`specs/product.md`](../../specs/product.md) for the full product narrative.

---

## High-level system diagram

```mermaid
flowchart TB
    subgraph clients["Clients"]
        UI["Streamlit UI<br/>(apps/ui)"]
        API_docs["Swagger / OpenAPI"]
    end

    subgraph app["Application layer"]
        API["FastAPI<br/>(apps/api)"]
        Client["HomelibClient<br/>InProcess | Http"]
        Svc["Service layer<br/>(WP06+)"]
    end

    subgraph rag["Retrieval & generation"]
        Index["index.py<br/>lexical + vector"]
        Hybrid["hybrid.py<br/>RRF fusion"]
        Rerank["rerank.py"]
        Rewrite["rewrite.py"]
        Answer["answer.py / agent.py"]
    end

    subgraph ingest["Ingestion"]
        Parse["homelib-core<br/>parse_file()"]
        Chunk["chunk_book()"]
        DLT["dlt pipeline<br/>(apps/ingest)"]
    end

    subgraph store["Storage (edition-dependent)"]
        PG[("Postgres<br/>v1 fallback")]
        SQL[("SQLite + FTS5<br/>v2 target")]
        Matrix["NumPy embedding<br/>matrix cache"]
    end

    subgraph llm["LLM providers"]
        Ollama["Ollama / LM Studio"]
        Cloud["Managed cloud<br/>(demo)"]
    end

    UI --> Client
    Client --> API
    Client --> Svc
    API --> Svc
    Svc --> Index
    Index --> Hybrid
    Hybrid --> Rerank
    Rewrite --> Hybrid
    Svc --> Answer
    Answer --> llm

    Parse --> Chunk --> DLT
    DLT --> PG
    DLT --> SQL
    DLT --> Matrix
    Index --> PG
    Index --> SQL
    Index --> Matrix
```

**Boundary rule:** the UI never touches the database. All access goes through `HomelibClient` ([`specs/client.md`](../../specs/client.md)).

---

## v1 vs v2 migration story

| Aspect | v1 (`main`, tag `v1-fallback`) | v2 (`v2` + stacked `feat/wp*`) |
|---|---|---|
| Database | Postgres + `tsvector` + pgvector | SQLite + FTS5 + NumPy matrix ([ADR-004](../adrs/ADR-004-sqlite-replaces-postgres.md)) |
| Monitoring | Grafana (6 panels + feedback) | In-app Observatory ([ADR-005](../adrs/ADR-005-observatory-replaces-grafana.md)) |
| Editions | Single self-hosted compose stack | `APP_MODE=demo` \| `selfhosted` ([ADR-006](../adrs/ADR-006-editions-and-hosting.md)) |
| Identity | Implicit single user | Demo sessions + local principal ([`specs/principals.md`](../../specs/principals.md)) |
| API | 7 live endpoints (OpenAPI pinned) | Product §8 routes — incremental ([`specs/api.md`](../../specs/api.md)) |
| Deploy target | Docker Compose reviewer path | + Streamlit Community Cloud demo (submission day) |

**Migration strategy:** additive, not rip-and-replace. Postgres compose stays on `main` until v2 drill is green. v1 remains eligible as a submission fallback (`v1-fallback` tag). Chunk IDs and ground-truth evals must survive the store switch.

```mermaid
timeline
    title Store evolution
    v1 fallback : Postgres FTS + pgvector : Verified rubric-complete
    WP02 : SQLite schema + principals : Migrations + seed checksums
    WP03 : dlt → SQLite ELT : Same 18/729/9168 counts
    WP04 : FTS5 + matrix cache : Hybrid arms on SQLite
    WP06+ : New §8 API routes : OpenAPI snapshot regenerates
```

Evidence: [`docs/evidence.md`](../evidence.md) rows for WP02–WP04.

---

## Editions at a glance

From [`specs/editions.md`](../../specs/editions.md) and [ADR-006](../adrs/ADR-006-editions-and-hosting.md):

| Capability | Public showcase (`demo`) | Home / self-hosted (`selfhosted`) | Cloud trial (later) |
|---|---|---|---|
| Interface | Streamlit Community Cloud | Streamlit + FastAPI on LAN/localhost | Hosted web app |
| LLM | App-owner cloud key | LM Studio (Mac) or Ollama (Compose) | Managed + optional BYOK |
| Database | Resettable SQLite seed | Persistent mounted SQLite | Tenant DB |
| Identity | Random `demo_session_id` | Single `local_user` | OIDC |
| Uploads | Disabled | Enabled with rights declaration | Quota storage |
| Mutable state | Session-scoped, TTL | Persistent | Per-account |
| Client | `InProcessClient` | `HttpClient` | TBD |
| Monitoring | Observatory (in-app) | Observatory (Grafana panels are v1 and empty on this path) | TBD |

### Edition topology (who talks to what)

```mermaid
flowchart TB
    subgraph demo["APP_MODE=demo — Streamlit Community Cloud (bonus 11, owner deploy)"]
        D_UI[Streamlit app.py] -->|InProcessClient| D_ASGI[ApiClient over httpx.ASGITransport]
        D_ASGI --> D_API[FastAPI app in the same process]
        D_API --> D_DB[(seed homelib.sqlite<br/>inflated from data/seed/*.gz)]
        D_API -->|LLM_* from st.secrets| D_LLM[Groq — OpenAI-compatible]
        D_UI -. X-Demo-Session .-> D_API
    end
    subgraph compose["APP_MODE=selfhosted — docker compose (the reviewer path)"]
        C_UI[ui :8501] -->|HttpClient| C_API[api :8000]
        C_API --> C_DB[(data/homelib.sqlite<br/>just seed-sqlite)]
        C_API -->|LLM_BASE_URL| C_OLL[ollama qwen2.5:7b-instruct]
        C_ING[ingest one-shots] --> C_PG[(postgres — v1 store, Grafana)]
        C_ING --> C_DB
        C_GRAF[grafana :3001] --> C_PG
    end
    subgraph home["Home / LAN — same image, LM Studio or Ollama"]
        H_UI[ui] -->|HttpClient| H_API[api]
        H_API --> H_DB[(persistent SQLite)]
    end
```

The demo edition has no network hop between UI and API: `InProcessClient` wraps an `ApiClient` over `httpx.ASGITransport`, so route handlers, `LLM_*` wiring and the SQLite store are the same code as compose. The demo principal travels as `X-Demo-Session` (minted once per browser session, `ensure_demo_session`).

**Commercial packaging:** paid Home/Pro features land in the same Forgejo repo after public GitHub publish — not a second remote ([ADR-010](../adrs/ADR-010-commercial-split.md)).

---

## Stack: SQLite + FTS5 + NumPy + optional cloud LLM

### Storage ([ADR-004](../adrs/ADR-004-sqlite-replaces-postgres.md))

- **Lexical arm:** SQLite FTS5 virtual table (`chunks_fts`), BM25 ranking.
- **Vector arm:** Contiguous float32 NumPy matrix in memory, keyed by `index_revision`. Embeddings durable in DB/sidecar; matrix is the query cache — do not decode BLOBs per query.
- **Seed verification:** logical checksums and row counts, not byte-identical `.sqlite` files (SQLite headers/WAL differ across machines).

### Retrieval ([ADR-001](../adrs/ADR-001-retrieval-arm.md))

Production default: **`hybrid_rerank`** (RRF fusion + cross-encoder rerank). Query rewrite is **off** (measured negative result).

Dispatch: set `HOMELIB_SQLITE_PATH` to route `homelib_rag.index` to SQLite; unset uses Postgres (v1).

### LLM ([`specs/provider.md`](../../specs/provider.md))

OpenAI-compatible client. Local-first (Ollama/LM Studio); demo uses managed cloud with cost ceilings. Apple Foundation Models reserved — not capstone week.

### Ingestion

`apps/ingest/pipeline.py` — dlt ELT with staging → canonical sync, idempotent merge keys. v1 destination: Postgres. v2: SQLite ([`specs/ingestion.md`](../../specs/ingestion.md)).

---

## Home topology (self-hosted)

From product §4.3 and mockup `docs/mockups/00-home-topology.png`:

```mermaid
flowchart LR
    I["iPad / phone browser"] --> U["Streamlit on home Mac"]
    U --> A["HomeLib API + services"]
    A --> D["SQLite + local files"]
    A --> L["LM Studio or Ollama"]
    I --> P["Projector mirroring"]
```

The phone is controller and casting source; the Mac mini runs model and database.

---

## Related pages

- [Decision log](decision-log.md) — why each major choice was made
- [Retrieval pipeline](retrieval-pipeline.md) — arm details and degradation
- [Data model and schemas](data-model-and-schemas.md) — tables and API map
- [Local development](local-development.md) — run it yourself
