# spec: rotunda — Library Crossroads doors (product §5.2)

**Implemented by:** WP08 (static door grid first), PR-D 2026-09-05
(`apps/ui/rotunda.py` + `rotunda_template.html`, rendered inline through
`st.html(unsafe_allow_javascript=True)`). **Consumed by:** the Crossroads in
`apps/ui/app.py`. The HTML prototype in `docs/mockups/` was the template's
source; its six named wings and regex "search" did **not** ship — doors come
from `CROSSROADS_DOORS`. Enter is a same-document link (`<a href="?door=X">`):
the iframe route (`st.iframe` / `components.v1.html`) was tried first and
Streamlit's iframe sandbox has no `allow-top-navigation`, so a parent
navigation from inside it is a SecurityError. The static grid beneath the
room is always rendered: if the script fails, the grid is the navigation.

## Purpose

Present Areas and Wings as doors. Useful before magical: an accessible list
or grid must work if the animated room is disabled. AI never silently
creates an active Wing; it proposes, the user accepts (`POST /v1/wings`).

## Public interface

UI state (not a table):

```
active_area_id: str | None
active_wing_id: str | None     # URL query so refresh/back work
reduced_motion: bool           # cross-fades instead of rotation
```

Door positions when the custom component ships: center, near-left,
near-right, far-left, far-right; wrap indefinitely. Clicking a side door
rotates it to center before entry.

Seed wings may resemble the HTML six-name fixture; the schema is
user-extensible (`specs/data-model.md` contradiction 2).

## Data contracts (field-level)

Areas/Wings HTTP: `specs/api.md`. HTML `wings[].kind` values (`topic wing` /
`crossroads` / `hidden door`) are a hint, not a closed enum.

Paid rotunda assets and polished sphere: **not this week** (ADR-010).

## Error/degradation behavior

- No Wing match → Mentor proposal, not an auto-created row.
- Custom component failure / reduced-motion / missing WebGL → static grid
  of the same `GET /v1/wings` payload.
- HTML regex routing (`destination`) is **not** a retrieval arm.

## Named red tests

- `test_crossroads_renders_static_doors_from_wings_list` — mock GET wings;
  at least one accessible control per wing (`aria-label` Enter {name}).
- `test_url_state_round_trips_active_wing`.
- `test_mentor_cannot_insert_active_wing_without_post` — service-level;
  WP06/WP02.

## Verify

```
uv run pytest apps/ui/tests -k 'crossroads or rotunda or static_door' -v
```
