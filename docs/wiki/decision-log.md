# Decision log

Major fork-in-the-road decisions for HomeLib v2. Each entry lists options considered, trade-offs, the chosen path, and where it is recorded in code or ADRs.

For binding decisions, prefer the ADR file as canonical; this page is the navigational index.

---

## Hybrid search: BM25/FTS5 + vector + RRF vs alternatives

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Lexical only (FTS5 / tsvector)** | Fast (~77 ms), exact phrases, no embedding load | Misses paraphrase and semantic matches | Arm, not default |
| **Vector only (pgvector / matrix)** | Paraphrase-friendly | Weak on proper nouns, numbers; slower | Arm, not default |
| **Hybrid + RRF (k=60)** | +64% hit-rate vs best single arm on measured corpus | Both backends must be reachable for true hybrid | **Yes — fusion layer** |
| **Pure vector (no lexical)** | Simpler ops | Loses keyword precision; worse on this corpus | No |
| **Elasticsearch / OpenSearch** | Mature hybrid, scaling | Extra service; violates local-first / Community Cloud constraints | No |

**Chosen:** Reciprocal Rank Fusion of lexical + vector, production arm `hybrid_rerank` with cross-encoder rerank.

**Why:** Measured on 235 ground-truth questions — hybrid 0.174 hit-rate@5 vs vector 0.106. Fusion recovers complementary failures.

**Canonical:** [ADR-001](../adrs/ADR-001-retrieval-arm.md), [`specs/hybrid.md`](../../specs/hybrid.md)

---

## Vectorizer: ONNX vs torch vs cloud embeddings

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **sentence-transformers (torch)** | Course-aligned; already in v1 ingest; well-tested | ~420 MB RSS warm (WP04 probe on M4 Pro) | **Yes (v2 capstone week)** |
| **ONNX Runtime** | Lower memory; better Cloud fit | Migration cost; parity testing needed | Deferred — measure if torch exceeds Cloud 1 GB |
| **Cloud embedding API** | No local RAM | Privacy, cost, offline failure | No for home; demo precomputes seed |

**Chosen:** Keep `all-MiniLM-L6-v2` via torch for query-time embed; precomputed matrix at ingest for corpus vectors.

**Why:** Community Cloud memory decision uses documented 1 GB limit vs measured local RSS — not a live canary ([`docs/evidence.md`](../evidence.md) addendum §3). ONNX remains an extension point if deploy RSS fails.

**Canonical:** [`specs/indexing.md`](../../specs/indexing.md), [`specs/evals-retrieval.md`](../../specs/evals-retrieval.md)

---

## Storage: SQLite + FTS5 vs Postgres + pgvector

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Postgres + pgvector** | Proven on v1; rubric-verified | Second engine for demo; Compose weight | v1 fallback only |
| **SQLite + FTS5 + NumPy matrix** | Single file; resettable seed; Cloud-friendly | Two stores during migration; WAL discipline | **Yes (v2 target)** |
| **Qdrant / dedicated vector DB** | Scale | Extra service; overkill for 9k chunks | No |

**Chosen:** SQLite + FTS5 + cached NumPy matrix keyed by `index_revision`.

**Why:** One engine for demo and home; seed file shippable to Streamlit Cloud. v1 Postgres preserved until v2 drill green.

**Canonical:** [ADR-004](../adrs/ADR-004-sqlite-replaces-postgres.md)

---

## Observability: Observatory vs Grafana

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Grafana OSS container** | Rich SQL explorer; 6 panels verified on v1 | Second origin/port; not on Community Cloud | v1 fallback |
| **In-app Observatory (Streamlit)** | Single URL; demo traffic fills charts | Rebuild panel UX; lose Grafana explorer | **Yes (v2)** |

**Chosen:** Streamlit page over `query_log` / feedback aggregates.

**Why:** Public showcase cannot assume reviewers open port 3001 ([ADR-005](../adrs/ADR-005-observatory-replaces-grafana.md)).

**Canonical:** [ADR-005](../adrs/ADR-005-observatory-replaces-grafana.md), [`specs/observatory.md`](../../specs/observatory.md)

---

## Ingest: dlt ELT shape, staging → canonical, idempotency

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Ad-hoc SQL scripts** | Simple | No schema evolution; rubric wants dlt | No |
| **dlt merge into canonical only** | One destination | Schema migrations can break generated columns | No |
| **dlt staging → explicit canonical sync** | Idempotent; FK-ordered transform; rollback on error | More moving parts | **Yes** |
| **Truncate-and-reload** | Easy | Breaks uptime; not idempotent | No |

**Chosen:** dlt loads `homelib_staging` (SQLite: `homelib__homelib_staging.sqlite`); ordered transform to canonical tables in one transaction.

**Why:** Second run adds zero rows; rights gate and catalog errors roll back cleanly (WP03 evidence).

