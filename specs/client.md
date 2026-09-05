# spec: client — `HomelibClient` in-process vs HTTP seam

**Implemented by:** WP08. **Consumed by:** Streamlit UI only.
**Product:** §7.1. v1 `apps/ui` `ApiClient` is HTTP-only; v2 adds in-process
for Community Cloud (one Streamlit process, no sidecar API).

## Purpose

One service layer, two clients. The UI must not import SQLite, parsers, or
provider SDKs. A parametrized suite runs the same behaviour against both
clients so demo and selfhosted cannot diverge.

## Public interface

```python
class HomelibClient(Protocol):
    def health(self) -> Health: ...
    def search(self, body: SearchRequest) -> SearchResponse: ...
    def ask(self, body: AskRequest) -> AskResponse: ...
    def mentor_intake(self, body: MentorIntakeRequest) -> MentorIntakeResponse: ...
    def create_path(self, body: CreatePathRequest) -> PathResponse: ...
    def list_areas(self) -> list[Area]: ...
    def create_area(self, body: CreateAreaRequest) -> Area: ...
    def list_wings(self, *, area_id: str | None = None) -> list[Wing]: ...
    def create_wing(self, body: CreateWingRequest) -> Wing: ...
    def list_resources(self, **filters: object) -> ResourceList: ...
    def scene_search(self, resource_id: str, body: SceneSearchRequest) -> SceneSearchResponse: ...
    def get_block(self, block_id: str) -> Block: ...
    def get_playlist(self) -> Playlist: ...
    def accept_playlist(self, body: PlaylistAcceptRequest) -> Playlist: ...
    def add_playlist_item(self, body: AddPlaylistItemRequest) -> Playlist: ...
    def patch_playlist_items(self, body: PatchPlaylistItemsRequest) -> Playlist: ...
    def delete_playlist_item(self, item_id: str) -> Playlist: ...
    def record_progress(self, body: ProgressEvent) -> dict: ...
    def add_bookmark(self, body: BookmarkRequest) -> Bookmark: ...
    def submit_feedback(self, body: FeedbackRequest) -> dict: ...
    def observatory(self) -> ObservatoryResponse: ...
    def audio_capabilities(self) -> AudioCapabilities: ...

class InProcessClient:   # APP_MODE=demo; calls the application service layer
    ...
class HttpClient:        # APP_MODE=selfhosted; FastAPI, per-call timeouts
    ...
```

Request/response models: `specs/api.md`. Timeouts: LLM-touching calls use
the Compose default (300s), not a 10s blanket (v1 UI bug).

v1 methods `build_roadmap` / `list_books` remain until WP08 migrates the
tabs; new screens must not call them.

## Data contracts (field-level)

AST boundary (port v1 `test_ui_module_has_no_db_or_psycopg_import`):
`apps/ui/**` must not import `psycopg`, `sqlite3` (except tests),
`homelib_core` parsers, `homelib_rag` internals, `sqlalchemy`, `dlt`, or
vendor SDKs. Shared Pydantic models re-exported for typing are allowed.

`X-Demo-Session` (the header the route reads — the earlier `-Id` spelling never
shipped): both clients expose `create_demo_session() -> str` (`POST /v1/demo/session`)
and `set_demo_session(id | None)`. `apps.ui.view_model.ensure_demo_session` mints
once per browser session, keeps the id in Streamlit session state under
`demo_session_id`, and re-attaches it on every rerun (each rerun builds a fresh
client). In `selfhosted` it clears the id, so a leaked `APP_MODE=demo` cannot make
the client send one. `ApiClient._request` retries a 401 **exactly once**, and only
when a session id is set: mint a fresh session, resend. A selfhosted 401 propagates.
`InProcessClient` forwards both methods explicitly (no `__getattr__`).

## Error/degradation behavior

- Same status codes and bodies on both clients (conformance suite).
- Unreachable HTTP API → UI `st.error`, not a crash of other tabs (v1).
- `AskResponse.degraded` still shows the banner.

## Named red tests

- `test_ui_boundary_forbids_store_and_provider_imports` — AST walk, port v1.
- `test_inprocess_http_conformance_health` — parametrize both clients.
- `test_inprocess_http_conformance_ask_degraded_flag`.
- `test_http_client_ask_timeout_is_not_ten_seconds`.
- `test_demo_session_header_sent_on_playlist_and_progress_calls` — both clients.
- `test_create_demo_session_returns_id_on_both_clients`.
- `test_request_retries_once_with_fresh_session_on_401_in_demo`.
- `test_request_does_not_remint_on_401_in_selfhosted`.
- `test_401_retry_happens_at_most_once`.
- `test_ensure_demo_session_mints_once_and_reuses_state` (view model).
- `test_demo_mode_same_header_shares_principal_and_missing_header_does_not` (route).

## Verify

```
uv run pytest apps/ui/tests -v -k 'boundary or conformance or HomelibClient'
```
