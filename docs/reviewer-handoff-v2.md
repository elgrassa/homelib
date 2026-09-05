# HomeLib v2 — reviewer handoff

Cold-start pack for a separate review session. Prefer this file +
[`docs/wiki/README.md`](wiki/README.md) over chat history.

**Git snapshot this handoff describes (refreshed 2026-09-05):** product tip
`v2` @ `86ba349`; readiness stack open into `v2`, oldest-first — PR-A #25
`fix/h1-h3-h2-sqlite-demo-path` (`ae83d51`) → PR-B #26
`fix/roadmap-door-monitoring-honesty` (`c2675e3`) → PR-D
`feat/crossroads-rotunda` (`ee0f318`) → PR-C `docs/stakeholder-review-wiki-mermaid-sync`.
Nothing merged by agents. The picky-review findings, scoreboard and talk track
live in [`handoffs/2026-09-05-stakeholder-picky-review-and-wiki-mermaid-handoff.md`](handoffs/2026-09-05-stakeholder-picky-review-and-wiki-mermaid-handoff.md);
this file keeps the cold-start map. WP11 publish/Cloud remain owner Mon.

Forgejo: http://localhost:3000/elgrassa/homelib · remote
`ssh://git@localhost:2222/elgrassa/homelib.git`

---

## 1. Project intent

HomeLib is a **local-first personal knowledge library** (LLM Zoomcamp 2026
capstone): ingest lawful books, retrieve exact passages, ask a cited mentor,
and (later WPs) build Coffee Table paths / projection reading.

**Plan 2.1 alignment:** product SOT = [`specs/product.md`](../specs/product.md);
execution SOT = [`docs/plan-v2.md`](plan-v2.md) (**verbatim freeze** — corrections
live in [`docs/evidence.md`](evidence.md) addendum + CHECKLIST §I). Editions:
`APP_MODE=demo` (resettable showcase) vs `selfhosted`. Local LLM default
(Ollama / LM Studio); no paid cloud LLM lanes by default.

**Safety:** tag `v1-fallback` = `535f58b` on `main` (verified Postgres stack).
`v2` → `main` blocked until v2 cold-clone drill is green.

---

## 2. Architecture & schema (v2 on `v2` branch)

### Store

- SQLite via [`apps/store/sqlite.py`](../apps/store/sqlite.py): migrations
  `schema_migrations`, principals (`demo_session` / `local_user`), 24h demo TTL,
  `rights_status` CHECK (`unknown` fail-closed, `metadata_only` never indexed,
  `public_domain` / `licensed` indexable).
- Corpus: `books`, `blocks`, `chunks`, `chunk_embeddings` (**float32 BLOB**,
  dim 384), FTS5 `chunks_fts`, `index_state.index_revision`.
- Progress / paths (tables exist; product UI later): playlists, read/listen
  progress, areas/wings, bookmarks, query_log, feedback, conversation.

### Key modules

| Area | Path | Notes |
|---|---|---|
| Ingest | `apps/ingest/sqlite_pipeline.py` | dlt → staging → canonical sync; rebuild FTS + bump revision |
| Retrieval | `homelib_rag.sqlite_index` / `hybrid` / `rerank` / `rewrite` | Dispatch when `HOMELIB_SQLITE_PATH` set |
| Scene search | `homelib_rag.scene_search` | Exact/Keyword/Semantic/Smart/Ask + anchors |
| Catalog | `homelib_rag.connectors` | Fixture-first OL / Gutenberg / Standard Ebooks |
| Mentor | `homelib_rag.mentor` | Intake proposals only — **no DB writes** |
| API / UI | `apps/api`, `apps/ui` | SQLite when `HOMELIB_SQLITE_PATH` set; Crossroads + Coffee Table + Observatory + Projection |
| Runtime | `apps/runtime_settings.py` | `APP_MODE` skeleton |

Canonical seed counts after `run_sqlite_pipeline`: **18 / 729 / 9168 / 9168**.

---

## 3. How to run locally

