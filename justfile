# homelib — canonical entry points. `just` with no args lists everything.
set shell := ["bash", "-uc"]

default:
    @just --list

# ── local gates ─────────────────────────────────────────────────────────────

# Full local gate: what CI runs. Green here == green there.
ci: lint typecheck secrets test

lint:
    uv run ruff check .
    uv run ruff format --check .

typecheck:
    uv run mypy

# Scan the whole HISTORY, not just the working tree: a secret that was
# committed and then deleted is still in the repo, and this one is going
# public. Skips with a loud warning rather than failing when gitleaks is not
# installed, so a contributor without it is told rather than silently passing.
secrets:
    #!/usr/bin/env bash
    set -uo pipefail
    if ! command -v gitleaks >/dev/null 2>&1; then
      echo "⚠ gitleaks not installed — history NOT scanned (brew install gitleaks)"
      exit 0
    fi
    gitleaks git --config .gitleaks.toml --redact --no-banner .

# pytest basetemps go to a repo-local, gitignored dir instead of the OS temp
# dir: a killed session (agent loop, CI SIGKILL) leaves its basetemp locked and
# pytest never reclaims it. Repo-local means `just clean` and the CI teardown
# can. The dir MUST exist first or tempfile silently falls back to /tmp.
test:
    mkdir -p .pytest-tmp && TMPDIR="$PWD/.pytest-tmp" uv run pytest -q --cov --cov-report=term-missing

# Wipe local pytest scratch (killed-session basetemps accumulate here by design).
clean:
    rm -rf .pytest-tmp .pytest_cache

# Fast loop: no coverage gate.
test-fast:
    mkdir -p .pytest-tmp && TMPDIR="$PWD/.pytest-tmp" uv run pytest -q --no-cov -x

# Local code-graph refresh for inspection. Never commit the output — branches
# that touch graphify-out/ hard-fail graph-guard; graph-refresh owns the
# committed graph on main after merge (see the shared CI template this project adapts).
[private]
graph:
    command -v graphify >/dev/null || { echo "graphify not installed (owner-only tooling)"; exit 0; }
    PYTHONHASHSEED=0 graphify update .

# What the pre-push hook runs. Everything cheap, nothing slow: the integration
# tests, the embedding-model loads and the coverage floor are the PR's job.
# Keep this under a minute — a slow pre-push gate teaches people --no-verify.
gate-fast:
    bash .githooks/pre-push

# Opt-in: point git at .githooks so the pre-push gate runs. Undo with
# `git config --unset core.hooksPath`.
hooks:
    git config core.hooksPath .githooks
    @echo "✓ pre-push gate installed (undo: git config --unset core.hooksPath)"

fmt:
    uv run ruff format .
    uv run ruff check --fix .

# ── stack ───────────────────────────────────────────────────────────────────

# Compose lives in docker/, so Compose treats THAT as the project directory and
# looks for docker/.env — it does not pick up the repo-root .env on its own.
# Without --env-file the stack boots with a blank POSTGRES_PASSWORD and an empty
# LLM_MODEL, warning but not failing. Every compose call therefore passes it.
# `-p homelib` is not decoration. Compose derives the project name from the
# directory holding the compose file, which here is `docker/` — so the stack
# comes up as project "docker", named after the most generic directory name in
# software. Two consequences, both observed: a Docker restart brought the stack
# back under a different project than the one that had been seeded, pointing at
# a fresh EMPTY volume while `homelib_pgdata` sat there full; and any other
# project on this machine with a `docker/` directory computes the same names.
# The same class of bug as the fixed test-database name — a constant, shared
# identifier on a shared host.
compose := "docker compose -p homelib --env-file .env -f docker/docker-compose.yml"

# Refuse to run against a missing .env rather than silently using blank values.
_require-env:
    @test -f .env || { echo "✗ no .env — run: cp .env.example .env"; exit 1; }

up: _require-env
    {{compose}} up -d --build

down: _require-env
    {{compose}} down

logs SERVICE="": _require-env
    {{compose}} logs -f {{SERVICE}}

