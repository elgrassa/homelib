# spec: principals — demo sessions and local-user identity

**Implemented by:** WP02. **Consumed by:** every mutating §8 route, Coffee Table,
progress, Mentor, feedback. Schema draft: `specs/data-model.md` §3.

## Purpose

Every private write has a non-null principal. The public showcase never shares
mutable state between browsers. Home edition is one local principal on one
SQLite file. Null-owner writes are refused, not silently attributed.

## Public interface

```python
class PrincipalKind(StrEnum):
    DEMO_SESSION = "demo_session"
    LOCAL_USER = "local_user"

class Principal(BaseModel):
    id: str
    kind: PrincipalKind
    created_at: datetime

class DemoSession(BaseModel):
    id: str                          # random; also the Streamlit session key
    principal_id: str
    created_at: datetime
    expires_at: datetime             # TTL; cleaned on restart in APP_MODE=demo
    reset_generation: int

class UserRepository(Protocol):
    def current(self) -> Principal: ...
    def require_write(self) -> Principal: ...   # raises if principal is missing
```

Identity source:

| `APP_MODE` | Principal | How it is established |
|---|---|---|
| `demo` | `demo_session` | Random `demo_session_id` in Streamlit Session State (and `X-Demo-Session-Id` on HTTP). Mutable rows FK this principal. Restart + TTL wipe mutable rows. |
| `selfhosted` | `local_user` | Single well-known local principal. Persistent. LAN PIN / household profiles are **not** this week (ADR-010). |
| later | OIDC | Out of scope. |

## Data contracts (field-level)

```
principal      id: str PK
               kind: "demo_session"|"local_user"
               created_at: datetime

demo_session   id: str PK
               principal_id: str FK principal NOT NULL
               created_at: datetime
               expires_at: datetime
               reset_generation: int

X-Demo-Session-Id   request header on mutating HTTP calls in APP_MODE=demo
                    InProcessClient reads Streamlit session state instead
```

Shared seed (`books`, `chunks`, seed `wings`/`areas`, `catalog`) is read-only
and has no owner. Private tables (`playlist`, `playlist_item`, `read_progress`,
`listen_progress`, `conversation`, `message` (WP06), `feedback`, `bookmarks`,
principal-owned `areas`) require `principal_id` NOT NULL on mutating rows.

## Error/degradation behavior

- Missing principal on a private write → **403** (`detail` names the missing
  owner). Never insert with `principal_id` NULL.
- Unknown / expired demo session on a mutating route → **401**; the client
  mints a new session and retries once.
- Session A cannot read session B's playlist, conversation, progress, bookmarks,
  principal-owned areas, or feedback. A leaked id is not an ACL bypass: queries
  filter by the authenticated principal, not by a client-supplied owner field.
- `APP_MODE=demo` restart restores seed counts; all mutable principal rows are
  gone (`test_demo_reset_restores_seed`).
- Health and public catalog/search of the seed corpus do not require a session.

## Named red tests

- `test_private_write_requires_principal` — INSERT playlist / progress /
  conversation / feedback with `principal_id` NULL is refused.
- `test_demo_sessions_cannot_read_each_other` — two sessions; A cannot SELECT
  B's private rows (playlist, read_progress, conversation, bookmarks,
  principal-owned areas).
- `test_demo_reset_restores_seed` — after reset, seed book/chunk/wing counts
  and logical checksums match canonical seed; private rows are empty.
- `test_restart_persists` — `APP_MODE=selfhosted`: playlist ordinal, last-opened
  item, and read progress survive process restart on the same SQLite file.

## Verify

```
uv run pytest -k 'principal or demo_session or demo_reset or restart_persists' -v
```
