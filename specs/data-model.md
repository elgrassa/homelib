# spec: data-model — WP00 schema draft (ideas only)

**Implemented by:** WP02 (migrations). **WP01:** still draft — no Alembic, no
FTS5, no dropping Postgres compose. Field-level HTTP: `specs/api.md`. Identity:
`specs/principals.md`. Playlist: `specs/coffee-table.md`. Rights: `specs/rights.md`.

**Status:** draft. Grounded in the HTML prototype's actual JS, `specs/product.md` §§4–8, and `docs/mockups/`. Contradictions are listed, not silently resolved.

## 1. Sources examined

| Source | What was used |
|---|---|
| `docs/mockups/homelib-magic-library-standalone.html` | Full file. sha256 `693888a9d320b1479d7adf6eb103ce56db9eb805894cbfbc66f5a3d6dc678869` (14,975 bytes). Discovery-screen-only: rotating doors + topic search. No playlist, reader, mentor thread, or progress objects. |
| Mockups | `00-home-topology.png` … `07-mentor-session-voice.jpg` (see `docs/mockups/README.md`) |
| `specs/product.md` | §4.1–4.2 editions/demo sessions; §5.1–5.9 IA / Coffee Table / scene search / reader; §6 rights; §7.4–7.5 SQLite + embeddings; §8 endpoints |
| v1 | `specs/indexing.md` tables (`books`, `blocks`, `chunks`, `chunk_embeddings`, `catalog`, `query_log`) |
| ADR-010 | Paid-tier tables must not be created in the public snapshot |

## 2. Entities mined from the HTML

Quote JS identifiers as they appear. Do not invent a parallel vocabulary first.

| JS identifier | Kind | Role in the prototype |
|---|---|---|
| `root` | `document.getElementById('homelib-magic-library')` | Shadow-root-like wrapper; not persisted |
| `stage` | `#hl-stage` | 3D door carousel DOM |
| `compass` | `#hl-compass` | Text `Facing: ${wings[active].name}` |
| `title` | `#hl-result-title` | Result heading |
| `copy` | `#hl-result-copy` | Result blurb from `wings[active].copy` |
| `status` | `#hl-status` | Ephemeral message after search / Ask / Build path |
| `topic` | `#hl-topic` | Search input; default value `"AI agent evaluation"` |
| `wings` | `const` array of `{ name, kind, copy }` | Hard-coded six doors |
| `wings[].name` | string | `'AI Engineering'`, `'Software Craft'`, `'Systems & Scale'`, `'Business & Strategy'`, `'Ideas in Common'`, `'Surprise Me'` |
| `wings[].kind` | string | `'topic wing'` \| `'crossroads'` \| `'hidden door'` |
| `wings[].copy` | string | Blurb shown in the result panel |
| `active` | `let` number | Selected wing index; wrapped with modulo |
| `angle` | `360 / wings.length` | Layout constant |
| `q` | `topic.value.toLowerCase()` | Search query, submit handler only |
| `destination` | number | Regex-routed wing index (`0`–`4`; default `4` = Ideas in Common) |
| `message` | `selectWing(index, message = '')` | Written to `status` |
| `.hl-door` buttons | created in `wings.forEach` | `aria-pressed`, `aria-label` `Enter ${wing.name}` |
| Nav buttons | static HTML, no JS listeners | `Explore` (aria-current), `Ask my shelf`, `Reading path`, `My library` |
| `#hl-ask` / `#hl-roadmap` | click → `status.textContent` | No objects created |

**Not in the HTML at all:** books, blocks, chunks, playlist/Coffee Table, reader position, conversation messages, citations as records, progress, principals, demo sessions, rights, Observatory.

## 3. Proposed SQLite tables

This week vs later. Identity and corpus are load-bearing for scored RAG. UX tables exist so WP08 has somewhere to write. Paid-tier tables: §8.

### This week — identity

- `principal` — `id` PK, `kind` (`demo_session` \| `local_user`), `created_at`. Null id is not a principal.
- `demo_session` — `id` (random), `principal_id` FK, `created_at`, `expires_at` (TTL), `reset_generation`. Every mutable row FKs a non-null `principal_id`. Null-owner writes refused (`test_private_write_requires_principal`).

### This week — corpus (port v1 shape; SQLite)

- `books` — v1 columns (`book_id`, title, authors, language, source_url, license_note) plus `rights_status` FK/check.
- `blocks` — v1 (`block_id`, book_id, ordinal, section_path, text, char_start/end, format, page, spine_index, anchor). Citations resolve to `block_id`.
- `chunks` — v1 ids **must remain identical** (ground truth). `char_start`/`char_end` map to original text.
- `chunks_fts` — FTS5 virtual table over chunk text (WP03/WP04).
- Embeddings: either `chunk_embeddings(chunk_id, embedding BLOB, model, dim, index_revision)` **or** a sidecar NumPy matrix keyed by `index_revision` (product §7.5 — prefer the cache; BLOB is the durable copy). Do not decode all BLOBs per query.

