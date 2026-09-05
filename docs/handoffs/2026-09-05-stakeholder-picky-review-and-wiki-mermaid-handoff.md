# Stakeholder picky review + wiki/mermaid handoff — 2026-09-05

**Product tip at start:** `v2` @ `86ba349`. **Stack produced:** PR-A #25 (`ae83d51`) → PR-B #26 (`c2675e3`) → PR-D `feat/crossroads-rotunda` (`ee0f318`) → PR-C `docs/stakeholder-review-wiki-mermaid-sync`, all into `v2`, stacked oldest-first, rebase-merge only. **Nothing merged by agents.** Deadline Tue 2026-09-08 01:00; submission Mon Sep 7; GO/NO-GO Sun Sep 6 18:00.

## 0. Live snapshot (read-only, start of session)

| Check | Result |
|---|---|
| Host stack (`-p homelib`, ports 8010/8501/3011) | api `/health` 200 `ok` 18/9168 · `/v1/observatory` 6 charts (queries_over_time 2 points) · UI 200 · Grafana 200 |
| Doors live | six (Ask, Mentor, Coffee Table, Shelf, Observatory, Projection) — Roadmap renderer existed, unreachable |
| SQLite-only ask (Cloud shape) | **degraded on every ask** before PR-A (`_book_metadata` Postgres-only) |
| Demo Coffee Table | **empty after every rerun** before PR-A (UI never sent `X-Demo-Session`) |
| Forgejo issue | [#24 Out of scope for the 2026-09-05 readiness stack](http://minips.local:3000/elgrassa/homelib/issues/24) |

## 1. Scoreboard (rubric, cold re-score on the stack)

| # | Criterion | Before | After | Evidence |
|---|---|---|---|---|
| 1 | Problem description | 2 | 2 | README |
| 2 | Retrieval flow (KB + LLM) | 2 (Postgres) / **0 on SQLite-only** | 2 | `test_answer_end_to_end_not_degraded_on_sqlite_only_host`; smoke |
| 3 | Retrieval eval | 2 | 2 | ADR-001 §v2 0.638/0.572 |
| 4 | LLM eval | 2 | 2 | ADR-003 null result |
| 5 | Interface | 2 | 2 | 18 API paths; seven doors + rotunda |
| 6 | Ingestion (dlt) | 2 | 2 | `just seed` + `just seed-sqlite` (CLI, exit 1 on empty) |
| 7 | Monitoring | 2 claimed / **vacuous drill check** | 2 | Observatory asserted by the drill; Grafana honesty |
| 8 | Containerization | 2 | 2 | `--build` on seeds; api pinned selfhosted |
| 9 | Reproducibility | 2 (`d6f9946`, 2026-09-04) | **2 on `d6f9946`; re-run on `ae83d51` FAILED under load** | `just drill` @ `ae83d51`: clone/seed/health 18/9168 passed, ask step 3/5 timeouts (300 s) at host load 340–410 — infra, quiet-box re-run pending before GO/NO-GO |
| 10 | Best practices | 3 | 3 | unchanged |
| 11 | Cloud (bonus) | 0 | 0 — **not deployed**; PR-B2 files drafted, held until the drill re-run passes | owner creates the app Mon (Python 3.13, Groq secrets) |
| 12 | Extras (bonus) | partial | partial | Mentor agent, eval gate |

## 2. Findings

### Fixed in this stack (each with named tests — see PR bodies for the regression matrix)

| # | Finding | PR | Tests |
|---|---|---|---|
| H1 | SQLite-only hosts degraded on every ask | #25 | `test_answer_book_metadata_dispatches_to_sqlite`, `test_answer_end_to_end_not_degraded_on_sqlite_only_host`, `test_agent_search_catalog_uses_sqlite_when_path_set`, `test_run_agent_is_not_on_the_demo_request_path` |
| H3 | Demo principal never persisted | #25 | `test_demo_session_header_sent_on_playlist_and_progress_calls`, `test_request_retries_once_with_fresh_session_on_401_in_demo`, `test_request_does_not_remint_on_401_in_selfhosted`, `test_ensure_demo_session_mints_once_and_reuses_state`, `test_demo_mode_same_header_shares_principal_and_missing_header_does_not` |
| H2 | Cold clone answered nothing, nothing noticed | #25 | `test_cli_main_seeds_db_and_reports_counts`, `test_cli_main_exits_nonzero_on_empty_seed`, `test_health_is_degraded_when_store_has_zero_books`, `test_drill_asserts_seed_counts_via_health`, `test_seed_one_shots_build_the_profile_image_before_running` |
| M1 | Roadmap door unreachable | #26 | `test_every_door_has_a_renderer_and_vice_versa`, AppTest `test_every_door_renders_without_exception` |
| M2 | Grafana "dual monitoring" + vacuous drill check | #26 | `test_drill_verifies_monitoring_via_observatory_not_grafana_panel_count` |
| Docs | wiki "WP07–11 not started", CHECKLIST v1 rows, `specs/ui.md` v1 tabs, no door/monitoring/edition diagrams | PR-C | `test_specs_ui_door_list_matches_crossroads_doors` |
| UX | Rotunda (first-class Crossroads) | PR-D | `test_rotunda_door_labels_match_crossroads_doors`, `test_rotunda_html_emits_door_param_link_for_every_door`, `test_rotunda_is_an_inline_fragment_not_an_iframe_document`, `test_rotunda_script_text_contains_no_markup_like_characters`, `test_rotunda_html_neutralises_script_close`, AppTest `test_door_query_param_opens_that_door_and_is_consumed`, `test_unknown_door_query_param_does_not_crash_the_crossroads` |

### Found while verifying (not in the review brief)

- **Streamlit iframes cannot navigate the page.** The plan's rotunda Enter (`<a target="_parent">` from `components.v1.html`) is a `SecurityError`: Streamlit's iframe sandbox has no `allow-top-navigation` (and `components.v1.html` is deprecated in 1.62 in favour of `st.iframe`, same sandbox). PR-D renders the room inline with `st.html(unsafe_allow_javascript=True)` — safe because the HTML is built only from `CROSSROADS_DOORS`/`DOOR_COPY` — and Enter is a same-document `?door=` link.
- **DOMPurify eats scripts that look like markup.** With `SAFE_FOR_XML`, one `<name` in a JS comment removed the whole `<script>` and the room silently lost its doors. Pinned: no `<` in the script text, injected JSON escapes `<` as `\u003c`.
- **Drill re-run red under load.** See scoreboard row 9; the failing attempts are timeouts and a CPU model declining to cite, not a request-path change. The PASS on `d6f9946` stands; the quiet-box re-run is owner/next-agent P0.

- **Stale seed image.** The first drill on PR-A failed: `up --build` never builds the `seed`-profile ingest service, so `run --rm ingest` reused a five-day-old image. Fixed on PR-A (`--build` on every seed one-shot) with a hygiene pin. `just seed` on any host with an old `homelib-ingest` image had the same hole.
- **Forgejo quick lane timeouts.** Runs 13120 (`9e280cd`), 13125 (`ae83d51`) and 13126 (`c2675e3`) all died at the quick lane's 20-min limit — ruff, format and gitleaks green, then `context deadline exceeded` during mypy/pytest — with host load 340–410 (local gates, the drill's builds and the heavy lane at once). The heavy lane on `ae83d51` passed in 44 of its 45 minutes. Infra, not code (every local `just ci` on the same commits is green); the quick lane's limit is an owner call, not changed here.
- **Streamlit Cloud dependency precedence:** Cloud installs from `uv.lock` when present, so a root `requirements.txt` would have been dead weight. PR-B2 relies on `uv.lock` (CPU torch index already pinned) instead of the planned `requirements.txt`; Python 3.13 is an Advanced-settings choice (default 3.12).

