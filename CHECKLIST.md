# homelib — submission checklist

Tracks the LLM Zoomcamp 2026 rubric (`DataTalksClub/llm-zoomcamp/project.md`),
self-hosted Docker readiness, and the "nice to have" work that makes this a
maintainable product rather than a submission.

**Status vocabulary is deliberately strict.** `done` means verified by a command
whose output is recorded in [`docs/evidence.md`](docs/evidence.md) — not "the
code exists". Anything unverified is `partial`, however finished it looks.

Last updated: 2026-09-01.

---

## A. Rubric — the graded criteria (26 points)

| # | Criterion | Max | Status | Evidence / what remains |
|---|---|---|---|---|
| 1 | **Problem description** | 2 | ✅ done | README states the problem in user terms: unsearchable shelf, unplanned reading order |
| 2 | **Retrieval flow** — KB **and** LLM both used | 2 | ✅ done | Postgres FTS + pgvector + grounded answer with validated citations (WP-14) |
| 3 | **Retrieval evaluation** — multiple approaches, best one used | 2 | ✅ done | 4 arms × 235 questions, 0 degraded; ADR-001 records the choice and the evidence |
| 4 | **LLM evaluation** — multiple approaches, best one used | 2 | ✅ done | 4 arms (3 challengers + production control) × 30 questions, judge with bias control. **Null result, recorded in ADR-003**: run-to-run variance exceeds between-arm spread, so the incumbent stays |
| 5 | **Interface** — UI or API | 2 | ✅ done | Both: FastAPI (7 endpoints, OpenAPI snapshot pinned) and a 3-tab Streamlit UI |
| 6 | **Ingestion pipeline** — automated, e.g. **dlt** | 2 | ✅ done | Real dlt source/resources, ELT into the canonical schema; 37 tests, 0 skipped, against a live Postgres |
| 7 | **Monitoring** — feedback **and** dashboard ≥5 charts | 2 | ✅ done | 6 panels + feedback loop **verified live end to end**: ask → request_id → 👍 → persisted in `query_log` |
| 8 | **Containerization** — everything in docker-compose | 2 | ✅ done | 7 services, digest-pinned, healthchecked; postgres + grafana verified healthy |
| 9 | **Reproducibility** — runs as described, data available, versions pinned | 2 | 🟡 partial | Exact pins ✅, snapshot ✅, digests ✅, context window now pinned ✅. **Remaining core work: run `just drill`** — no longer blocked, the API is up |
| 10 | **Best practices** — hybrid (1) + rerank (1) + rewrite (1) | 3 | ✅ done | All three implemented **and measured**. Rewrite compared on a matched sample and rejected on evidence — a recorded negative result |
| 11 | **Bonus: cloud deployment** | 2 | ⬜ optional | Buffer-day only. Never at the cost of 1–10 |
| 12 | **Bonus: extras** | 3 | 🟡 partial | Eval regression gate ✅ built; audiobook + Obsidian BookShelf are buffer-day |
| — | **Peer reviews (×3)** | +9 | ⬜ todo | **Required, and time-boxed — schedule ≥2h after submitting** |

**Floor without any bonus: 21/26.** Never trade a graded criterion for a bonus.

## B. Self-hosted Docker readiness

- [x] One `docker compose up` brings up the whole product — 7 services
- [x] Every image pinned by tag **and** digest (postgres 17.11, ollama 0.33.2, grafana 13.0.2)
- [x] Per-service healthchecks; dependants wait on `service_healthy`
- [x] All ports loopback-bound, and overridable from `.env` for busy machines
- [x] Local LLM in-stack by default — **no account, no API key required**
- [x] Cloud provider is a documented override, not a requirement
- [x] Embedding weights baked into the image — verified offline via `--network none`
- [x] Images lean enough to actually build: **18.5 GB → 2.68 GB**
- [x] Grafana on a read-only DB role — verified `INSERT` is refused
- [x] Schema created by `initdb/`; ivfflat index deferred until after load
- [ ] `docker compose up` verified all-healthy **end to end** (needs api + ui + ingest images)
- [ ] Cold-clone drill green (`just drill`) — script written, blocked on the API
- [ ] Reviewer path timed end to end on a clean machine

