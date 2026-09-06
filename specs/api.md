# spec: api — `apps/api` (FastAPI)

**Implemented by (v1, live):** WP-14 (ask/roadmap), WP-16 (feedback), WP-09 (ingest).
**v2 target:** WP06–WP10 implement product.md §8. This file is the field-level
contract. **`specs/openapi.snapshot.json` stays the v1 snapshot until the
first API implementation PR** (plan WP01: drift test from that PR, not this
docs WP). Public request models: `extra="forbid"`. Provider payloads:
`raw_json` only.

**Consumed by:** Streamlit via `specs/client.md` (`InProcessClient` |
`HttpClient`), demo scripts, Swagger.

## Purpose

The single contract every consumer talks through. The UI has **no** database
access; if something is not on this surface, the UI cannot do it. FastAPI
auto-generates OpenAPI at `/openapi.json` and Swagger UI at `/docs` — that is
the reviewer-facing API documentation, and the README links it.

Identity: mutating v2 routes require a principal (`specs/principals.md`).
`APP_MODE=demo` sends `X-Demo-Session`; missing owner → **403**, never a
null-owner insert.

## Endpoints — live v1 (OpenAPI snapshot)

These paths are what `test_openapi_snapshot_matches` pins today.

| Endpoint | Request | Response |
|---|---|---|
| `GET /health` | — | `Health {status, db: bool, llm: {provider, model, reachable: bool}, books: int, chunks: int}` |
| `POST /v1/ask` | `AskRequest {query: str, k: int = 5, arm: "lexical"\|"vector"\|"hybrid"\|"hybrid_rerank"\|None, rewrite: bool = false}` | `AskResponse {request_id, answer, citations: list[Citation], arm_used: str, degraded: bool, latency_ms: int, tokens: {prompt: int, completion: int}, trace_id: str\|None}` |
| `POST /v1/roadmap` | `RoadmapRequest {interests: list[str], level: "beginner"\|"intermediate"\|"advanced", goal: str, max_steps: int = 8}` | `RoadmapResponse {request_id, steps: list[RoadmapStep], rationale: str}` |
| `POST /v1/ingest` | `IngestRequest {path: str} \| {source: "snapshot"}` | `IngestResponse {book_id, blocks: int, chunks: int, extraction: ExtractionResult}` |
| `POST /v1/feedback` | `FeedbackRequest {request_id: str, feedback: "up"\|"down", comment: str\|None}` | `{ok: true}` |
| `GET /v1/books` | — | `list[BookSummary {book_id, title, authors, blocks, chunks, format}]` |
| `GET /v1/books/{book_id}/blocks` | `ordinal: int = 0` | `Block` (Projection page by dense ordinal) |
| `GET /v1/blocks/{block_id}` | — | `Block` |
| `GET /v1/traces/{trace_id}` | — | `TraceResponse {trace_id, spans: list[TraceSpanNode]}` (C5, specs/monitoring.md "Tracing"; SQLite-only, 503 without `HOMELIB_SQLITE_PATH`) |

Supporting shapes:

```
Citation    {chunk_id, block_id, book_id, book_title, section_path: list[str],
             page: int|None, quote: str}
RoadmapStep {order: int, ol_key: str|None, book_id: str|None, title: str,
             authors: list[str], why: str, prerequisites: list[int],
             est_effort: "light"|"medium"|"deep"}

PathStepPreview {order: int, title: str, why: str,
                 est_effort: "light"|"medium"|"deep" | None = None}
                 # mentor-intake proposal only; no persisted ids yet

PathStep          same fields as RoadmapStep (persisted `POST /v1/paths`)
```

`Citation` carries **both** a `chunk_id` and a `block_id`, and the distinction
is load-bearing rather than redundant. A chunk is the retrieval unit; a block is
the document unit a reader opens, and `GET /v1/blocks/{block_id}` is keyed on
the latter. Passing a `chunk_id` there returns 404 — which is precisely how the
UI's "show full source" action was broken until the cold-clone drill tried to
resolve a real citation end to end. A citation nobody can open is not a
citation, so the id needed to open it belongs in the shape.

`arm: None` on `/v1/ask` means "use the production winner" — the arm chosen on
evidence in `docs/adrs/ADR-001-retrieval-arm.md`, not a hardcoded preference.

## v2 target — product.md §8 (markdown this WP; not in the snapshot yet)

All request models `extra="forbid"` (unknown JSON → **422**). Shared
`degraded: bool` means a fallback path ran; never a silent 500 for vector/LLM
down. `Citation` is unchanged from v1 (both `chunk_id` and `block_id`).

