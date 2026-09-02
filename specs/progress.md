# spec: progress — reading and listening positions

**Implemented by:** WP07. Schema: WP02. **Consumed by:** reader, projection,
Coffee Table last-opened, `POST /v1/progress`. **ADR-009:** listen column
reserved; no production audio this week.

## Purpose

Reading position and listening position are independent. A restart in
`selfhosted` restores both. Demo sessions wipe progress on reset.

## Public interface

```python
class ProgressKind(StrEnum):
    READ = "read"
    LISTEN = "listen"

class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_id: str
    kind: ProgressKind
    block_id: str | None
    char_offset: int | None       # index into canonical_text
```

Unknown fields → **422**.

HTTP: `specs/api.md` `POST /v1/progress` → `{ok: true}`.

## Data contracts (field-level)

```
read_progress     principal_id FK NOT NULL, resource_id, book_id,
                  block_id, char_offset, updated_at
                  PK (principal_id, resource_id)

listen_progress   same columns as read_progress (ADR-009)
                  POST kind=listen may persist a row; no player this week
```

`char_offset` must satisfy `0 <= offset <= len(canonical_text)` when a local
document exists; metadata-only Discover rows reject progress with **409**.

## Error/degradation behavior

- Null principal → refused.
- Unknown `resource_id` → **404**.
- `kind=listen` is accepted (200) and stored; UI must not imply audio exists
  unless `GET /v1/audio/capabilities`.preview_available.
- Demo reset deletes both tables' rows for that principal.

## Named red tests

- `test_independent_read_listen_progress` — writing read does not overwrite
  listen (and vice versa) for the same resource.
- `test_restart_persists` — selfhosted file still has the last read offset.
- `test_demo_reset_restores_seed` — progress rows gone after demo reset.

## Verify

```
uv run pytest -k 'progress or restart_persists or demo_reset' -v
```