## C. Engineering quality (the "maintainable, extendable" half)

- [x] **Spec-first**: 18 one-page specs written before their code
- [x] `just ci` = ruff + mypy --strict + gitleaks + pytest, **90% coverage floor enforced**
- [x] Gates split by cost: pre-push is fast (11.7s measured, 355 tests); the PR runs the 13 integration/slow/llm tests and the coverage floor
- [x] Exact pins everywhere; `uv.lock` authoritative; CI uses `--frozen` so drift fails
- [x] Forgejo CI with the pinned checkout SHA (hostexecutor runners never auto-clone) — **verified green on the real runner**, not just written
- [x] Every new module ships behavioural tests in the same commit
- [x] Degradation is contractual, not incidental — rerank returns `None`, rewrite falls back, hybrid reports the arm it actually used
- [x] Privacy by default: queries logged as a 16-char sha256 prefix, plaintext opt-in
- [x] Secrets never staged; `.gitleaks.toml` **enforced** in CI and pre-push (it was wired into nothing until 2026-08-30); `.env.example` committed
- [x] `docs/evidence.md` records every verification — including a diagnosis I got wrong and retracted
- [x] Eval baselines replaced with measured values + honest notes; gate exits 0
- [ ] Eval regression gate wired into CI as a blocking step
- [x] CI split by cost across lanes: quick gate (ruff/gitleaks/mypy/fast tests) + heavy full suite with the coverage floor
- [x] `specs/openapi.snapshot.json` drift guard green
- [x] ADR-002 (catalog source) written — records the Kaggle/Google Books/Goodreads rejections, enforced by a grep test
- [x] ADR-001 (retrieval arm) — hybrid+rerank on measured evidence; rewrite rejected
- [ ] Fresh-eyes pass: no dead code, no stale docstrings

## D. Nice to have — extendability

- [ ] **Audiobook** — one chapter to WAV via a local TTS endpoint (ffmpeg `concat` demuxer, not a mixer)
- [ ] **Obsidian BookShelf** — one note per book, atomic write
- [ ] DjVu confirmed against a real-world file, not only a synthesized fixture
- [ ] Incremental re-ingest of a single book without a full reload
- [ ] Multi-language corpus (parsers are language-agnostic; the FTS config is not)
- [ ] `homelib-core` reusable as the `read_document` seam for LocalExpert

## E. Known gaps, stated plainly

1. ~~No Forgejo remote~~ **Resolved 2026-08-30.** `elgrassa/homelib` is live;
   36 commits pushed, CI green first try (run 12254), `main` seeded from that
   verified commit and set as default. PR #1 open.
2. ~~dlt pipeline is red~~ **Resolved 2026-08-30** via exactly that ELT
   shape. 37 tests, 0 skipped, against a live Postgres.
3. **Open Library has no `description` field** on `search.json` (0% coverage).
   Harmless: the roadmap always generates its own rationale.
4. ~~The local model invents authors~~ **Closed structurally 2026-08-30.** The
   schema the model fills has no `book_title`/`book_id` field, so an invented
   attribution has no path into a response; titles come from Postgres.
5. **LLM eval must stay bounded** — ~13s per grounded answer warm.
7. **Two latent LLM-config hazards, recorded not fixed.** `_TIMEOUT_SECONDS = 30`
   in `OpenAIClient` is a production ceiling a cold model load can blow through,
   and `_MAX_CONTEXT_HITS = 20` would put prompts near ~7,600 tokens — fine on
   the current 32k-context model, not fine on a 4k or 8k one, and silent from
   the client side either way.
8. **A zero-citation answer currently counts as a success.** `degraded=False`
   with `citations=[]` is the legitimate "the passages do not answer this"
   reply, but it means a prompt variant can win the bake-off by declining more
   often. No winner is published without the per-arm count of ungrounded
   successes.
6. **The local 7B model is the current ceiling on answer quality.** After the
   citation fixes, 7/12 sampled questions answer without degrading; the rest
   are the model returning a bare `{}` or quoting text that appears in no
   passage. Both are correctly rejected rather than passed off as grounded.
   This is what the prompt-variant bake-off exists to move.

