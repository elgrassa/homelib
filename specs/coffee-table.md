# spec: coffee-table — persistent playlist (product §5.6)

**Implemented by:** WP07. Schema: WP02. **Consumed by:** UI, Mentor proposals,
`POST /v1/playlists/current*`. **Not this week:** paid household playlists.

## Purpose

The Coffee Table is an ordered, restart-persistent playlist — not a transient
recommendation strip. AI stacks are drafts until accepted. Manual items and
user order survive regeneration. Removing an item does not delete the resource.

## Public interface

```python
class PlaylistOrigin(StrEnum):
    MENTOR_PROPOSAL = "mentor_proposal"
    MANUAL_SHELF = "manual_shelf"
    MANUAL_DISCOVER = "manual_discover"
    ROADMAP = "roadmap"

class PlaylistStatus(StrEnum):
    PROPOSED = "proposed"
    QUEUED = "queued"
    READING = "reading"
    LISTENING = "listening"       # reserved; ADR-009, no production audio
    PAUSED = "paused"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    REMOVED = "removed"

class PlaylistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    resource_id: str
    book_id: str | None           # v1 corpus alias this week
    ordinal: int                  # 0-based, dense after compact
    origin: PlaylistOrigin
    status: PlaylistStatus
    accepted_at: datetime | None
    manual: bool                  # True ⇒ never auto-removed by regen

class Playlist(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    principal_id: str
    items: list[PlaylistItem]     # excluded: status=removed, unless include_removed
    last_opened_item_id: str | None
    updated_at: datetime
```

HTTP shapes: `specs/api.md` § v2.

## Data contracts (field-level)

```
playlist        id PK, principal_id FK NOT NULL, last_opened_item_id, updated_at
playlist_item   id PK, playlist_id FK, resource_id, book_id,
                ordinal int, origin, status, accepted_at, manual bool
```

Rules (product §5.6, plan WP07 red tests):

1. AI proposals require acceptance as a whole or per item before `queued`.
2. `manual is True` items are never removed by later Mentor regeneration.
3. User ordinals survive Mentor updates (regen only touches `proposed` rows).
4. `completed` or deliberately `removed` is not silently reinserted.
5. `removed` keeps the resource row; only the playlist membership ends.
6. Home/`selfhosted`: last-opened item + ordinals persist across process restart.
7. `demo`: playlist is session-scoped and wiped on reset/restart.

## Error/degradation behavior

- Null `principal_id` write → refused (`test_private_write_requires_principal`).
- Accept of unknown item ids → **404**.
- Reorder with a gap/duplicate ordinal → **422**; server does not auto-heal
  a malicious payload.
- Regen while items are `reading`/`paused` does not reset those rows.
- `listening` status may be stored; audio playback is Coming soon (ADR-009).

## Named red tests

- `test_acceptance_required_before_queued` — proposed items stay `proposed`
  until accept; they do not appear as the current reading stack.
- `test_manual_survives_regeneration`.
- `test_no_silent_reinsert_of_completed_or_removed`.
- `test_remove_keeps_resource`.
- `test_independent_read_listen_progress` — see `specs/progress.md`.
- `test_restart_persists` — see `specs/principals.md`.

## Verify

```
uv run pytest -k 'playlist or coffee_table or acceptance_required' -v
```