### `GET /health`

Request: none.

Response `Health`:

```
status: "ok"|"degraded"
db: bool
llm: {provider: str, model: str, reachable: bool}   # never keys
books: int
chunks: int
index_revision: str | None          # v2; null until WP04 matrix exists
app_mode: "demo"|"selfhosted"       # v2
```

### `POST /v1/search`

Request `SearchRequest`:

```
query: str                          # required, stripped; empty → 422
mode: "exact"|"keyword"|"semantic"|"smart"   # default "smart"
k: int = 5                          # 1..50
wing_id: str | None
area_id: str | None
scope: "library"|"wing"|"shelf"|"discover" = "library"
```

Response `SearchResponse`:

```
request_id: str
hits: list[SearchHit]
mode_used: str                      # arm actually used after degradation
degraded: bool
latency_ms: int
```

`SearchHit`: `resource_id, book_id, chunk_id, block_id, title, section_path,
quote, score, char_start, char_end, open_anchor, rights_status`.

LLM offline: Exact/Keyword/Semantic/Smart still return hits.

### `POST /v1/ask`

Keep the live v1 `AskRequest` / `AskResponse`. Optional v2 fields (additive,
defaults keep v1 behaviour):

```
conversation_id: str | None = None
wing_id: str | None = None
resource_id: str | None = None      # book/chapter scope when set
```

Do not add these to the OpenAPI snapshot until the route is implemented.

### `POST /v1/mentor/intake`

Replaces the *product* role of v1 `POST /v1/roadmap` (that path stays live
until WP06 removes or aliases it).

Request `MentorIntakeRequest`:

```
goal: str                           # required
interests: list[str] = []
level: "beginner"|"intermediate"|"advanced"|None = None
```

Response `MentorIntakeResponse`:

```
request_id: str
proposed_area: {name: str, copy: str | None} | None
proposed_wing: {name: str, area_name: str | None, copy: str | None} | None
proposed_path: {title: str, kind: "reading"|"learning"|"action",
                steps: list[PathStepPreview]} | None
rationale: str
citations: list[Citation]
degraded: bool
high_stakes_notice: str | None      # informational; never auto-executes
```

None of the proposed rows are persisted as active Areas/Wings/playlist items
until the user POSTs the accept routes.

### `POST /v1/paths`

Request `CreatePathRequest`:

```
intake_request_id: str | None
title: str
kind: "reading"|"learning"|"action"
steps: list[PathStep]               # same fields as v1 RoadmapStep
```

Response `PathResponse`: `{path_id, title, kind, steps, accepted: true}`.
POST **creates an accepted artifact** (user already confirmed). Fail-closed
parse; one bounded repair (v1 roadmap lesson).

### `GET /v1/areas` / `POST /v1/areas`

GET → `list[Area {id, name, copy, wing_count: int}]` (seed + principal’s own).

POST `CreateAreaRequest {name: str, copy: str | None}` → `Area`.
AI must not call this without user confirmation.

### `GET /v1/wings` / `POST /v1/wings`

GET query: `area_id: str | None`.

Response `list[Wing {id, area_id, name, kind: str, copy, resource_count: int}]`.

POST `CreateWingRequest {area_id: str, name: str, kind: str | None, copy: str | None}`
→ `Wing`. Same acceptance rule as Areas.

### `GET /v1/resources`

Query: `source: "shelf"|"discover"|None`, `wing_id`, `q`, `rights_status`,
`format`, `language`.

Response `ResourceList`:

```
items: list[ResourceSummary]
unique_count: int                   # not the sum of provider counts
approximate_provider_counts: dict[str, int]   # UI prefixes ~
degraded: bool                      # a connector timed out
```

`ResourceSummary`: `id, book_id | None, title, authors: list[str],
source: "shelf"|"discover", rights_status, can_index_text, full_text_available,
format | None`.

v1 `GET /v1/books` remains until WP08; `book_id` is the citation identity
this week (`specs/data-model.md` naming confusion).

### `POST /v1/resources/{id}/search`

See `specs/scene-search.md`. Request `SceneSearchRequest`:

```
query: str
mode: "exact"|"keyword"|"semantic"|"smart"|"ask"
chapter_id: str | None = None
k: int = 5
```

Response `SceneSearchResponse`: `{request_id, resource_id, hits: list[SceneHit],
mode_used, degraded, latency_ms}`.

### `GET /v1/books/{book_id}/blocks`

Query `ordinal` (default `0`, must be ≥ 0). Returns the `Block` at that dense
ordinal for Projection Prev/Next. Unknown book/ordinal → **404**.