---

## F. v2 work packages (WP00–WP11)

v1 evidence above stays. This section tracks the rebuild. Status vocabulary unchanged: `done` means a command in [`docs/evidence.md`](docs/evidence.md).

| WP | Scope | Status |
|---|---|---|
| **WP00** | Plan freeze, `v1-fallback` tag, ADRs, mockups, CI `v2` trigger, demo-mode config skeleton, schema *draft* | 🟡 landing this PR — tag exists; FTS5 demo smoke is **not** this PR |
| **WP01** | Specs + OpenAPI snapshot for §8 endpoints | ⬜ |
| **WP02** | SQLite, principals, isolation tests | ⬜ |
| **WP03** | Ingest + rights; chunk ids match v1 | ⬜ |
| **WP04** | FTS5 + matrix + evals | ⬜ |
| **WP05** | Lawful connectors | ⬜ |
| **WP06** | Mentor + cited answer | ⬜ |
| **WP07** | Coffee Table + progress | ⬜ |
| **WP08** | Thin Streamlit e2e (mockups are UX SOT) | ⬜ |
| **WP09** | Projection; static doors before rotunda | ⬜ |
| **WP10** | Observatory ≥5 charts + feedback | ⬜ |
| **WP11** | Docs, drill, owner publish + Cloud | ⬜ |

**GO/NO-GO** Sat Sep 6 18:00 (product §12.4). NO-GO ⇒ submit v1 (`v1-fallback`). Never trade a scored 2-point row for polish / Home/Pro / rotunda / TTS.

### Cut order (HTML prototype first)

1. standalone HTML prototype (reference copy in `docs/mockups/`; do not ship it)
2. Memory Sphere particles and polish
3. two-page projection (keep one-page)
4. custom rotating-room (keep static door grid)
5. live Standard Ebooks/Gutenberg (keep fixtures + live OL)
6. full audio generation (keep one preview)
7. rewrite in production if eval does not justify it (v1 already evaluated and rejected)

### Scored bar — do not drop for v2 UX

Problem description; KB+LLM flow; multiple retrieval evals; multiple LLM evals; UI **and** API; dlt ingest; feedback **and** ≥5 charts; full compose; reproducible pins + data; hybrid; rerank; query rewrite evaluated (v1 rejected on evidence — still counts); cloud deploy on submission day (owner). Peer reviews: owner, after submit.

---

## G. Never commit before public GitHub (`just publish`)

Paid tier lands in the **same Forgejo repo after** the public snapshot and Forgejo is private (ADR-010). Until then, do **not** commit:

- [ ] arbitrary personal-book ingestion
- [ ] hardened EPUB/PDF/OCR pipelines (beyond v1 parsers already public)
- [ ] persistent private conversations/artifacts beyond demo-session / single-principal capstone paths
- [ ] LM Studio discovery and model-management UI
- [ ] production local TTS/STT
- [ ] Silver Memory generation
- [ ] polished sphere and rotunda assets
- [ ] household profiles and LAN authentication
- [ ] backup, restore and migration
- [ ] Obsidian plugin
- [ ] native Apple companion
- [ ] installers, signed releases and automatic updates
- [ ] offline commercial licence verification
- [ ] signing keys or proprietary visual assets

Public showcase copy (HomeLib Home blurb + waitlist link) on the Streamlit demo is allowed.

---

## H. WP00 landing checklist (this PR)

- [x] `v1-fallback` tag at PR #3 merge (`535f58b1a47d3545c1e4b6a36e75c06b58f5a640`)
- [x] `specs/product.md` + `docs/plan-v2.md` (verbatim)
- [x] ADR-004 … ADR-010 (ADR-010 = single-repo delayed paid tier)
- [x] `docs/mockups/` UX SOT + HTML prototype reference
- [x] `specs/data-model.md` draft
- [x] CI `on.push.branches: [main, v2]`
- [x] `APP_MODE` config skeleton (not FTS5)
- [ ] Forgejo CI green on this PR
- [ ] rebase-merge into `main`; branch `v2` from that SHA

