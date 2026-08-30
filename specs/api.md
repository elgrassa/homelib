# spec: api — `apps/api` (FastAPI)

**Implemented by:** WP-14 (ask/roadmap), WP-16 (feedback), WP-09 (ingest).
**Consumed by:** the Streamlit UI, the demo scripts, and reviewers via Swagger.

## Purpose

The single contract every consumer talks through. The UI has **no** database
access; if something is not on this surface, the UI cannot do it. FastAPI
auto-generates OpenAPI at `/openapi.json` and Swagger UI at `/docs` — that is
the reviewer-facing API documentation, and the README links it.

## Endpoints (all under `/v1` except health)

| Endpoint | Request | Response |
|---|---|---|
| `GET /health` | — | `Health {status, db: bool, llm: {provider, model, reachable: bool}, books: int, chunks: int}` |
| `POST /v1/ask` | `AskRequest {query: str, k: int = 5, arm: "lexical"\|"vector"\|"hybrid"\|"hybrid_rerank"\|None, rewrite: bool = true}` | `AskResponse {request_id, answer, citations: list[Citation], arm_used: str, degraded: bool, latency_ms: int, tokens: {prompt: int, completion: int}}` |
| `POST /v1/roadmap` | `RoadmapRequest {interests: list[str], level: "beginner"\|"intermediate"\|"advanced", goal: str, max_steps: int = 8}` | `RoadmapResponse {request_id, steps: list[RoadmapStep], rationale: str}` |
| `POST /v1/ingest` | `IngestRequest {path: str} \| {source: "snapshot"}` | `IngestResponse {book_id, blocks: int, chunks: int, extraction: ExtractionResult}` |
| `POST /v1/feedback` | `FeedbackRequest {request_id: str, feedback: "up"\|"down", comment: str\|None}` | `{ok: true}` |
| `GET /v1/books` | — | `list[BookSummary {book_id, title, authors, blocks, chunks, format}]` |
| `GET /v1/blocks/{block_id}` | — | `Block` |

Supporting shapes:

```
Citation    {chunk_id, book_id, book_title, section_path: list[str],
             page: int|None, quote: str}
RoadmapStep {order: int, ol_key: str|None, book_id: str|None, title: str,
             authors: list[str], why: str, prerequisites: list[int],
             est_effort: "light"|"medium"|"deep"}
```

`arm: None` on `/v1/ask` means "use the production winner" — the arm chosen on
evidence in `docs/adrs/ADR-001-retrieval-arm.md`, not a hardcoded preference.

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
`specs/openapi.snapshot.json`. Changing the API means regenerating the snapshot
in the same PR — deliberately, with the diff visible in review.

## Named red tests

- `test_openapi_snapshot_matches` — the drift guard above.
- `test_feedback_unknown_request_id_returns_404`.
- `test_ask_degrades_to_200_when_vector_backend_down` — vector search raises,
  response is 200 with `degraded is True` and `arm_used == "lexical"`.
- `test_health_never_leaks_key_material` — `/health` body contains no substring
  of the configured `LLM_API_KEY`.

## Verify

```
uv run pytest apps/api/tests evals/tests/test_openapi_snapshot.py -v
curl -s localhost:8000/openapi.json | python -c "import json,sys; print(sorted(json.load(sys.stdin)['paths']))"
curl -s localhost:8000/health
```
