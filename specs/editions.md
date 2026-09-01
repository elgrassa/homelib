# spec: editions — `APP_MODE` and the capability matrix

**Implemented by:** WP00 skeleton (config only); behaviour lands with WP02–WP11.
**Consumed by:** provider, principals, audio, UI banners, Compose profiles.
**ADRs:** ADR-006 (editions/hosting), ADR-010 (no paid tier this week).

## Purpose

Two editions from one codebase this week. A third (persistent cloud trial) is
post-capstone. Paid Home/Pro packaging stays out of the public schema until
after `just publish` (ADR-010).

## Public interface

```python
class AppMode(StrEnum):
    DEMO = "demo"
    SELFHOSTED = "selfhosted"

class EntitlementProvider(Protocol):
    def mode(self) -> AppMode: ...
    def uploads_enabled(self) -> bool: ...
    def audio_generation_enabled(self) -> bool: ...   # False this week
    def persistence(self) -> Literal["session", "sqlite_file"]: ...
```

```env
APP_MODE=demo|selfhosted
LLM_MODE=managed|openai_compatible|apple_future
LLM_BASE_URL=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=300          # Compose/reviewer default (plan §0.2)
LLM_MAX_OUTPUT_TOKENS=800        # canonical default; paths/roadmap routes may request up to 1600
HOMELIB_BIND=127.0.0.1           # lan profile is an explicit opt-in
```

`LLM_TIMEOUT_SECONDS=90` in product.md §7.2 is the **demo / cloud-provider**
suggestion. Reviewer Compose stays **300** (v1 measured ~70s uncontended on
CPU-only in-VM Ollama). Do not silently tighten Compose to 90.

`LLM_MAX_OUTPUT_TOKENS=800` is the **canonical env default** (matches
`.env.example` and `apps/runtime_settings.py`). `POST /v1/paths` and v1
`POST /v1/roadmap` may pass up to **1600** to the provider for structured
path output (v1 truncation lesson) — that is a per-route ceiling, not a second
default.

## Data contracts (field-level)

| Capability | `demo` | `selfhosted` |
|---|---|---|
| Interface | Streamlit, in-process client | Streamlit + FastAPI HTTP client |
| LLM | App-owner cloud (`ManagedCloudProvider`) | LM Studio preferred; Ollama in reviewer Compose |
| Database | Resettable SQLite seed (WP02+) | Persistent mounted SQLite (WP02+) |
| Identity | Random demo session (`specs/principals.md`) | Single `local_user` |
| Uploads | Disabled | Enabled with rights declaration (not this WP; not paid-tier arbitrary ingest) |
| Mutable state | Session-scoped; wiped on restart | Persistent |
| Audio | One lawful preview; generate = Coming soon | Same this week (ADR-009) |
| BYOK | Not offered | Config (`LLM_BASE_URL`) |
| Banner | Visible “Public showcase — changes may reset…” | None |

Network profiles (`selfhosted` only): `local` binds Streamlit to `127.0.0.1`;
`lan` binds Streamlit only, with PIN/token — **not implemented this week**.
FastAPI, SQLite and the model port stay off the LAN.

Rejected this week: Vercel; early Streamlit Cloud canary (owner: Cloud is
created on submission day); Apple Foundation Models (reserved provider,
Coming soon).

## Error/degradation behavior

- Unknown `APP_MODE` → process refuses to start (fail closed).
- `demo` + upload / path-ingest / remote URL → **403** with an explicit
  “disabled in public showcase” detail. Never silently no-op.
- `apple_future` `LLM_MODE` → provider `health().reachable is False`;
  ask/search still run retrieval and return `degraded: true` if generation
  was requested.
- Compose still runs Postgres until WP02. Edition config must not drop that
  service from compose in this WP.

## Named red tests

- `test_unknown_app_mode_refuses_to_start`.
- `test_demo_rejects_upload_and_remote_url`.
- `test_health_exposes_app_mode_never_secrets`.
- `test_compose_default_timeout_is_not_ninety` — reviewer Compose /
  `.env.example` `LLM_TIMEOUT_SECONDS` is ≥ 300.

## Verify

```
uv run pytest -k 'app_mode or entitlement' -v
grep -n '^APP_MODE\|^LLM_TIMEOUT' .env.example
```
