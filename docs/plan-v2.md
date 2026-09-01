# HomeLib v2.1 — final merged execution plan (capstone rebuild + product)

**Status:** Pavlo's consolidated "improved product and build plan v2" (message of 2026-09-01) is ADOPTED as the product/architecture source of truth. WP00 saves that full text as `specs/product.md` (the executor session has it in-context; the older `~/Downloads/homelib-improved-product-build-plan*.md` files are superseded). This file is the execution layer: review corrections, owner actions, engineering appendix, calendar, and the safety track. Where the two conflict on product/UX, `specs/product.md` wins; on engineering discipline, dates, and verification, this file wins.

**Handoff requirement (owner instruction):** both documents are committed into the repo via PR #3 — `specs/product.md` (product SOT) + `docs/plan-v2.md` (this file, verbatim) — so any fresh session can execute from the repo alone: read `docs/plan-v2.md` first, then `specs/product.md`, then `docs/evidence.md` for current state. No plan content may live only in a chat transcript or a local `plans/` directory.

## ⏰ DEADLINE — corrected weekdays (the source doc's labels are shifted +1)

**2026-09-08 01:00 is the night of SUNDAY Sep 7 → MONDAY Sep 8.** Sep 1 = Monday (today), Sep 6 = Saturday, Sep 7 = **Sunday, the submission day**. There is no Monday build day. Attempt 3 — the LAST. **Owner task: confirm the cohort platform's timezone for "01:00" and record it in `docs/evidence.md`** — until confirmed, treat the deadline as 01:00 in the platform's earliest plausible TZ and target submission by Sunday 20:00 CET.

## 0. Review verdict on the consolidated plan (adopted, with these corrections)

1. **Calendar weekdays** — fixed above and in §8. Dates and content-per-date are kept exactly; only labels change.
2. **`LLM_TIMEOUT_SECONDS=90` (product doc §7.2) is too tight for the reviewer Compose profile.** v1 measured CPU-only in-VM Ollama at ~49 tok/s prefill / ~7.4 tok/s generation ⇒ a real cited answer costs ~70 s+ *uncontended*. Compose default stays **300** (v1 commit 467b6bc); 90 is fine as the *demo* (cloud-provider) default. Keep `max_tokens` bounded per call (answers 400, roadmap/paths 1600 — the v1 truncation lesson).
3. **Public-repo history strategy** (product doc §4.6 left it open): develop on Forgejo `homelib` branch `v2` as always; the public GitHub repo receives the v1-style `just publish` full-history push **after a pre-publish scan** (secrets via gitleaks + a manual grep for homelab hostnames/paths in docs/evidence.md — redact if needed). Nothing premium exists in history this week, so curated-fresh-history is deferred to the commercial split. The submitted hash is the public repo's HEAD; the cold-clone drill runs against the public clone at that hash.
4. **Fallback eligibility** — recorded reasoning, not an open question: the course's no-reuse rule bans previously *submitted* capstones; v1 was built entirely within this attempt and never submitted. Eligible. Record this in evidence at WP00.
5. **Standalone HTML prototype** is now FIRST in the cut order (product doc §13) — it therefore does not get a WP slot; build it only if everything else is green early.
6. **Seed determinism** — adopt the correction: SQLite files are not byte-reproducible; verify canonical row counts + logical checksums. The v1 JSONL snapshot's byte-stability guarantees still hold for the *inputs*.
7. Everything else — editions matrix, demo-session isolation rules, principals, provider contract (`supports_tools`/`supports_structured_output` additions are good), commercial/licence analysis (PolyForm-NC provisional), Obsidian design, acceptance journeys A–E, GO/NO-GO definition — adopted as written.

## 1. Owner actions (Pavlo) — GitHub + Streamlit at the VERY END (owner decision 2026-09-01)

Pavlo creates the public GitHub repo and the Streamlit Community Cloud app only **after homelib is fully tested locally** — no early canary. Consequence, accepted and mitigated: the first Community Cloud deploy happens on submission day, so its risks (dependency install, memory ceiling, secrets, cold start) are rehearsed locally instead — the build runs the Streamlit app in `APP_MODE=demo` locally throughout (in-process client, resettable seed, measured RSS with the chosen embedding runtime), and WP04's ONNX-vs-torch memory decision is made against Community Cloud's documented limits rather than a live canary. Keep the demo path dependency-light so the late deploy is boring.

