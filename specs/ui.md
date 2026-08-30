# spec: ui — `apps/ui` (Streamlit)

**Implemented by:** WP-14 (ask tab, against the live API), WP-16 (feedback wiring), WP-17 (library tab polish).
**Consumed by:** the human reviewer; nothing consumes this — it is the leaf.

## Purpose

A reviewer-facing surface with zero setup beyond `docker compose up`, built
entirely on the public API contract in `specs/api.md`. The binding constraint:
**the UI never opens a database connection or imports anything from
`homelib_rag`/`homelib_core` internals — every action is an HTTP call to
`API_URL`.** This keeps the API the single contract every consumer, including
the UI itself, is forced to go through.

## Public interface

```python
# apps/ui/client.py — the ONLY module allowed to make network calls
class ApiClient:
    def __init__(self, base_url: str) -> None: ...
    def ask(self, query: str, *, k: int = 5, arm: str | None = None, rewrite: bool = True) -> AskResponse: ...
    def get_block(self, block_id: str) -> Block: ...
    def submit_feedback(self, request_id: str, feedback: Literal["up", "down"]) -> None: ...
    def build_roadmap(self, interests: list[str], level: str, goal: str, max_steps: int = 8) -> RoadmapResponse: ...
    def list_books(self) -> list[BookSummary]: ...

# apps/ui/app.py
def render_ask_tab(client: ApiClient) -> None: ...
def render_roadmap_tab(client: ApiClient) -> None: ...
def render_library_tab(client: ApiClient) -> None: ...
```

`AskResponse`, `Citation`, `RoadmapRequest`/`RoadmapResponse`, `BookSummary`,
`Block` are all defined once in `specs/api.md` / `specs/core-models.md` — this
spec imports them by name, it does not redefine their fields.

## Data contracts (field-level)

No new data shapes. The UI's only state beyond one HTTP request/response cycle
is Streamlit session state holding the last `AskResponse` (so citation
expanders and the feedback buttons can reference `request_id` without a second
`/v1/ask` call), keyed:

```
st.session_state["last_ask"]: AskResponse | None
st.session_state["feedback_sent"]: set[str]     # request_ids already voted on, to disable double-submit
```

**Ask tab:** query input -> `client.ask(...)` -> renders `answer`, then one
expander per `Citation` (`book_title · section_path · page`); expanding a
citation lazily calls `client.get_block(citation.chunk_id-derived block id)`
to show the full source block, not just the `quote` already in the response.
👍/👎 buttons call `client.submit_feedback(request_id, ...)` and then disable
themselves via `feedback_sent`.

**Roadmap tab:** a form (`interests` free-text split on commas, `level`
selectbox, `goal` free-text) -> `client.build_roadmap(...)` -> renders
`steps` **in `order`**, each with `title`, `authors`, `why`, and its
`prerequisites` resolved to the titles of the referenced earlier steps (not
raw integers).

**Library tab:** `client.list_books()` rendered as a table (`title`, `authors`,
`blocks`, `chunks`, `format`) plus a summary line (`sum(blocks)`, `sum(chunks)`,
book count) as the ingest-stats readout.

## Error/degradation behavior

- `AskResponse.degraded == True` renders a visible banner above the answer
  ("answered with a degraded backend: {arm_used}") — the UI never hides a
  degraded response as if it were a clean one.
- A `4xx`/`5xx` from any `ApiClient` call surfaces as `st.error(...)` with the
  response's `detail` field (specs/api.md's error envelope); the UI never
  crashes the whole page on one failed call — each tab's render function
  catches its own client errors.
- `submit_feedback` on an already-voted `request_id` (present in
  `feedback_sent`) is a no-op in the UI layer — the button is disabled, so the
  second `POST /v1/feedback` (which would 404 if `request_id` were somehow
  wrong, or double-count if not) is never sent.
- `API_URL` unreachable at startup: every tab shows a single shared "backend
  unavailable" state instead of three independent stack traces; `client.ask`
  etc. raising a connection error is caught once at the top of `app.py`.
- The UI holds **no** database credentials and imports **no** module from
  `packages/homelib-core` or `packages/homelib-rag` other than the Pydantic
  response models re-exported for typing — enforced by the red test below.

## Named red tests (write before the code)

- `test_ui_module_has_no_db_or_psycopg_import` — static check: `grep`/AST-walk
  `apps/ui/**/*.py` and assert no import of `psycopg`, `sqlalchemy`, or any
  `homelib_core.*`/`homelib_rag.*` submodule beyond the shared Pydantic models;
  behavioral, run as a real test over the actual source tree, not a comment.
- `test_ask_tab_shows_degraded_banner_when_response_degraded` — `ApiClient`
  mocked to return `AskResponse(degraded=True, ...)`; rendered output (via
  Streamlit's `AppTest` harness) contains the degraded banner text.
- `test_feedback_button_disabled_after_vote` — simulate one 👍 click via
  `AppTest`, assert the button is disabled on rerender and `submit_feedback`
  was called exactly once.
- `test_roadmap_steps_render_in_order` — mocked `RoadmapResponse` with steps
  `order=[3,1,2]`; rendered list appears in `1,2,3` order.
- `test_library_tab_summary_matches_book_list` — mocked `list_books()` of 3
  books; rendered summary line's totals equal the hand-summed `blocks`/`chunks`.
- `test_api_client_error_does_not_crash_other_tabs` — `ask` raises a connection
  error; `render_roadmap_tab` and `render_library_tab` still render without
  raising when called independently in the same `AppTest` session.

## Verify

```
uv run pytest apps/ui/tests -v
uv run python -c "import ast,pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('apps/ui').rglob('*.py')]"   # no import errors
uv run streamlit run apps/ui/app.py --server.headless true &  # smoke boot, kill after health check
curl -fs localhost:8501/_stcore/health
```
