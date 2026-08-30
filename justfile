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

up:
    docker compose -f docker/docker-compose.yml up -d --build

down:
    docker compose -f docker/docker-compose.yml down

logs SERVICE="":
    docker compose -f docker/docker-compose.yml logs -f {{SERVICE}}

# One-shot dlt ingestion: corpus snapshot + catalog -> Postgres.
seed:
    docker compose -f docker/docker-compose.yml --profile seed run --rm ingest

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