# One-shot dlt ingestion: corpus snapshot + catalog -> Postgres (v1 store,
# Grafana path). The API reads SQLite (ADR-004) — run `just seed-sqlite` too.
# `--build`: the ingest service sits behind the `seed` profile, so `just up`
# (compose up --build) never builds it. Without --build, `run` happily reuses
# whatever `homelib-ingest` image exists — days old, missing modules — and the
# drill found exactly that (a 5-day-old image without sqlite_pipeline).
seed: _require-env
    {{compose}} --profile seed run --rm --build ingest

# One-shot dlt ingestion into the SQLite file the API actually opens
# (/data/homelib.sqlite in the container == data/homelib.sqlite on the host).
# A deliberately SEPARATE one-shot, not `&&` in the image CMD: each seed embeds
# 9,168 chunks, and a cold clone that skips Postgres should not pay twice.
seed-sqlite: _require-env
    {{compose}} --profile seed run --rm --build ingest python -m apps.ingest.sqlite_pipeline

# Dev convenience only (needs the host venv). A cold clone uses `just seed-sqlite`.
seed-sqlite-local:
    uv run python -m apps.ingest.sqlite_pipeline --db data/homelib.sqlite

ps: _require-env
    {{compose}} ps --format '{{{{.Name}} {{{{.Status}}'

# ── evaluation ──────────────────────────────────────────────────────────────

eval: eval-retrieval eval-llm

eval-retrieval:
    uv run python evals/retrieval_eval.py

eval-llm:
    uv run python evals/llm_eval.py

# Compare committed winner floors in evals/eval-baseline.json to the numbers
# already published in evals/results/retrieval.md + llm_eval.md — no bake-off.
# Named-column parse (not positional regex): hit-rate/MRR from retrieval.md,
# production faithfulness from llm_eval.md. Wired into Forgejo CI as an
# archive-regression step (not a live bake-off). Optional fresh metrics:
# `just eval-gate --from-run path/to/metrics.json`.
eval-gate *ARGS:
    uv run python -m evals.gate {{ARGS}}

# RRF fusion-constant sweep: hybrid arm only, k in {1,10,60,100,200}, appends
# (replaces on re-run) the "RRF k sweep" table in evals/results/retrieval.md.
eval-rrf-k:
    uv run python evals/retrieval_eval.py --rrf-k 1 --rrf-k 10 --rrf-k 60 --rrf-k 100 --rrf-k 200

# Chunking experiment: target_chars/overlap in {600/100, 1200/200, 2000/400},
# book-level hit-rate/MRR@5 (fresh in-memory lexical+vector indices per config)
# -> evals/results/chunking.md. --books 6 matches the documented, measured run
# (evals/results/chunking.md, ~8 min): embedding all 18 books across three
# configs is the actual bottleneck, not question count -- see
# evals/chunk_sweep.py's docstring before widening this to the full corpus.
eval-chunking:
    uv run python evals/chunk_sweep.py --books 6 --questions 235

# ── demos (used as WP verify commands) ──────────────────────────────────────

demo-ask Q:
    uv run python scripts/demo_ask.py --query {{quote(Q)}}

demo-roadmap INTERESTS:
    uv run python scripts/demo_roadmap.py --interests {{quote(INTERESTS)}}

# ── drill ───────────────────────────────────────────────────────────────────

# The reproducibility gate: clone into an empty dir, up, seed, ask, verify.
# Runs on offset ports so it can never pass by reusing a stack you already have.
drill TARGET="/tmp/homelib-drill":
    bash scripts/cold_clone_drill.sh {{TARGET}}

# ── publish ─────────────────────────────────────────────────────────────────

