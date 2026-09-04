# Handoff — Zoomcamp checklist + plan v2.1 verification

**Audience:** a fresh model that must **evidence-verify** the LLM Zoomcamp final-project checklist and that HomeLib v2.1 plan is in place — not vibes.

**Written:** 2026-09-04 (CEST) by coordinator follow-up after UI PYTHONPATH fix session.  
**Repo:** `/Users/pavloskorodziievskyi/IdeaProjects/homelib`  
**Do not trust this handoff.** Re-run the commands in §7 before claiming anything.

Privacy: no `.env` secrets, no passwords, no PII. Ports and SHAs only.

---

## 0. Step-0 live snapshot (reconciled this session)

| Ref | Value (verify again) |
|---|---|
| `main` | `e288f210bf96f4c381609a6725b1df7f8075c9f1` — WP00 only (`docs: freeze v2.1 plan and scaffold WP00`) |
| Product tip `v2` | `3933aa402710e845979225e41af7178b091834ba` (`docs: record just drill PASSED on v2 @ d6f9946`) |
| Tag `v1-fallback` (peeled) | `535f58b1a47d3545c1e4b6a36e75c06b58f5a640` |
| Open Forgejo PRs | **Not empty.** `#1`–`#16` merged/closed; **open:** `#17` UI PYTHONPATH, `#18` compose `HOMELIB_SQLITE_PATH` (WIP) |
| UI fix commit | `fix/ui-pythonpath` @ `e579808` (on top of `v2` @ `3933aa4`) — PR `#17` |
| Compose/SQLite fix lane | `fix/compose-sqlite-path` @ `400daed` — PR `#18` (this worktree may be here; **do not confuse with product tip**) |
| Sibling worktree | `…/homelib/.claude/worktrees/fix-pytest-tmp-leak` on `fix/pytest-tmp-leak` |

```bash
cd /Users/pavloskorodziievskyi/IdeaProjects/homelib
git fetch forgejo
git rev-parse main v2 'v1-fallback^{}'
git log -1 --oneline main v2
tea pr list --state open
git worktree list
```

### What “latest” means

- Product work merges into **`v2`**, not `main`.
- Local stack / reviewer path should track **`v2` tip** (today `3933aa4`), then layer open fix PRs `#17` / `#18` if not yet merged.
- `main` remains WP00 freeze until owner merges `v2`→`main`.

---

## 1. Local stack ports (this machine’s `.env`)

Loopback-bound via compose (`127.0.0.1:…`). Values observed:

| Service | Host port | Notes |
|---|---|---|
| API | **8010** | `API_PORT=8010` |
| Grafana | **3011** | `GRAFANA_PORT=3011` |
| Ollama | **11444** | `OLLAMA_PORT=11444` |
| UI | **8501** | `UI_PORT` unset → default 8501 |
| Postgres | **5432** | `POSTGRES_PORT` unset → default 5432 |

Do not paste other `.env` keys into notes or commits.

---

## 2. Verified this session (paste / re-run)

### 2.1 UI PYTHONPATH fix (independent re-verify)

| Check | Result |
|---|---|
| Source on `fix/ui-pythonpath` | `ENV PYTHONPATH=/app` in `docker/ui.Dockerfile`; hygiene test `test_ui_dockerfile_pins_pythonpath_so_apps_imports_resolve` |
| Live container | `docker exec homelib-ui-1 printenv PYTHONPATH` → `/app` |
| UI health | `curl` `http://127.0.0.1:8501/_stcore/health` → 200 |
| Crossroads | Playwright: heading HomeLib, “Library Crossroads”, doors **Ask / Mentor / Coffee Table / Shelf / Observatory / Projection** |
| UI logs | No `ModuleNotFoundError` |
| API health | `{"status":"ok",…,"books":18,"chunks":9168}` on `:8010/health` |
| Hygiene test | `uv run pytest tests/test_repo_hygiene.py::test_ui_dockerfile_pins_pythonpath_so_apps_imports_resolve -q` → **1 passed** (when that commit is checked out) |

**Deviation from prior “uncommitted on v2” report:** sibling session committed the three-file fix to `fix/ui-pythonpath` @ `e579808` and opened PR `#17`. Live UI image still carries the rebuild. Current worktree may be `fix/compose-sqlite-path` (no `PYTHONPATH` in *that* tree’s Dockerfile) — check branch before editing.

### 2.2 Ask → citation resolve → feedback → query_log

Live API has `HOMELIB_SQLITE_PATH=/data/homelib.sqlite` (compose lane / PR `#18` wiring). **Feedback lands in SQLite**, not Postgres.