### This week — library UX

- `areas` — user-extensible; not hard-coded “AI Engineering”.
- `wings` — `id`, `area_id`, `name`, `kind` (topic/crossroads/hidden — HTML kinds are a hint, not a closed enum), `copy`, `principal_id` (seed rows: a well-known system principal or null-owner **read-only seed**).
- `wing_membership` — `wing_id`, `book_id` or `resource_id`, ordinal.

CONFUSION: product §7.4 lists `resources` / `documents` as well as books. v1 is `books`. Draft: keep `books` as the indexed corpus table this week; `resources` can alias or wait for WP02 if Discover metadata-only rows need a wider type.

### This week — Coffee Table (product §5.6)

- `playlist` — one “current” table per principal (`id`, `principal_id`, `last_opened_item_id`, `updated_at`).
- `playlist_item` — `playlist_id`, `resource_id`/`book_id`, `ordinal`, `origin` (`mentor_proposal` \| `manual_shelf` \| `manual_discover` \| `roadmap`), `status` (`proposed`, `queued`, `reading`, `listening`, `paused`, `completed`, `skipped`, `removed`), `accepted_at`, `manual` boolean. Rules: acceptance-required; manual survives regen; no silent reinsert of completed/removed; remove keeps the resource.

### This week — progress

- `read_progress` — `principal_id`, `book_id`, `block_id`/`char_offset`, `updated_at`. Independent of listen.
- `listen_progress` — **columns reserved**, unused (ADR-009). No production audio rows.

### This week — Mentor

- `conversation` — `id`, `principal_id`, `wing_id` nullable, `created_at`.
- `message` — `conversation_id`, role, text, `created_at`.
- `citation` — `message_id`, `block_id` **required**, must resolve before return (v1 lesson).
- `feedback` — thumbs on a `request_id` (can live on `query_log` as v1, plus a row here if the UI needs conversation-scoped votes).

### This week — catalog / rights / Observatory

- `catalog` — keep v1 OL shape (`ol_key`, title, authors, subjects, first_publish_year, description, provenance_note). Ambiguous editions never merge.
- `rights_status` — per resource: source, license, `can_index_text`, `can_generate_audio`, `can_bundle_demo`. Unknown fail-closed (ADR-008).
- `query_log` — port v1: `request_id`, ts, latency_ms, arm, k, rerank, rewrite, model, tokens_prompt, tokens_completion, query_sha256_prefix, `degraded`, feedback, plus `demo_session_id` / `principal_id`.

### Later this week (Coming-soon flags only, no paid implementation)

- `audio_assets` — at most one bundled public-domain preview row.
- Feature flags: `voice_input`, `apple_fm`, `rotunda_component` default off.

## 4. HTML → table map

| HTML state field | Proposed persistence |
|---|---|
| `topic` / `#hl-topic` value | UI-only while typing; last submitted query may log to `query_log` / `searches` |
| `q` | not persisted (derived) |
| `destination` | not persisted (derived routing) |
| `wings[]` | seed rows in `wings` (user-extensible later — HTML is a fixture, not the taxonomy) |
| `wings[].name` | `wings.name` |
| `wings[].kind` | `wings.kind` |
| `wings[].copy` | `wings.copy` |
| `active` | UI session / URL state (`?wing=`); home edition may persist last wing on `principal` |
| `angle` | UI-only / not persisted |
| `compass` text | UI-only / derived |
| `title`, `copy`, `status` | UI-only / not persisted |
| `message` | UI-only / not persisted |
| `#hl-ask` click | opens Mentor (`conversation`) — HTML only sets `status` |
| `#hl-roadmap` click | proposes path (`playlist` proposed items) — HTML only sets `status` |
| Nav: Explore / Ask my shelf / Reading path / My library | routes; cut-order note: HTML prototype is first to cut — do not treat these labels as the product IA (product §5.1 uses Crossroads / Shelf / Coffee Table / …) |
| Door DOM / `aria-pressed` | UI-only |

## 5. Mockup-only entities (not in the HTML)

| Mockup | Entity | This week vs deferred |
|---|---|---|
| `07-mentor-session-voice.jpg` | live transcript, voice button, “Evidence Used” counts | **Deferred** (ADR-009). Schema may reserve `listen_progress` / a `transcript` JSON column; do not ship TTS/STT |
| `01` / sidebar | Discover vs My Shelf toggle | This week as a **filter** on catalog vs `books` owned by principal — not a table |
| `02` | chapter TOC, provenance sidebar, reading % | TOC from `blocks.section_path`; provenance from `rights_status` + book metadata; `%` from `read_progress` |
| `03` | five-stage path with projects | Coffee Table / roadmap artifacts — this week as `playlist_item` + optional `artifact` text; not a separate “stage” table unless WP07 needs it |
| `04`/`05`/`06` | rotunda doors, sphere | Static door grid this week; custom rotating-room **cut-order after HTML prototype**; paid sphere assets post-publish (ADR-010) |
| `00` | Apple Foundation Model node | Coming soon / reserved provider (ADR-006) |

