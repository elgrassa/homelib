# spec: ui — `apps/ui` (Streamlit Crossroads)

**Implemented by:** WP08 (static door grid, `HomelibClient`), WP09 (Projection),
WP10 (Observatory door), PR-B 2026-09-05 (Roadmap door, `DOOR_RENDERERS`),
PR-D (rotunda above the grid). **Supersedes** the v1 three-tab description that
lived here until 2026-09-05; the v1 tabs are on tag `v1-fallback`.

**Consumed by:** the human reviewer; nothing consumes this — it is the leaf.

## Purpose

One Streamlit page, `apps/ui/app.py`, that a reviewer reaches with zero setup
beyond `docker compose up` (selfhosted) or a Community Cloud URL (demo). The
binding constraint is unchanged: **the UI never opens a database connection and
never imports `homelib_rag` / `homelib_core` / `apps.store` internals — every
action goes through `HomelibClient`** (`specs/client.md`). Selfhosted uses
`HttpClient` (HTTP to FastAPI); demo uses `InProcessClient` (FastAPI in the same
process over `httpx.ASGITransport`). The AST boundary test stays. The same
container also runs the `:8502` clean-read companion (`apps/ui/read_server.py`),
an HTTP client of the API only.

## Public interface

```python
# apps/ui/view_model.py — pure, no Streamlit import
CROSSROADS_DOORS: tuple[str, ...]      # ("Ask", "Mentor", "Roadmap", "Coffee Table", "Shelf", "Observatory", "Projection")
def normalize_door(value: str) -> str  # raises ValueError on an unknown label
def ensure_demo_session(client, session_state, app_mode=None) -> str | None
def build_homelib_client() -> HttpClient | InProcessClient

# apps/ui/rotunda.py — pure (PR-D)
def build_rotunda_html(doors: Sequence[str], active: str, *, reduced_motion: bool = False) -> str
def door_from_query(params: Mapping[str, str], current: str, doors: Sequence[str]) -> str

# apps/ui/app.py
DOOR_RENDERERS: dict[str, Callable[[Client], None]]   # keys == CROSSROADS_DOORS, same order
def render_ask_tab(client) / render_mentor_tab / render_roadmap_tab / render_coffee_table_tab
def render_library_tab / render_observatory_tab / render_projection_tab
def main() -> None
```

## The doors

| Door | Client calls | Renders |
|---|---|---|
| Ask | `ask`, `get_block`, `submit_feedback` | answer, degraded banner when `degraded`, one expander per citation (lazy block fetch), 👍/👎 once per `request_id` |
| Mentor | `mentor_intake` | proposed path + notice; abstains rather than invents |
| Roadmap | `build_roadmap` | steps **in `order`** with prerequisites resolved to titles |
| Coffee Table | `get_playlist`, `add_playlist_item`, `accept_playlist`, `remove_playlist_item`, `save_progress` | current stack; `proposed` items need acceptance before they count |
| Shelf | `list_books` | table (`title`, `authors`, `blocks`, `chunks`, `format`) + ingest summary line |
| Observatory | `get_observatory` | ≥5 charts (nine chart defs shipped) + the feedback loop |
| Projection | `get_block`, `save_progress` | one-page reader with "Enter projector mode" |

Navigation: `st.session_state["door"]` holds the open door. It changes from the
button grid (always rendered) or from the rotunda's Enter link — a same-document
navigation to `?door=<label>` that `door_from_query` resolves and `normalize_door`
validates. An unknown `?door=` keeps the current door; it never raises.

## Data contracts (field-level)

No new shapes. Session state beyond one request/response cycle:

```
st.session_state["door"]: str                 # one of CROSSROADS_DOORS
st.session_state["demo_session_id"]: str      # demo only; sent as X-Demo-Session
st.session_state["last_ask"]: AskResponse | None
st.session_state["feedback_sent"]: set[str]   # request_ids already voted
st.session_state["last_roadmap"]: RoadmapResponse | None
```

## Error/degradation behavior

- `AskResponse.degraded == True` renders a visible banner — never hidden.
- Any `ApiClientError` / `ApiUnavailableError` inside a door renders `st.error`
  with the API's `detail`; each renderer catches its own errors so one failing
  door never takes the page down. The demo-session mint at the top of `main`
  degrades to `st.warning` for the same reason.
- Demo: a 401 (server forgot the session) is retried **once** with a fresh
  session by `ApiClient`; selfhosted never mints.
- The rotunda is an enhancement: if the component fails to render, the grid is
  the navigation. Reduced motion disables rotation, not entry.

## Named tests (all present)

- `test_ui_never_imports_database_or_internal_packages` — AST walk over `apps/ui`.
- `test_every_door_has_a_renderer_and_vice_versa` — `DOOR_RENDERERS` ≡ `CROSSROADS_DOORS`, same order.
- `test_every_door_renders_without_exception[door]` — `streamlit.testing.v1.AppTest`, API on a closed port.
- `test_door_grid_has_one_button_per_door`, `test_clicking_a_door_button_opens_that_door` — AppTest.
- `test_ensure_demo_session_mints_once_and_reuses_state`, `test_ensure_demo_session_is_a_noop_that_clears_in_selfhosted`.
- `test_rotunda_html_emits_door_param_link_for_every_door`, `test_rotunda_is_an_inline_fragment_not_an_iframe_document`, `test_rotunda_script_text_contains_no_markup_like_characters`, `test_unknown_door_param_falls_back_via_normalize_door`, `test_rotunda_html_neutralises_script_close` (PR-D).
- `test_specs_ui_door_list_matches_crossroads_doors` — this spec's door table is the code's tuple.

## Verify

```
uv run pytest apps/ui/tests -q
uv run streamlit run apps/ui/app.py --server.headless true &
curl -fs localhost:8501/_stcore/health
```
