# homelib — canonical entry points. `just` with no args lists everything.
set shell := ["bash", "-uc"]

default:
    @just --list

# ── local gates ─────────────────────────────────────────────────────────────

# Full local gate: what CI runs. Green here == green there.
ci: lint typecheck test

lint:
    uv run ruff check .
    uv run ruff format --check .

typecheck:
    uv run mypy

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

# ── publish ─────────────────────────────────────────────────────────────────

# Push the public submission copy ONLY after Forgejo CI is green for this branch.
publish:
    #!/usr/bin/env bash
    set -euo pipefail
    branch=$(git rev-parse --abbrev-ref HEAD)
    if ! git remote get-url public >/dev/null 2>&1; then
      echo "✗ no 'public' remote configured (see docs/submission.md)"; exit 1
    fi
    DB=/Volumes/ExternalSSDMini/CI/Forgejo/data/forgejo.db
    if [[ -f "$DB" ]]; then
      status=$(sqlite3 "$DB" "SELECT status FROM action_run WHERE ref='refs/heads/$branch' ORDER BY id DESC LIMIT 1" 2>/dev/null || echo "")
      case "$status" in
        3) echo "✓ Forgejo CI green for $branch" ;;
        1|2) echo "⏳ Forgejo CI still running (status=$status)"; exit 1 ;;
        *) echo "✗ Forgejo CI not green (status=${status:-none})"; exit 1 ;;
      esac
    else
      echo "⚠ Forgejo DB not readable — verify CI in the web UI before continuing"; exit 1
    fi
    git push public "$branch:main"
    echo "→ pinned commit: $(git rev-parse HEAD)"