```text
POST /v1/ask  {"query":"Who wrote Walden?","rewrite":false,"k":3}
→ request_id c7b1f731-26fb-49c2-8544-17ca125fbe4d
→ citations: 3 (block_id 25a30321b30d03cc), degraded=false, answer "Henry David Thoreau"
GET /v1/blocks/25a30321b30d03cc → book_id=thoreau-walden, text "by Henry David Thoreau"
POST /v1/feedback {"request_id":"c7b1f731-…","feedback":"up"} → {"ok":true}
SQLite query_log row: feedback='up', query_sha256_prefix='900150a382f6a2cc'
```

Cold LLM asks can take **2–5+ minutes**; timeouts at 300s are possible while Ollama is busy.

### 2.3 Seed / Grafana / embeddings vs chat

| Claim | Evidence |
|---|---|
| Seed **18 / 729 / 9168 / 9168** | SQLite inside API + Postgres `books/blocks/chunks/chunk_embeddings` counts |
| Grafana **6 panels** | `docker/grafana/provisioning/dashboards/json/homelib-overview.json`: Queries/hour, Latency p50/p95, Retrieval arm, Feedback ratio, Token usage, Degraded-answer rate; Grafana `:3011/api/health` ok |
| HuggingFace | **MiniLM (`all-MiniLM-L6-v2`) bake/embed only** — not the chat model |
| Chat | **Ollama** `qwen2.5:7b-instruct` (`/health` → `llm.provider=ollama`) |

**Residual:** Grafana reads **Postgres**. With `HOMELIB_SQLITE_PATH` set, new ask/feedback rows may **not** appear on the Grafana dashboard until store/observability is reconciled. Observatory (`GET /v1/observatory`) is the v2 path.

---

## 3. Checklist verification matrix (`CHECKLIST.md` on **`v2` tip**)

Statuses below are **claims on `v2` @ `3933aa4`**. Re-verify with `git show v2:CHECKLIST.md` and commands — do not copy checkmarks blindly.

### §A Rubric (graded)

| # | Claim on v2 | Where to re-verify | Known residual |
|---|---|---|---|
| 1 Problem description | ✅ done | `README.md` | — |
| 2 Retrieval + LLM | ✅ done | `POST /v1/ask` + citations; ADR-001 | Cold LLM latency |
| 3 Retrieval eval | ✅ done | `docs/evidence.md` WP04; `just eval-retrieval` with SQLite path | Needs `HOMELIB_SQLITE_PATH` for v2 eval path |
| 4 LLM eval | ✅ done | ADR-003; evals artifacts | Null result recorded — incumbent kept |
| 5 Interface UI+API | ✅ done | OpenAPI + Streamlit Crossroads | UI `_stcore/health` false-healthy for script errors (mitigated by PYTHONPATH pin + hygiene test; healthcheck still only hits Streamlit core) |
| 6 Ingest dlt | ✅ done | `apps/ingest` tests; seed counts | — |
| 7 Monitoring | ✅ done | Feedback loop + ≥5 charts | Grafana=Postgres; live SQLite feedback may not show in Grafana |
| 8 Containerization | ✅ done | `just ps`; digest pins | Open PR `#18` still changing compose env |
| 9 Reproducibility | ✅ done | `just drill` PASSED @ `d6f9946` (evidence row) | Owner still owns Mon publish/Cloud |
| 10 Best practices | ✅ done | hybrid + rerank + rewrite evaluated | Rewrite rejected on evidence |
| 11 Cloud bonus | ⬜ optional | Owner Mon | Buffer only |
| 12 Extras | 🟡 partial | CHECKLIST | Audiobook / Obsidian buffer |
| Peer ×3 | ⬜ todo | After submit | Owner schedule |

### §B Docker readiness

Most rows ✅ on checklist; **open:** “Reviewer path timed end to end on a clean machine”. Re-verify: `just drill`, compose health, port overrides.

### §C Engineering quality

Mostly ✅; **open:** eval regression gate as blocking CI step; fresh-eyes pass. Re-verify: `just ci`, OpenAPI snapshot guard.

### §D Nice to have

All open (audiobook, Obsidian, DjVu real file, incremental re-ingest, multi-language FTS, homelib-core reuse).

### §E Known gaps

Read `CHECKLIST.md` §E verbatim on `v2` — latent timeout/context hazards, zero-citation-as-success, 7B quality ceiling.

### §F WP00–WP11

| WP | Claim | Re-verify | Residual |
|---|---|---|---|
| WP00–WP10 | ✅ done on `v2` | PRs `#4`–`#15` / `#16` drill evidence; Crossroads doors | Thin surface; not full rotunda |
| WP11 | 🟡 drill ✅ | `docs/evidence.md` drill row | **Owner Mon:** `just publish`, Streamlit Cloud, submit, peer×3 |
| GO/NO-GO | Sun Sep 6 18:00 local demo rehearsal | `docs/evidence.md` addendum §2–§4; `specs/product.md` §12.4 | Live URL check **Mon Sep 7** after owner deploy |
| `v2`→`main` | Not done | Owner after drill (drill already green) | Still unmerged |