| When | Action |
|---|---|
| Any day this week | Confirm deadline timezone on the cohort platform (see banner). |
| Before the public push | Sign off the provisional licence: **PolyForm Noncommercial** for the public capstone repo (product doc §4.6). |
| Sun Sep 7 (end) | Create public GitHub repo → `just publish` → create Streamlit Cloud app from it, set secrets (app-owner cloud LLM key **with a hard budget cap** + product doc §4.2 limits — provider/key is your explicit choice) → verify URL logged-out → submit the form → schedule 3 peer reviews before closing the laptop. |

## 2. Safety track (unchanged, binding)

- v1 is CI-green on `main` after PR #3 merges (run 12564 green — merge is WP00 step 1). **Tag `v1-fallback` at that merge commit; record the hash.** Never rewrite `main`.
- v1 drill re-run opportunistically in a quiet window (~35 min) to bulletproof the fallback; evidence row either way.
- All v2 work on integration branch `v2`; feature PRs target `v2`; `v2`→`main` only when the v2 drill is green.
- **Scope-cut checkpoint Fri Sep 5 18:00; GO/NO-GO Sat Sep 6 18:00** per product doc §12.4 (public demo loads logged-out, cited answer resolves, both evals committed, ingest repeatable, feedback+5 charts, Compose healthy, drill plausible for Sunday, no rights/secret/isolation blocker). NO-GO ⇒ submit v1 Sunday; v2 continues post-capstone.

## 3. Executor operating rules (binding, restored from v1)

1. Orchestrator Fable/Opus; mechanical WPs to **Sonnet 5 subagents, SYNCHRONOUS** (`run_in_background: false`); parallelize only disjoint-file WPs.
2. Every subagent prompt: WP text verbatim + spec path + exact verify commands + *"Your final message must contain the verbatim output of every verify command; do not summarize."* **Orchestrator re-runs every verify itself.**
3. SDD per WP: spec → named red tests failing → implement → green → verify → evidence row in `docs/evidence.md`.
4. Git: rebase on `forgejo/v2` at WP start; `feat/<slug>` PRs into `v2`; stage specific files; linear history; no `--no-verify`; heredoc commits `Co-Authored-By: Claude <noreply@anthropic.com>`. CI in `.forgejo/workflows/` only, every job starts `uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd`; triggers extended to `v2`; keep v1's per-process test-DB names + lane split + 25-min quick-runner cap lessons.
5. WP fails twice → stop, record blocker, move on.
6. Machine discipline before drills/evals/timing: `uptime` < ~10, Forgejo queue empty (`select count(*) from action_run where status in (5,6)`), `curl -s localhost:11434/api/ps`; never fight prep-os CI or evict a peer's model unannounced.
7. Gates green before any push; secrets never staged; gitleaks stays wired.

## 4. What v2 ports from verified v1 (do not rewrite the database-agnostic 60%)