# Push the public submission copy ONLY after Forgejo CI is green for THIS commit.
#
# The gate reads Forgejo's SQLite directly because this instance exposes no
# logs API. Three things it is deliberately strict about:
#
#   * It keys on commit_sha, not branch. A branch-keyed check goes green on
#     the last commit CI happened to see, which is not necessarily the commit
#     about to be published.
#   * It scopes to this repository. `feat/scaffold` is not a unique ref name
#     on an instance hosting many repos.
#   * Status 1 is SUCCESS in Forgejo's enum (1 success, 2 failure, 3 cancelled,
#     4 skipped, 5 waiting, 6 running, 7 blocked). Verified against the live
#     table: 8.5k rows at 1, and every job under a status=1 run is itself 1.
#
# The Forgejo database path is owner-machine-specific — set HOMELIB_FORGEJO_DB
# to it locally, or verify CI green in the web UI and skip this recipe.
[private]
publish:
    #!/usr/bin/env bash
    set -euo pipefail
    branch=$(git rev-parse --abbrev-ref HEAD)
    sha=$(git rev-parse HEAD)
    if ! git remote get-url public >/dev/null 2>&1; then
      echo "✗ no 'public' remote configured (see docs/submission.md)"; exit 1
    fi
    if [[ -n "$(git status --porcelain)" ]]; then
      echo "✗ working tree is dirty — publish exactly what CI verified"; exit 1
    fi
    if ! git ls-remote --exit-code forgejo "$sha" >/dev/null 2>&1 \
       && [[ "$(git rev-parse "forgejo/$branch" 2>/dev/null || echo none)" != "$sha" ]]; then
      echo "✗ $sha is not on forgejo/$branch — push there first, CI runs on that"; exit 1
    fi
    DB="${HOMELIB_FORGEJO_DB:-}"
    if [[ -z "$DB" ]]; then
      echo "⚠ Forgejo DB not found — set HOMELIB_FORGEJO_DB or verify CI in the web UI before continuing"; exit 1
    fi
    repo_id=$(sqlite3 "$DB" "SELECT id FROM repository WHERE lower_name='homelib' LIMIT 1")
    if [[ -z "$repo_id" ]]; then
      echo "✗ no 'homelib' repository in the Forgejo DB"; exit 1
    fi
    status=$(sqlite3 "$DB" "SELECT status FROM action_run WHERE repo_id=$repo_id AND commit_sha='$sha' ORDER BY id DESC LIMIT 1")
    # graph-refresh commits touch only graphify-out/ and often have no action_run;
    # allow the first-parent's green CI when this tip is graph-only.
    if [[ -z "$status" ]]; then
      parent=$(git rev-parse "${sha}^" 2>/dev/null || true)
      if [[ -n "$parent" ]]; then
        only_graph=$(git diff --name-only "$parent" "$sha" | awk '!/^graphify-out\//{n++} END{print n+0}')
        if [[ "$only_graph" -eq 0 ]]; then
          status=$(sqlite3 "$DB" "SELECT status FROM action_run WHERE repo_id=$repo_id AND commit_sha='$parent' ORDER BY id DESC LIMIT 1")
          if [[ -n "$status" ]]; then
            echo "ℹ tip $sha has no CI run (graph-refresh only); using parent ${parent:0:8}"
            sha_for_msg="$parent"
          fi
        fi
      fi
    fi
    case "$status" in
      1) echo "✓ Forgejo CI green for ${sha_for_msg:-$sha}" ;;
      5|6|7) echo "⏳ Forgejo CI still in progress (status=$status)"; exit 1 ;;
      2) echo "✗ Forgejo CI FAILED for ${sha_for_msg:-$sha}"; exit 1 ;;
      "") echo "✗ no CI run recorded for $sha — has it been pushed to forgejo?"; exit 1 ;;
      *) echo "✗ Forgejo CI not green (status=$status)"; exit 1 ;;
    esac
    git push public "$branch:main"
    echo "→ pinned commit: $sha"

# Build the committed Cloud seed from a seeded data/homelib.sqlite: checkpoint
# the WAL so the copy is self-contained, then gzip deterministically (-n drops
# the timestamp so an unchanged seed produces an identical artefact).
[private]
seed-gz:
    sqlite3 data/homelib.sqlite "PRAGMA wal_checkpoint(TRUNCATE);"
    mkdir -p data/seed
    gzip -9 -n -c data/homelib.sqlite > data/seed/homelib.sqlite.gz
    ls -la data/seed/homelib.sqlite.gz