```bash
cd /path/to/homelib
cp .env.example .env          # if needed
uv sync --all-extras

# Edition
# .env: APP_MODE=demo
# .env: HOMELIB_SQLITE_PATH=data/homelib.sqlite

# Seed SQLite (embeddings — minutes first time)
uv run python -c "from pathlib import Path; from apps.ingest.sqlite_pipeline import run_sqlite_pipeline; run_sqlite_pipeline(Path('data/homelib.sqlite'))"

export HOMELIB_SQLITE_PATH=$PWD/data/homelib.sqlite APP_MODE=demo
just ci                       # ruff + mypy + gitleaks + pytest ≥90%
just eval-retrieval           # 4 arms × 235 Q, LLM-free

# v1 Compose reviewer path (Postgres + Ollama + API + UI) — still the
# runnable HTTP surface on this tip:
just up && just seed
open http://localhost:8501    # UI (override UI_PORT in .env)
open http://localhost:8000/docs
```

Ports (defaults; override in `.env`): API `8000`, UI `8501`, Grafana `3001`,
Ollama `11434`, Postgres `5432`. Always `-p homelib --env-file .env`.

**Known host issue (2026-09-03):** Docker Desktop can hang (`docker info`
non-returning). If Compose will not start, v2 library path + eval still
verify without it; Ollama on `:11434` may still answer.

Wiki detail: [`docs/wiki/local-development.md`](wiki/local-development.md).

---

## 4. Plan 2.1 / Zoomcamp checklist matrix

Status vocabulary matches CHECKLIST: `done` = command recorded in
[`docs/evidence.md`](evidence.md). Honest about v2 gaps.

### Rubric (CHECKLIST §A) — mostly **v1 evidence on `main`**

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Problem description | done (v1) | README |
| 2 | Retrieval KB + LLM | done (v1); **v2 wired** when `HOMELIB_SQLITE_PATH` | health/books/ask/feedback + mentor/scene/playlists/observatory |
| 3 | Retrieval evaluation | done | v1 ADR-001; **v2 SQLite re-measure** `evals/results/retrieval.md` + ADR-001 §v2 |
| 4 | LLM evaluation | done (v1) | ADR-003 null result |
| 5 | Interface UI or API | done | FastAPI (18 paths) + Streamlit Crossroads: **seven doors** behind the rotunda (PR-B, PR-D), static grid always rendered |
| 6 | Ingestion dlt | done | v1 Postgres; v2 SQLite pipeline tests + seed |
| 7 | Monitoring ≥5 charts + feedback | done | Observatory (`GET /v1/observatory`, 6 charts over SQLite `query_log`) + thumbs; asserted by the drill. Grafana charts Postgres only — empty on the tip path (ADR-005 addendum) |
| 8 | Containerization | done (v1) | `docker/` compose |
| 9 | Reproducibility | done on `d6f9946`; **re-run pending** | `just drill` PASSED 2026-09-04 on a quiet box; the 2026-09-05 re-run on `ae83d51` passed clone/seed/health and FAILED the ask step under host load 340–410 (3/5 asks hit the 300 s timeout) — `docs/evidence.md` |
| 10 | Hybrid + rerank + rewrite | done | rewrite rejected on evidence |
| 11–12 | Bonus cloud / extras | optional / partial | late owner deploy |

### v2 WPs (CHECKLIST §F)

| WP | Status | Evidence / tip |
|---|---|---|
| WP00–WP01 | done | PR #4–#5 |
| WP02 | done | PR #6 → `v2` |
| WP03 | done | PR #7 @ `16269a9` |
| WP04 | done | PR #8 @ `8653148` + eval branch (BLOB/FTS fixes, metrics, ADR) |
| WP05 | done | PR #9 @ `bda328a`; `docs/wiki/` |
| WP06 | done | PR #10 @ `39b9146`; API `POST /v1/mentor/intake` |
| WP07 | done | Coffee Table store + `/v1/playlists/*` + progress |
| WP08 | done | Crossroads doors + HomelibClient conformance + AST |
| WP09 | done | One-page projection; static doors; rotunda shipped in PR-D (inline `st.html`, grid kept beneath) |
| WP10 | done | Observatory ≥5 + `demo_traffic.py` + feedback DB |
| WP11 | drill green on `d6f9946`, red under load on `ae83d51` | Docs/evidence synced (PR-C); **quiet-box drill re-run, Cloud, publish, peers = owner Mon** |