**Canonical:** [`specs/ingestion.md`](../../specs/ingestion.md), [`apps/ingest/pipeline.py`](../../apps/ingest/pipeline.py)

---

## Principal / demo session isolation model

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Shared mutable state** | Simple | Privacy leak between demo visitors | No |
| **Null-owner writes** | Easy defaults | Session A data visible to B | No |
| **Random `demo_session_id` → `principal_id` FK** | Isolation; resettable | Header/session plumbing | **Yes** |
| **OIDC accounts** | Production-grade | Out of capstone scope | Later |

**Chosen:** Every mutable row FKs non-null `principal_id`. Demo mints random session; restart/TTL wipes mutable rows, seed unchanged.

**Canonical:** [`specs/principals.md`](../../specs/principals.md), [`specs/data-model.md`](../../specs/data-model.md) §3

---

## Rights gate fail-closed

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Index unknown-rights text** | More searchable content | Legal and distribution risk | No |
| **Fail closed: metadata only** | Safe public history | Some Discover rows unusable for RAG | **Yes** |
| **Silent omit** | Clean UX | Hides why content missing | No |

**Chosen:** Unknown rights → no FTS5, no embedding matrix, no audio. UI explains restriction.

**Canonical:** [ADR-008](../adrs/ADR-008-rights-gate.md), [`specs/rights.md`](../../specs/rights.md)

---

## HomelibClient: InProcess vs Http

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **HTTP only (v1)** | Clear separation | Sidecar API on Community Cloud | v1 only |
| **InProcess for demo** | One process; lower latency | Must enforce import boundary | **Yes (`demo`)** |
| **Http for selfhosted** | Matches Compose topology | Network failures | **Yes (`selfhosted`)** |

**Chosen:** Protocol `HomelibClient` with `InProcessClient` and `HttpClient`; parametrized conformance tests.

**Why:** Streamlit Cloud runs single process; home edition keeps FastAPI sidecar ([`specs/client.md`](../../specs/client.md)).

---

## Chunk ID stability for eval ground truth

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Regenerate IDs on re-chunk** | Clean hashes | Breaks 235-question ground truth | No |
| **Stable v1 chunk_id scheme** | Eval regression comparable | Must preserve through SQLite migration | **Yes** |

**Chosen:** WP03 named test `test_chunk_ids_match_v1_snapshot`. Chunking params change → re-run pipeline, not re-fetch corpus.

**Canonical:** [`specs/chunking.md`](../../specs/chunking.md), [`evals/ground_truth.jsonl`](../../evals/ground_truth.jsonl)

---

## Seed determinism: logical checksums vs byte-identical SQLite

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Byte-identical committed `.sqlite`** | Simple reviewer story | Fails across OS/SQLite versions | No |
| **Logical checksums + row counts** | Honest rebuild verification | Requires documented verify command | **Yes** |
| **Byte-identical gzip snapshot (inputs)** | Offline ingest | N/A for DB file | **Yes for corpus JSONL** |

**Chosen:** `data/corpus_snapshot.jsonl.gz` is byte-stable (empty gzip filename). SQLite seeds verified by counts and logical checksums, not file hash.

**Why:** SQLite headers and WAL differ; gzip mtime lesson in evidence ([`docs/evidence.md`](../evidence.md) build_snapshot defects).

---

## Related ADRs (quick index)

| ADR | Topic |
|---|---|
| [ADR-001](../adrs/ADR-001-retrieval-arm.md) | hybrid_rerank; rewrite off |
| [ADR-002](../adrs/ADR-002-catalog-source.md) | Open Library yes; Kaggle/Google Books no |
| [ADR-003](../adrs/ADR-003-answer-prompt.md) | Incumbent prompt stays (null bake-off) |
| [ADR-004](../adrs/ADR-004-sqlite-replaces-postgres.md) | SQLite + FTS5 + matrix |
| [ADR-005](../adrs/ADR-005-observatory-replaces-grafana.md) | In-app monitoring |
| [ADR-006](../adrs/ADR-006-editions-and-hosting.md) | demo vs selfhosted; late Cloud deploy |
| [ADR-007](../adrs/ADR-007-licence-provisional.md) | Apache-2.0 provisional |
| [ADR-008](../adrs/ADR-008-rights-gate.md) | Unknown rights fail closed |
| [ADR-009](../adrs/ADR-009-audio-deferred.md) | TTS/STT deferred |
| [ADR-010](../adrs/ADR-010-commercial-split.md) | Single repo until publish |

---

## Answer prompt and rewrite (supplementary)

| Decision | Outcome | ADR |
|---|---|---|
| Query rewrite | Implemented, **default off** | ADR-001 |
| Answer prompt bake-off | Null result — incumbent stays | ADR-003 |
| Catalog source | Open Library metadata; banned scrapers grep-enforced | ADR-002 |

See [Retrieval pipeline](retrieval-pipeline.md) for degradation contracts.
