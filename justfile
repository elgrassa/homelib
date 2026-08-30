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

test:
    uv run pytest -q --cov --cov-report=term-missing

# Fast loop: no coverage gate.
test-fast:
    uv run pytest -q --no-cov -x

fmt:
    uv run ruff format .
    uv run ruff check --fix .

# ── stack ───────────────────────────────────────────────────────────────────

# Compose lives in docker/, so Compose treats THAT as the project directory and
# looks for docker/.env — it does not pick up the repo-root .env on its own.
# Without --env-file the stack boots with a blank POSTGRES_PASSWORD and an empty
# LLM_MODEL, warning but not failing. Every compose call therefore passes it.
compose := "docker compose --env-file .env -f docker/docker-compose.yml"

# Refuse to run against a missing .env rather than silently using blank values.
_require-env:
    @test -f .env || { echo "✗ no .env — run: cp .env.example .env"; exit 1; }

up: _require-env
    {{compose}} up -d --build

down: _require-env
    {{compose}} down

logs SERVICE="": _require-env
    {{compose}} logs -f {{SERVICE}}

# One-shot dlt ingestion: corpus snapshot + catalog -> Postgres.
seed: _require-env
    {{compose}} --profile seed run --rm ingest

ps: _require-env
    {{compose}} ps --format '{{{{.Name}} {{{{.Status}}'

# ── evaluation ──────────────────────────────────────────────────────────────

eval: eval-retrieval eval-llm

eval-retrieval:
    uv run python evals/retrieval_eval.py

eval-llm:
    uv run python evals/llm_eval.py

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
    DB=""
    for candidate in "$HOME/CI/Forgejo/data/forgejo.db" \
                     /Volumes/ExternalSSDMini/CI/Forgejo/data/forgejo.db; do
      [[ -f "$candidate" ]] && { DB="$candidate"; break; }
    done
    if [[ -z "$DB" ]]; then
      echo "⚠ Forgejo DB not found — verify CI in the web UI before continuing"; exit 1
    fi
    repo_id=$(sqlite3 "$DB" "SELECT id FROM repository WHERE lower_name='homelib' LIMIT 1")
    if [[ -z "$repo_id" ]]; then
      echo "✗ no 'homelib' repository in the Forgejo DB"; exit 1
    fi
    status=$(sqlite3 "$DB" "SELECT status FROM action_run WHERE repo_id=$repo_id AND commit_sha='$sha' ORDER BY id DESC LIMIT 1")
    case "$status" in
      1) echo "✓ Forgejo CI green for $sha" ;;
      5|6|7) echo "⏳ Forgejo CI still in progress (status=$status)"; exit 1 ;;
      2) echo "✗ Forgejo CI FAILED for $sha"; exit 1 ;;
      "") echo "✗ no CI run recorded for $sha — has it been pushed to forgejo?"; exit 1 ;;
      *) echo "✗ Forgejo CI not green (status=$status)"; exit 1 ;;
    esac
    git push public "$branch:main"
    echo "→ pinned commit: $sha"