### Recorded, not fixed (owner decisions)

| # | Decision | Where |
|---|---|---|
| M3 | Licence: tree Apache-2.0 vs ADR-007 PolyForm-NC | decision-log "Licence — owner decision"; no LICENSE change in any PR |
| M4 | Cloud deploy: owner creates the app, picks Python 3.13, pastes Groq `LLM_*` secrets | `docs/submission.md`; PR-B2 |
| — | `just publish`, public remote, `/design-login`, Grafana removal, `v2`→`main`, merges | issue #24 |

### Stack status at hand-off

| PR | Branch | Base | Gate | Forgejo |
|---|---|---|---|---|
| A #25 | `fix/h1-h3-h2-sqlite-demo-path` @ `ae83d51` | `v2` | `just ci` 650 passed / 90.34% | run 13125: **heavy lane PASSED** (44 min); quick lane hit its 20-min limit after gitleaks (infra, load 340–410) |
| B #26 | `fix/roadmap-door-monitoring-honesty` @ `c2675e3` | A | `just ci` 661 passed / 90.39% | run 13126: quick lane hit the 20-min limit after gitleaks (infra); heavy lane running at hand-off |
| D #27 | `feat/crossroads-rotunda` @ `ee0f318` | B | `just ci` 675 passed / 90.45% | run 13129 running at hand-off |
| C | `docs/stakeholder-review-wiki-mermaid-sync` | D | docs + 3 hygiene tests | opened after `just ci` |
| B2 | `feat/streamlit-cloud-groq-files` | — | **not opened** — drafted, held until the drill re-run passes (plan: best-effort after drill PASS) | — |

## 3. Talk track (5–8 min)

1. **The library** (30 s): a private academic shelf you can ask, with citations that open the page. Doors, not tabs.
2. **Ask** (2 min): question → cited answer → open the block → 👍. Point at `arm_used=hybrid_rerank` and the eval table (why rewrite is off).
3. **Mentor → Roadmap → Coffee Table** (2 min): agent proposes, you accept, the stack persists per principal — show it survive a rerun in demo.
4. **Observatory** (1 min): the question you just asked is already a point on `queries_over_time`. This is what the drill asserts.
5. **Reproducibility** (1 min): `just up && just seed && just seed-sqlite`; `/health` goes `degraded` → `ok 18/9168`; `just drill` clones cold on offset ports and rebuilds every image.
6. **What was wrong on Friday and how we know it is fixed** (1 min): three HIGHs, each with a test that was red on the old tree.

## 4. Re-verify (next agent or owner)

```bash
just ci
HOMELIB_SQLITE_PATH=data/homelib.sqlite LLM_BASE_URL=http://localhost:11434/v1 bash scripts/sqlite_only_smoke.sh
just drill
uv run pytest apps/ui/tests -q
curl -fsS localhost:8010/health; curl -fsS localhost:8010/v1/observatory | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d["charts"]))'
```

## 5. Pasteable prompt for the next model

> Repo `elgrassa/homelib` on Forgejo (never GitHub). Read `docs/handoffs/2026-09-05-stakeholder-picky-review-and-wiki-mermaid-handoff.md`, then `CHECKLIST.md`, `docs/evidence.md` (last 8 rows), `docs/wiki/README.md`. The stack PR-A #25 → PR-B #26 → PR-C → PR-D into `v2` is open; agents do not merge. Verify with `just ci` and `just drill` before any claim. Owner-only: `just publish`, Streamlit Cloud app (Python 3.13, Groq secrets), licence, peers. Do not add a provider chain, server TTS, WebGL, or touch LICENSE.
