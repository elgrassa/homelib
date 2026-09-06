# Submission — LLM Zoomcamp 2026

## What is submitted

A public GitHub snapshot of this project's `main` branch: a repository a
stranger can clone and run without an account. Development happens on a
private Forgejo instance (branches, PRs, CI, code review); GitHub is a
one-way publication target that receives `main` only — nothing is developed
there, and its Actions are irrelevant (CI is `.forgejo/workflows/` only).

- **Tag / commit graded:** `<filled in at publish time — see the printed SHA>`

## Cloud runtime (showcase URL)

**What Cloud runs:** one Streamlit process from the root `streamlit_app.py`
entrypoint (a thin shim over `apps/ui/app.py`) with `APP_MODE=demo` and a
seed SQLite file — **not** the FastAPI + Ollama Docker Compose stack.
Compose stays the reviewer / self-hosted path (`just up`). Community Cloud
has no sidecar API and no local Ollama, so generation uses an app-owner
cloud LLM via secrets.

| Secret / env | Purpose |
|---|---|
| `APP_MODE` | `demo` |
| `HOMELIB_SQLITE_PATH` | `data/homelib.sqlite` (seeded snapshot path in the repo; inflated once from the committed gzip on cold start) |
| `GROQ_API_KEY` | One-secret form: with `LLM_API_KEY` blank or absent, the LLM client targets Groq |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | Explicit triple; wins over the one-secret form when `LLM_API_KEY` is set |

No secret values are committed anywhere in this repository. Missing or
invalid LLM credentials fail closed: search still works, and an ask returns
an explicit degraded answer rather than an error or a 500.

## Open it as a stranger

Before treating a submission or a redeploy as done, run through this from a
clean checkout:

1. `git clone` the repository into an empty directory.
2. `just ci` — green.
3. `bash scripts/sqlite_only_smoke.sh` — health, a non-degraded ask, and a
   resolving citation, all on the SQLite-only path (no Compose needed).
4. Open the Cloud demo URL.
5. Ask one question.
6. Click a citation and confirm it opens the source passage.

## If something is red at the deadline

Submit anyway, with the gap stated plainly in the README and
`CHECKLIST.md`. A working project with one honestly documented gap scores
better than a project that claims completeness a grader can disprove in one
command — and every criterion is scored independently, so one red area
cannot take the others down with it. `CHECKLIST.md` §E exists for exactly
this: it is already written to be read by someone else.