## 6. Contradictions (CONFUSION — do not silently pick)

1. **HTML vs product IA.** HTML nav is Explore / Ask my shelf / Reading path / My library. Product §5.1 is Library Crossroads, My Shelf, Discover, Coffee Table, Mentor Journal, Roadmaps, History, Observatory. Mockups mix both. **WP08 follows product.md**; HTML is cut-first prototype.
2. **Hard-coded wings vs user-extensible.** HTML freezes six names including `Surprise Me`. Product: users create Areas/Wings; AI never silently creates an active Wing. Seed may look like the HTML; schema must not.
3. **HTML search is regex keyword routing**, not RAG. Product/v1 is hybrid retrieval + cited Mentor. Do not persist `destination` regex as a retrieval arm.
4. **Naming: `books` (v1) vs `resources` (product §7.4).** Need one canonical id for citations this week (`book_id` / `block_id` as v1) so ground truth survives.
5. **Product §7.4** lists `playlists`/`playlist_items`/`progress_events`/`query_events`; this draft uses `playlist`/`playlist_item`/`read_progress`/`query_log` to match the WP00 brief. WP02 picks one and snapshots it.
6. **Embeddings:** product §7.5 cached matrix vs a `chunk_embeddings` table. Both: table (or sidecar file) durable; matrix is the query cache keyed by `index_revision`.
7. **v1 Postgres vs v2 SQLite** (ADR-004). Compose Postgres stays on `main` / v1 fallback. WP02 adds SQLite **additively**; this draft is the target store, not a license to drop the tagged compose service.
8. **Apple FM in topology mockup vs LM Studio this week** (ADR-006).
9. **Voice mentor mockup vs ADR-009.**
10. **Two-repo split in product §4.6 diagram / `docs/plan-v2.md` §9 vs ADR-010 evening pivot.** Schema follows ADR-010: no second remote; paid tables not created this week.
11. **Calendar weekdays** in `docs/plan-v2.md` vs machine `cal 9 2026` — evidence only; not a schema issue.
12. **Grafana vs Observatory.** `specs/monitoring.md` (v1) vs ADR-005 / `specs/observatory.md`. v2 scored surface is Observatory; Grafana may remain in compose until WP10.
13. **`POST /v1/roadmap` (live v1) vs `POST /v1/mentor/intake` + `POST /v1/paths` (product §8).** Keep roadmap until WP06; do not dual-write OpenAPI.
14. **`GET /v1/books` vs `GET /v1/resources`.** Citation identity stays `book_id` this week; resources is the Discover/shelf list.
15. **`LLM_TIMEOUT_SECONDS=90` (product §7.2) vs Compose 300 (plan §0.2).** Editions spec: Compose stays 300; 90 is demo-cloud suggestion only.
16. **WP01 “commit OpenAPI snapshot” vs no new routes this WP.** Snapshot stays v1-aligned; first API PR regenerates it.

## 7. WP02 red-test hooks

| Test | Schema attachment |
|---|---|
| `test_private_write_requires_principal` | INSERT into `playlist` / `playlist_item` / `read_progress` / `conversation` / `feedback` with `principal_id` NULL → refused (CHECK or application + FK). Seed catalog/`books` remain read-only shared rows. |
| `test_demo_sessions_cannot_read_each_other` | Two `demo_session` rows; session A cannot SELECT session B's `playlist_item` / `conversation` / `read_progress`. |
| `test_restart_persists` | Home/`selfhosted`: playlist ordinal, last-opened item, `read_progress` survive process restart (same SQLite file). Demo: see next test. |
| `test_demo_reset_restores_seed` | `APP_MODE=demo`: restart or reset wipes mutable principal rows; seed `books`/`chunks`/`wings` counts + logical checksums match the canonical seed. |

Also from the plan: `test_fresh_migration_then_upgrade`, `test_fk_enforced`, `test_seed_rerun_zero_new_rows`.

## 8. Out of scope this PR / paid-tier must not be created this week

**This PR:** no Alembic/SQLite implementation, no FTS5 code, no dropping Postgres compose.

**Public schema this week — do not create** (Coming-soon flags only if a column is required to compile). Paid tier lands in the **same Forgejo repo after** public GitHub + Forgejo private (ADR-010), not a second remote:

- household profiles / LAN auth tables
- commercial licence verification / entitlement tables
- Silver Memory artifacts
- production TTS/STT / audio generation jobs
- LM Studio discovery catalog
- backup/restore metadata
- Obsidian sync state
- Apple companion device registry
- installer/update-channel tables
- proprietary sphere/rotunda asset stores