| v1 asset | v2 fate |
|---|---|
| `packages/homelib-core` (models, EPUB/PDF/TXT/MD parsers, chunker, offset-invariant + round-trip tests) | as-is; OCR/DjVu post-capstone |
| `data/manifest.yaml` + `corpus_snapshot.jsonl.gz` (18 books) + `catalog.jsonl` (3,061 OL) | seed inputs; catalog doubles as the OL fixture |
| `hybrid.py` RRF (Cormack cit.), `rerank.py` None-on-failure, `rewrite.py` fail-open, `answer.py` (passage-number citations, whitespace-collapse quote check, env timeout, per-call max_tokens) | port; only the two arms rebuilt on FTS5 + cached-NumPy-matrix (§7.5 of product doc: contiguous matrix keyed by index revision, never per-query BLOB decode) |
| `evals/` metrics + judge/bias control + hedging guard + prompt-hash test + regression gate (`MetricSpec`, `compare_to_baseline`, append-only history, `_note`d baselines) + **ground_truth.jsonl (235 Q→chunk)** | port whole; chunk ids must remain v1-identical (red test) so ground truth stays valid |
| API discipline: degraded-200 contract, `_RawCitation` no-title field (author-hallucination closed structurally), OpenAPI snapshot + drift test, health booleans | port into product-doc §8 endpoints |
| UI `api_client` per-call timeouts, UI-boundary AST test | port into the `HomelibClient` seam + parametrized InProcess/Http conformance suite |
| dlt ELT shape (staging→canonical, idempotent) | `dlt[sqlalchemy]` → SQLite |
| `cold_clone_drill.sh` (multi-question, block_id-resolving, offset ports), `just publish` (commit-keyed, enum-correct), `.gitleaks.toml`, `.env.example` style | adapt (drill adds: restart persistence, playlist survival, scene-anchor open) |
| ADR-001/002/003 + Kaggle/GoogleBooks/Goodreads ban (grep-enforced) + course-FAQ ban | carry forward; re-record where results change |
| Postgres DDL, pgvector, Grafana | drop (ADR at WP00) |

Model policy: provenance/metadata `extra="allow"`; public API requests `extra="forbid"`; provider payloads under `raw_json`; every LLM output typed, fail-closed, one bounded repair; every citation resolves before return.

## 5. Work packages = product doc §12.3 (WP00–WP11), with these verification teeth added

Each WP keeps SDD order; red tests below are mandatory minimums; orchestrator re-runs all verifies.

- **WP00** (tonight+Tue am) — **PR #3 is already MERGED** (Pavlo, 2026-09-01 evening): `main` = verified v1 incl. the citation + timeout fixes. Steps: tag `v1-fallback` at current `main`, record hash + fallback-eligibility note; then a fresh branch `docs/v2-plan` → new PR into `main` carrying: `specs/product.md` (the consolidated v2 product plan from Pavlo's message), this execution plan as `docs/plan-v2.md` (verbatim — the handoff another session picks up), mockups → `docs/mockups/`, the ADRs (SQLite-replaces-Postgres, Observatory-replaces-Grafana, editions/hosting incl. LM-Studio-preferred + Vercel rejection + late-deploy decision, licence-provisional, rights gate, audio deferred), updated CHECKLIST for v2, and the initial scaffolding (CI triggers for `v2`, demo-mode config skeleton). Push → CI green → merge. Branch `v2` from that merge for everything after. **Local demo-mode smoke replaces the cloud canary:** seeded FTS5 search + provider health, RSS measured. Verify: `git tag | grep v1-fallback`; Forgejo CI green on the docs PR; local demo smoke recorded in evidence.
- **WP01** (Tue): specs per product doc list; field-level request/response schemas for every §8 endpoint; `specs/openapi.snapshot.json` + drift test from the first API PR. Verify: `ls specs/*.md | wc -l` ≥ 16; orchestrator contradiction pass (v1 caught a real one).
- **WP02** (Tue): red tests `test_fresh_migration_then_upgrade`, `test_fk_enforced`, `test_seed_rerun_zero_new_rows`, `test_restart_persists`, `test_demo_reset_restores_seed`, `test_private_write_requires_principal` (null-owner write refused), `test_demo_sessions_cannot_read_each_other`. Verify: pytest green; seed logical checksums stable across two builds.
- **WP03** (Wed): red tests `test_chunk_ids_match_v1_snapshot` (guards ground truth), `test_second_run_no_duplicates`, `test_every_citation_resolves`, `test_metadata_only_never_indexed`, `test_unknown_rights_fail_closed`. Verify: pipeline twice → identical counts (expect 18/729/9,168).
- **WP04** (Wed): red tests `test_rrf_hand_computed` (port), `test_vector_down_degrades_flagged`, `test_rerank_failure_preserves_order`, `test_exact_offsets_map_to_original_text`, `test_chapter_scope_never_leaks`, `test_book_scope_survives_rewrite`, `test_open_anchor_always_resolves`, `test_search_with_llm_unreachable`. Verify: `just eval-retrieval` → ≥4 arms on the 235 reused questions, committed table + ADR; scene-search set measured separately (exact-offset accuracy, scope-leak count, p50/p95); ONNX-vs-torch memory decision measured **on the deployed canary** and ADR'd.
- **WP05** (Thu): fixtures-first, no network in CI; live OL smoke recorded in evidence. Red tests: dedup-keeps-attributions, timeout-degrades-not-fails, unique-count-not-provider-sum, ambiguous-editions-never-merge.
- **WP06** (Thu): red tests: scripted-fake dispatch (port), intake-never-creates-active-state, path/roadmap fail-closed (port), citations-resolve (port), high-stakes-note, abstention-on-no-evidence. Verify: live cited answer + proposed stack on Compose.
- **WP07** (Fri): red tests = product doc §5.6 rules verbatim (acceptance-required, manual-survives-regeneration, no-silent-reinsert, independent read/listen progress, remove-keeps-resource, restart-persistence).
- **WP08** (Fri): thin end-to-end UI before polish; parametrized InProcess/Http conformance suite; boundary AST test. Fri 18:00 = scope-cut checkpoint.
- **WP09** (Sat): one-page projection first; static door grid before rotunda component; anchors survive font/pagination change; manual iPad/Android landscape smoke recorded. Sphere = bundled public-domain preview only.
- **WP10** (Sat): `demo_traffic.py --n 40` → all 5+ charts populated; feedback UI→service→DB verified live (v1-style). Sat 18:00 = **GO/NO-GO**.
- **WP11** (Sun Sep 7): reviewer Compose all-healthy; v2 drill green (cited answer + exact scene anchor + Coffee Table restart + chart data); README + docs set + rubric self-audit + course map + video + screenshots; pre-publish scan (gitleaks + homelab-info grep); `just publish` → public repo; Streamlit Cloud pinned to the submitted hash; record repo/URL/hash/timestamp; **submit**; re-verify project.md sha256 (`fde0647a…`) first.

