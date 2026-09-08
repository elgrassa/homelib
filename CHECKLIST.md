# homelib — submission checklist

Tracks the LLM Zoomcamp 2026 rubric (`DataTalksClub/llm-zoomcamp/project.md`),
self-hosted Docker readiness, and the "nice to have" work that makes this a
maintainable product rather than a submission.

**Status vocabulary is deliberately strict.** `done` means verified by a command
whose output is recorded in [`docs/evidence.md`](docs/evidence.md) — not "the
code exists". Anything unverified is `partial`, however finished it looks.

Last updated: 2026-09-08 (`just drill` PASSED on the merged tip; Cloud demo live at https://homelib.streamlit.app/; WP11 residual = owner `just publish` + submission SHA + peers).

---

## A. Rubric — the graded criteria (26 points)

| # | Criterion | Max | Status | Evidence / what remains |
|---|---|---|---|---|
| 1 | **Problem description** | 2 | ✅ done | README states the problem in user terms: unsearchable shelf, unplanned reading order |
| 2 | **Retrieval flow** — KB **and** LLM both used | 2 | ✅ done | Dual store: SQLite FTS5 + float32 matrix on the tip path (ADR-004), Postgres FTS + pgvector on `v1-fallback`; grounded answer with validated citations; PR-A made the SQLite-only host answer (`test_answer_end_to_end_not_degraded_on_sqlite_only_host`) |
| 3 | **Retrieval evaluation** — multiple approaches, best one used | 2 | ✅ done | 4 arms × 235 questions, 0 degraded; ADR-001 records the choice and the evidence |
| 4 | **LLM evaluation** — multiple approaches, best one used | 2 | ✅ done | 4 arms (3 challengers + production control) × 30 questions, judge with bias control. **Null result, recorded in ADR-003**: run-to-run variance exceeds between-arm spread, so the incumbent stays |
| 5 | **Interface** — UI or API | 2 | ✅ done | Both: FastAPI (**20** OpenAPI paths, snapshot pinned) and the Streamlit Crossroads — **seven doors** (Ask, Mentor, Roadmap, Coffee Table, Shelf, Observatory, Projection), rotunda above the grid (PR-D) |
| 6 | **Ingestion pipeline** — automated, e.g. **dlt** | 2 | ✅ done | Real dlt source/resources, ELT into the canonical schema for both stores; `just seed` (Postgres) + `just seed-sqlite` (`python -m apps.ingest.sqlite_pipeline`, exit 1 on an empty seed); 18/729/9168/9168 |
| 7 | **Monitoring** — feedback **and** dashboard ≥5 charts | 2 | ✅ done | Observatory door: **nine chart definitions** over SQLite `query_log` + `spans` + 👍/👎 → `POST /v1/feedback`; the drill asserts the ask it made appears in `queries_over_time` (PR-B). Online judge is operator-run (`scripts/judge_recent.py`), off by default. Grafana is v1 and empty on the tip path (ADR-005 addendum) |
| 8 | **Containerization** — everything in docker-compose | 2 | ✅ done | postgres, ollama, api, ui, grafana + `seed`-profile ingest, digest-pinned, healthchecked; api pinned `APP_MODE=selfhosted`; seeds run `--build` so a stale image can never pass (PR-A) |
| 9 | **Reproducibility** — runs as described, data available, versions pinned | 2 | ✅ done (train tip `ee0f318`) | Exact pins ✅, snapshot ✅, digests ✅, context window pinned ✅. **`just drill` PASSED on the train tip `ee0f318`** (2026-09-05 22:01, ~68 min at host load 200–440: cold clone from `.env.example`, `--build` Postgres seed 18 books, `--build` SQLite seed 18/729/9168/9168, `/health` ok 18/9168, ask attempt 1 timed out at 300 s, **attempt 2 grounded `hybrid_rerank` with a resolving citation**, Observatory then reported 6 charts / 5 populated — tip now ships **9 chart defs**; `queries_over_time` 1 point). History: PASSED on `v2` @ `d6f9946` (2026-09-04, quiet box, attempt 1/5); re-run #1 on `ae83d51` (2026-09-05) passed clone/`--build` seeds/health and **failed** the ask step under load 340–410 (3/5 timeouts) — infra, recorded in [`docs/evidence.md`](docs/evidence.md). `v2` itself is not re-drilled until the train merges. The drill asserts the Observatory (`queries_over_time`), not Grafana panel counts. |
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
- [x] `docker compose up` verified all-healthy **end to end** — `homelib-{api,ui,grafana,postgres,ollama}-1` healthy; API `:8010/health` 200 (2026-09-04)
- [x] Cold-clone drill green (`just drill`) — PASSED @ `d6f9946` (2026-09-04, ~9 min, quiet box) **and @ `ee0f318`** (2026-09-05, ~68 min under load, attempt 2/5 — the readiness-train tip); the 2026-09-05 re-run on `ae83d51` failed the ask step under load (evidence)
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
   36 commits pushed, CI green on the first push, `main` seeded from that
   verified commit and set as default. PR #1 open.
2. ~~dlt pipeline is red~~ **Resolved 2026-08-30** via exactly that ELT
   shape. 37 tests, 0 skipped, against a live Postgres.
3. **Open Library has no `description` field** on `search.json` (0% coverage).
   Harmless: the roadmap always generates its own rationale.
4. ~~The local model invents authors~~ **Closed structurally 2026-08-30.** The
   schema the model fills has no `book_title`/`book_id` field, so an invented
   attribution has no path into a response; titles come from Postgres.
5. **LLM eval must stay bounded** — ~13s per grounded answer warm.
6. **Two latent LLM-config hazards, recorded not fixed.** `_TIMEOUT_SECONDS = 30`
   in `OpenAIClient` is a production ceiling a cold model load can blow through,
   and `_MAX_CONTEXT_HITS = 20` would put prompts near ~7,600 tokens — fine on
   the current 32k-context model, not fine on a 4k or 8k one, and silent from
   the client side either way.
7. **A zero-citation answer currently counts as a success.** `degraded=False`
   with `citations=[]` is the legitimate "the passages do not answer this"
   reply, but it means a prompt variant can win the bake-off by declining more
   often. No winner is published without the per-arm count of ungrounded
   successes.
8. **The local 7B model is the current ceiling on answer quality.** After the
   citation fixes, 7/12 sampled questions answer without degrading; the rest
   are the model returning a bare `{}` or quoting text that appears in no
   passage. Both are correctly rejected rather than passed off as grounded.
   This is what the prompt-variant bake-off exists to move.
9. **Two drills on the readiness train, one red, one green — both recorded.** Re-run #1
   on `ae83d51` (2026-09-05) passed clone, `--build` seeds and `/health` 18/9168, then
   3 of 5 asks hit the 300 s timeout under host load 340–410 with a CPU Ollama:
   infra, not a request-path change, and not waved through. Re-run #2 on the train
   tip `ee0f318` **PASSED** the same evening (attempt 2/5, one load timeout). The
   lesson stays: a loaded box turns a 7B CPU model into timeouts; drill on a quiet
   box or read the attempt count, never the verdict alone.

---

## F. v2 work packages (WP00–WP11)

v1 evidence above stays. This section tracks the rebuild. Status vocabulary unchanged: `done` means a command in [`docs/evidence.md`](docs/evidence.md).

| WP | Scope | Status |
|---|---|---|
| **WP00** | Plan freeze, `v1-fallback` tag, ADRs, mockups, CI `v2` trigger, demo-mode config skeleton, schema *draft* | ✅ done — PR #4 merged |
| **WP01** | Specs + OpenAPI snapshot for §8 endpoints | ✅ done — PR #5 merged |
| **WP02** | SQLite, principals, isolation tests | ✅ done — PR #6 → `v2` |
| **WP03** | Ingest + rights; chunk ids match v1 | ✅ done — PR #7 → `v2` @ `16269a9` |
| **WP04** | FTS5 + matrix + evals | ✅ done — PR #8 → `v2` @ `8653148`; SQLite eval + ADR-001 §v2 on `feat/wp04-eval-sqlite` |
| **WP05** | Lawful connectors | ✅ done — PR #9 → `v2` @ `bda328a` |
| **WP06** | Mentor + cited answer (library) | ✅ done — PR #10 → `v2` @ `39b9146`; API route `POST /v1/mentor/intake` wired |
| **WP07** | Coffee Table + progress | ✅ done — store ops + §5.6 reds + `/v1/playlists/*` + `/v1/progress` |
| **WP08** | Thin Streamlit e2e (mockups are UX SOT) | ✅ done — Crossroads doors → Ask/Mentor/Roadmap/Coffee Table/Shelf/Observatory/Projection (`DOOR_RENDERERS` ≡ `CROSSROADS_DOORS`); rotunda PR-D |
| **WP09** | Projection; static doors before rotunda | ✅ done — one-page projector toggle + progress save; rotunda shipped in PR-D (inline `st.html`, static grid kept beneath) |
| **WP10** | Observatory ≥5 charts + feedback | ✅ done — `GET /v1/observatory` + UI + `scripts/demo_traffic.py` |
| **WP11** | Docs, drill, owner publish + Cloud | 🟡 drill ✅; Cloud demo live at https://homelib.streamlit.app/ (2026-09-08). Residual: owner `just publish` / public snapshot, submission SHA in evidence, peer×3 |

**Progress (2026-09-04):** WP00–WP10 on `v2` @ `d6f9946` (PR #15). **`just drill` PASSED** (criterion 9). Compose fleet all healthy. **v2 build ≈95%** of WP00–WP11. Remaining: Mon owner publish/Cloud/submit/peer×3. `v2`→`main` unblocked on drill.

**Progress (2026-09-05):** readiness train open into `v2` @ `86ba349`, nothing merged: #25 PR-A (H1/H3/H2) → #26 PR-B (Roadmap door, Observatory drill assert) → #27 PR-D (rotunda) → #28 PR-C (docs) → #29 PR-E (graphify jobs, draft). Local `just ci` green on every head; `just drill` PASSED on `ee0f318`. Merge order A → B → D → C → E; restack after each merge.

**GO/NO-GO** Sun Sep 6 18:00 (product §12.4; **local gate per addendum** — not live public URL). **One definition — the compose reviewer path on the train tip:** `just up && just seed && just seed-sqlite` → `/health` ok 18/9168, ask → cited answer that opens → 👍 → the ask is a point on the Observatory, Coffee Table add → rerun → still there in selfhosted, seven doors + rotunda; both evals committed; ingest repeatable; `just drill` green on the tip (it is: `ee0f318`). The `APP_MODE=demo` rehearsal (fresh session-isolated state, resettable seed, RSS within Community Cloud limits, cited answer via Groq) is the **bonus-#11 gate for PR-B2 and the owner's Cloud deploy — it is not GO/NO-GO** and never blocks rows 1–10. NO-GO ⇒ submit v1 (`v1-fallback` @ `535f58b`) Monday.

### Cut order (HTML prototype first)

1. standalone HTML prototype (reference copy in `docs/mockups/`; do not ship it)
2. Memory Sphere particles and polish
3. two-page projection (keep one-page)
4. custom rotating-room (keep static door grid)
5. live Standard Ebooks (OL + Gutenberg + optional Google Books / Hardcover live; fixtures in CI)
6. full audio generation (keep one preview)
7. rewrite in production if eval does not justify it (v1 already evaluated and rejected)

### Scored bar — do not drop for v2 UX

Problem description; KB+LLM flow; multiple retrieval evals; multiple LLM evals; UI **and** API; dlt ingest; feedback **and** ≥5 charts; full compose; reproducible pins + data; hybrid; rerank; query rewrite evaluated (v1 rejected on evidence — still counts); cloud deploy on submission day (owner). Peer reviews: owner, after submit.

---

## H. WP00 landing checklist (this PR)

- [x] `v1-fallback` tag at PR #3 merge (`535f58b1a47d3545c1e4b6a36e75c06b58f5a640`)
- [x] `specs/product.md` + `docs/plan-v2.md` (verbatim)
- [x] ADR-004 … ADR-010 (ADR-010 = single-repo delayed paid tier)
- [x] `docs/mockups/` UX SOT + HTML prototype reference
- [x] `specs/data-model.md` draft
- [x] CI `on.push.branches: [main, v2]`
- [x] `APP_MODE` config skeleton (not FTS5)
- [x] Forgejo CI green on this PR
- [x] rebase-merge into `main`; branch `v2` from that SHA

---

## I. Stacked review protocol (v2, binding 2026-09-01)

Pavlo merges **oldest → newest** (~10 PRs into `v2`). Agents do **not** merge to
`v2` or `main`.

- **Merge style:** rebase-merge only (Forgejo UI or an equivalent CLI).
  Restack downstream feature branches after each merge.
- **Draft newer PRs** until their base PR lands; avoid parallel review of
  dependent stacks.
- **`v2` → `main`:** DONE 2026-09-06 — `main` = `v2` = `eb4a4ff` (fast-forward, no merge commit); re-synced after #32 (MagicLib design-sync inputs, `5881157` + bot graph `96b3967`) — `main` follows every `v2` bot commit. Protocol from now on: push to `v2` first, wait for the `graph-refresh` bot commit (its push does not trigger a run), then fast-forward `main` to that tip. `main` never refreshes its own graph (a rebuild is not byte-stable — community ids, manifest mtimes, cache paths — so a main-side refresh forked `main` from `v2` on every fast-forward until `ci/graph-refresh-v2-only` landed 2026-09-06).
- **`v2` collapsed into `main` (2026-09-06, owner: "collapse v2 into main"):** `main` = `v2` = `8a0c6fc` at the time; `ci.yml` `push` scoped to `main`, `graph-refresh` refreshes on `main` and refuses a recreated `v2`, `post-merge-cleanup` protects `main` only. `main` is the single long-lived branch; every PR targets it. The bullet above is history. After the PR merges, delete `v2` on Forgejo.
- **PR #4** is closed history (WP00 landed via that merge).
- **Sep 2 gate (addendum):** no public canary until Mon Sep 7 owner deploy;
  rehearse `APP_MODE=demo` locally instead (see [`docs/evidence.md`](docs/evidence.md)
  addendum §2–§4).

---

