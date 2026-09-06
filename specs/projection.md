# spec: projection — projector reading mode (product §5.9)

**Implemented by:** WP09. **Consumed by:** reader UI. Cut order: one-page
first; two-page after that is stable.

## Purpose

iPad/Android browser mirrored to a wall projector. The user **explicitly**
enters projector mode — do not infer it from viewport width (mirroring may
report iPad dimensions).

## Public interface

```python
class ProjectionLayout(StrEnum):
    ONE_PAGE = "one_page"
    TWO_PAGE = "two_page"          # landscape only; fallback to one_page

# UI flags, not API this week unless a query param is needed:
# ?projection=1 hides Streamlit chrome / ordinary nav
# ?source=official|shelf — Projector submenu (default shelf; official =
#   Pottermore publisher links, metadata only). The internal two-page viewer
#   is opt-in via HOMELIB_OFFICIAL_VIEWER (owner's LAN box) — off by default,
#   never on the public demo.
# Official preview language default: uk (Pottermore Ukrainian HP)
```

Anchors (`open_anchor` / `block_id` + offsets) must survive font-size and
pagination changes. Progress: `specs/progress.md`; `selfhosted` survives
browser reconnect; `demo` may reset.

## Data contracts (field-level)

Required behaviour (acceptance, not extra endpoints):

- 16:9 stage; large type; high contrast
- large next/previous targets; swipe + keyboard
- optional family mode hides technical controls
- same page controls when mirrored or HDMI

Audio play/pause sharing reader state is Coming soon (ADR-009) except the
one bundled preview.

## Error/degradation behavior

- Two-page on a narrow viewport → one-page without error.
- Missing `block_id` in projection → do not blank the stage; show last
  good page or the book start.
- Projection must not call LAN-exposed FastAPI; only Streamlit (editions).

## Named red tests

- `test_projection_flag_not_inferred_from_viewport_alone`.
- `test_anchor_survives_font_size_change`.
- `test_one_page_fallback_when_two_page_unavailable`.

## Verify

```
uv run pytest apps/ui/tests -k 'projection or anchor_survives' -v
# manual: iPad/Android landscape smoke recorded in evidence at WP09
```