## 6. Rubric target (product doc §11): 21 core + 2 cloud = 23 before discretionary extras + 9 peer reviews. Never trade a scored criterion for polish. Cut order and never-cut list: product doc §13, with the correction that the HTML prototype is first to cut.

## 7. Restored guards (apply exactly as v1)

Eval regression gate red-drilled once (tamper→fail→restore, recorded); prompt-hash drift test; judge bias control + hedging guard (publish per-arm ungrounded counts — v1 proved it prevents crowning a prompt that declines most); OpenAPI snapshot guard; course map with per-row "how we run it"; corpus ADRs (banned sources grep-enforced); known-hazards registry (CPU latency numbers, compose project-name pinning, shared-host CI contention, Community Cloud memory) — each with a test or measured mitigation.

## 8. Calendar (dates authoritative; weekdays corrected)

| Date | Day | Delivery | Gate |
|---|---|---|---|
| Sep 1 | Mon (tonight) | Plan frozen; WP00 started (PR #3 merge, tag, ADRs) | fallback tagged |
| Sep 2 | Tue | WP00 done incl. **canary live**; WP01; WP02 | canary loads publicly; SQLite tests green |
| Sep 3 | Wed | WP03; WP04 | idempotent ingest; ≥4 measured arms; anchors resolve |
| Sep 4 | Thu | WP05; WP06; thin e2e | goal → cited proposal → exact open anchor |
| Sep 5 | Fri | WP07; WP08; first drill attempt | **scope-cut 18:00** |
| Sep 6 | Sat | WP09; WP10; Compose hardening | **GO/NO-GO 18:00** (product doc §12.4) |
| Sep 7 | **Sun** | WP11: evidence, docs, deploy, clean drill, publish, **submit by ~20:00 CET** | public URL + hash verified |
| Sep 8 | Mon 01:00 | **DEADLINE** (night Sun→Mon; TZ to confirm) | — |

## 9. Post-capstone: product doc §15 (home hardening + Obsidian contract-first, persistent cloud trial with OIDC/tenant-RLS/KMS-BYOK, native Apple companion, richer federation) + commercial split (`homelib-commercial-private`) with legal review of the licence before launch.