**Plan weekday corrections (do not rewrite `docs/plan-v2.md`):** see `docs/evidence.md` addendum — **Sep 7 = Monday submission day**; plan text still mislabels weekdays (verbatim freeze).

### Anchors the next agent must open

- `CHECKLIST.md` §A–§F on **`v2` tip**
- `docs/evidence.md` (+ plan addendum)
- `docs/plan-v2.md` (**verbatim freeze** — corrections only in evidence/CHECKLIST)
- `specs/product.md`
- `docs/reviewer-handoff-v2.md` (may describe an older feature branch tip — reconcile SHAs)

---

## 4. Honest residuals

1. **UI healthcheck** still only curls `_stcore/health` — can be green while the app script fails. PYTHONPATH pin + hygiene test reduce the known false-healthy; healthcheck itself is unchanged.
2. **v2 SQLite endpoints / observatory / eval** need `HOMELIB_SQLITE_PATH` (container default under PR `#18`: `/data/homelib.sqlite`; host path often `data/homelib.sqlite`).
3. **WP11 residual** = owner **Mon** publish / Cloud / submit / peer×3.
4. **`v2`→`main` not done.**
5. **GO/NO-GO calendar** per evidence addendum: Sun Sep 6 18:00 local; **Sep 7 = Monday** submission day (not Sunday as mislabeled in frozen plan).
6. **Open PRs `#17` / `#18`** — product tip `v2` alone does not yet include UI PYTHONPATH or compose SQLite wire until merged.
7. **Lane collision risk** — multiple worktrees/branches; always `git status -sb` + `git worktree list` before editing.

---

## 5. Exact verify commands (next agent must re-run)

```bash
cd /Users/pavloskorodziievskyi/IdeaProjects/homelib

# Step-0
git fetch forgejo
git status -sb
git rev-parse HEAD main v2 'v1-fallback^{}'
tea pr list --state open
git worktree list

# Prefer product tip for checklist reads
git show v2:CHECKLIST.md | sed -n '1,140p'
git show v2:docs/evidence.md | rg -n 'addendum|drill|PYTHONPATH|weekday|GO/NO-GO'

# Stack
just ps
curl -fsS http://127.0.0.1:8010/health
docker exec homelib-ui-1 printenv PYTHONPATH
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8501/_stcore/health
# Confirm Crossroads in a real browser (Playwright/manual): six doors

# Ask + citation + feedback (SQLite path when env set)
curl -fsS --max-time 300 -X POST http://127.0.0.1:8010/v1/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"Who wrote Walden?","rewrite":false,"k":3}' | tee /tmp/ask.json
# extract request_id + block_id, then:
# curl -fsS http://127.0.0.1:8010/v1/blocks/<block_id>
# curl -fsS -X POST http://127.0.0.1:8010/v1/feedback \
#   -H 'Content-Type: application/json' \
#   -d '{"request_id":"<rid>","feedback":"up"}'
# docker exec homelib-api-1 python -c "import sqlite3; ..."

# Seed counts (SQLite)
docker exec homelib-api-1 python -c \
  "import sqlite3; c=sqlite3.connect('/data/homelib.sqlite'); print(c.execute('select (select count(*) from books),(select count(*) from blocks),(select count(*) from chunks),(select count(*) from chunk_embeddings)').fetchone())"

# Grafana provisioned panels (committed JSON) + health
python -c "import json; d=json.load(open('docker/grafana/provisioning/dashboards/json/homelib-overview.json')); print(len(d['panels']), [p['title'] for p in d['panels']])"
curl -fsS http://127.0.0.1:3011/api/health

# Optional host SQLite observatory / eval
# HOMELIB_SQLITE_PATH=$PWD/data/homelib.sqlite APP_MODE=demo just eval-retrieval

# UI fix source (if not on that branch)
git show fix/ui-pythonpath:docker/ui.Dockerfile | rg PYTHONPATH
git show e579808 --stat
```

---

## 6. Out of scope for the next verify agent

- Do not commit/push/merge unless the owner asks.
- Do not `docker compose down -v` / destroy volumes.
- Do not change embedding/Ollama policy.
- Do not rewrite `docs/plan-v2.md` (verbatim freeze).
- Do not put secrets or `.env` passwords into follow-up handoffs.

---

## 7. Coordinator note (this session)

Independent UI-fix re-verify: **runtime PASS**. Source of truth for the Dockerfile/test/evidence trio: **`e579808` / PR `#17`**. Handoff written at path below. No PR created by this coordinator.