### `GET /v1/blocks/{id}`

Unchanged: `Block` (`specs/core-models.md`). `{id}` is **block_id**, not
chunk_id. Product §8 name for the v1 route.

### `GET /v1/playlists/current` / `POST /v1/playlists/current`

GET → `Playlist` (`specs/coffee-table.md`). Empty table → `{items: [], ...}`
200, not 404.

POST `PlaylistAcceptRequest {accept_item_ids: list[str] | None}` — `None`
accepts all `proposed` items. Response: `Playlist`.

### `POST /v1/playlists/current/items`

`AddPlaylistItemRequest {resource_id: str, origin: PlaylistOrigin}` → `Playlist`.

### `PATCH /v1/playlists/current/items`

`PatchPlaylistItemsRequest {items: list[{id: str, ordinal: int | None,
status: PlaylistStatus | None}]}` → `Playlist`. Unknown id → **404**.
Duplicate/gap ordinals → **422**.

### `DELETE /v1/playlists/current/items/{item_id}`

Sets `status=removed`; resource row remains. Response: `Playlist`.

(Product lists DELETE on the collection; a single-item path is the
unambiguous reading. Do not delete-by-body-only without an id.)

### `POST /v1/progress`

Request: `ProgressEvent` (`specs/progress.md`). Response `{ok: true}`.

### `POST /v1/bookmarks`

Request `BookmarkRequest {resource_id, block_id, char_start, char_end,
note: str | None}`. Response `Bookmark {id, ...same fields, created_at}`.

### `POST /v1/feedback`

Unchanged v1. Comment optional.

### `GET /v1/observatory`

Response: `ObservatoryResponse` (`specs/observatory.md`). Never plaintext
queries or keys.

### `GET /v1/audio/capabilities`

Response: `AudioCapabilities` (`specs/audio.md`). `can_generate` is false
this week.

## Error and degradation behavior

- Errors use FastAPI's envelope: `HTTPException` → `{detail: str}`.
- `POST /v1/feedback` with an unknown `request_id` → **404**. Feedback that
  cannot be attached to a real request is a bug, not a no-op.
- `GET /v1/blocks/{id}` on an unknown id → **404**.
- **A degraded backend is never a 500.** If the vector index or the LLM is
  unreachable, `/v1/ask` returns **200** with `degraded: true` and `arm_used`
  naming the arm it actually fell back to. Callers can tell a partial answer
  from a healthy one by reading the response, not by catching an exception.
- `/health` reports **booleans only** about the LLM — provider name, model
  name, reachability. Never key material, never a redacted-but-present key.

## Contract-drift guard

`evals/tests/test_openapi_snapshot.py` asserts the generated `openapi.json`
(paths, schema names, required fields) matches the committed
`specs/openapi.snapshot.json`. Changing the **implemented** API means
regenerating the snapshot in the same PR — deliberately, with the diff
visible in review. WP01 does not add routes; leaving the snapshot on v1 is
intentional, not drift.

**Known gap (C5):** `GET /v1/traces/{trace_id}` was added and the snapshot
regenerated in the same commit, per this rule — but
`test_snapshot_covers_every_endpoint_in_api_md`'s `expected_paths` set is a
literal list hardcoded in that same evals/ test file, and that file was out
of scope for the C5 change (edits to anything under `evals/` other than
importing `evals/judge.py` were explicitly disallowed for that work). That
one assertion is red until a session in scope for `evals/` adds
`/v1/traces/{trace_id}` to its `expected_paths` literal —
`test_openapi_snapshot_matches` (the actual drift guard against the
committed snapshot) and the two required-field tests are unaffected and
green.

## Named red tests

- `test_openapi_snapshot_matches` — the drift guard above.
- `test_feedback_unknown_request_id_returns_404`.
- `test_ask_degrades_to_200_when_vector_backend_down` — vector search raises,
  response is 200 with `degraded is True` and `arm_used == "lexical"`.
- `test_health_never_leaks_key_material` — `/health` body contains no substring
  of the configured `LLM_API_KEY`.
- v2 (first API PR, not this WP): `test_search_unknown_fields_422`;
  `test_private_write_requires_principal` on playlist POST;
  `test_blocks_chunk_id_still_404`.

## Verify

```
uv run pytest apps/api/tests evals/tests/test_openapi_snapshot.py -v
curl -s localhost:8000/openapi.json | python -c "import json,sys; print(sorted(json.load(sys.stdin)['paths']))"
curl -s localhost:8000/health
```
