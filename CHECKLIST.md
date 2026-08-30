# homelib — submission checklist

Tracks the LLM Zoomcamp 2026 rubric (`DataTalksClub/llm-zoomcamp/project.md`),
self-hosted Docker readiness, and the "nice to have" work that makes this a
maintainable product rather than a submission.

**Status vocabulary is deliberately strict.** `done` means verified by a command
whose output is recorded in [`docs/evidence.md`](docs/evidence.md) — not "the
code exists". Anything unverified is `partial`, however finished it looks.

Last updated: 2026-08-30.

---

## A. Rubric — the graded criteria (26 points)

| # | Criterion | Max | Status | Evidence / what remains |
|---|---|---|---|---|
| 1 | **Problem description** | 2 | ✅ done | README states the problem in user terms: unsearchable shelf, unplanned reading order |
| 2 | **Retrieval flow** — KB **and** LLM both used | 2 | ✅ done | Postgres FTS + pgvector + grounded answer with validated citations (WP-14) |
| 3 | **Retrieval evaluation** — multiple approaches, best one used | 2 | 🟡 partial | 235-pair ground truth ✅, hit-rate/MRR ✅ (hand-computed tests); 4-arm comparison + ADR-001 pending |
| 4 | **LLM evaluation** — multiple approaches, best one used | 2 | 🟡 partial | Harness ✅ (3 variants, judge with bias control, prompt-hash drift). Live bake-off still to run — it already found the answer-path defect |
| 5 | **Interface** — UI or API | 2 | ✅ done | Both: FastAPI (7 endpoints, OpenAPI snapshot pinned) and a 3-tab Streamlit UI |
| 6 | **Ingestion pipeline** — automated, e.g. **dlt** | 2 | ✅ done | Real dlt source/resources, ELT into the canonical schema; 37 tests, 0 skipped, against a live Postgres |
| 7 | **Monitoring** — feedback **and** dashboard ≥5 charts | 2 | 🟡 partial | Dashboard ✅ 6 panels, every query executed against the live schema. Feedback loop needs the API |
| 8 | **Containerization** — everything in docker-compose | 2 | ✅ done | 7 services, digest-pinned, healthchecked; postgres + grafana verified healthy |
| 9 | **Reproducibility** — runs as described, data available, versions pinned | 2 | 🟡 partial | Exact pins ✅, snapshot committed ✅, digests ✅; full cold-clone drill blocked on the API |
| 10 | **Best practices** — hybrid (1) + rerank (1) + rewrite (1) | 3 | 🟡 partial | All three implemented ✅; the point needs the eval table showing they were compared |
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
- [ ] Eval regression gate wired into CI as a blocking step
- [x] `specs/openapi.snapshot.json` drift guard green
- [x] ADR-002 (catalog source) written — records the Kaggle/Google Books/Goodreads rejections, enforced by a grep test
- [ ] ADR-001 (retrieval arm) — blocked on the 4-arm eval table
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
6. **The local 7B model is the current ceiling on answer quality.** After the
   citation fixes, 7/12 sampled questions answer without degrading; the rest
   are the model returning a bare `{}` or quoting text that appears in no
   passage. Both are correctly rejected rather than passed off as grounded.
   This is what the prompt-variant bake-off exists to move.