### Named WP04 eval numbers (SQLite, 2026-09-03)

| arm | hit-rate@5 | MRR@5 | degraded |
|---|---:|---:|---:|
| lexical | 0.064 | 0.055 | 0 |
| vector | 0.630 | 0.473 | 0 |
| hybrid | 0.638 | 0.483 | 0 |
| **hybrid_rerank** | **0.638** | **0.572** | 0 |

Winner unchanged. Baseline floors in `evals/eval-baseline.json` updated for
SQLite (notes record supersession of 0.174 Postgres floor).

---

## 5. Wiki map

Maintained as repo markdown under `docs/wiki/` (sync to Forgejo wiki is
**manual** if the instance wiki is used).

| Page | Contents |
|---|---|
| [README](wiki/README.md) | Index + ground-truth hierarchy |
| [architecture-overview](wiki/architecture-overview.md) | Stack, editions, v1→v2 |
| [decision-log](wiki/decision-log.md) | Forks → ADRs |
| [repo-structure](wiki/repo-structure.md) | Tree, branch model |
| [data-model-and-schemas](wiki/data-model-and-schemas.md) | ER / API map |
| [user-flows](wiki/user-flows.md) | Demo / search / ingest sequences |
| [retrieval-pipeline](wiki/retrieval-pipeline.md) | FTS5, matrix, RRF, scene |
| [local-development](wiki/local-development.md) | `just`, env, compose |
| [debugging-and-troubleshooting](wiki/debugging-and-troubleshooting.md) | CI lanes, hazards |
| [improving-the-system](wiki/improving-the-system.md) | Extension points |

---

## 6. What to verify in review

1. **SQLite path:** seed counts; `just eval-retrieval` winner + 0 degraded;
   ADR-001 §v2 present; baseline notes mention SQLite.
2. **Regression tests:** `test_load_matrix_accepts_float32_blob_embeddings`,
   `test_fts_query_drops_english_stopwords_like_plainto_tsquery`.
3. **Connectors / mentor:** fixture tests; intake never writes; high-stakes
   notice; abstention on empty evidence.
4. **Rights / GDPR:** unknown fail-closed; metadata_only not in FTS; queries
   hashed by default; local-first LLM.
5. **Coverage floor:** `just ci` ≥ 90%.
6. **Honest residual (WP11):** quiet-box `just drill`, Compose all-healthy
   e2e proof, `just publish`, Streamlit Cloud, peer×3 — **owner Mon**. Do not
   claim a live public URL from this branch tip.
7. **Compose:** if Docker healthy, `just up` + `/health` + one `/v1/ask`.
   For SQLite demo path also set `HOMELIB_SQLITE_PATH` + seed.

---

## 7. Known gaps / improvements (priority)

1. **P0 — Quiet-box `just drill`** green before `v2`→`main` (criterion 9).
2. **P0 — Regenerate OpenAPI snapshot** for new v2 routes.
3. **P1 — Compose all-healthy e2e** with SQLite profile documented.
4. **P1 — Matched Postgres vs SQLite vector bake-off** (do not over-claim
   0.106→0.630 lift).
5. **P2 — Live OL smoke** outside CI (fixtures-only in CI by design).
6. **P3 — UX polish:** rotunda **shipped** (PR-D); sphere and audio stay cut-order last.
7. **Mon owner:** Cloud deploy, `just publish`, peer ×3 schedule.

---

## 8. Current git state

| Ref | SHA / note |
|---|---|
| `forgejo/v2` | `86ba349` — product tip; the stack below merges into it oldest-first |
| `main` / `v1-fallback` | `535f58b` |
| Open PRs | #25 PR-A → #26 PR-B → PR-D → PR-C, each gated by `just ci` before push; agents never merge |

Merge style: `tea pulls merge <n> --style rebase`. No force-push to `v2`/`main`.
