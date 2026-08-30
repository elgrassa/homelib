#!/usr/bin/env bash
# Cold-clone drill — the only honest test of "reproducible".
#
# Clones this repo into a directory with no prior state, brings the whole stack
# up from nothing but .env.example, seeds it, asks a real question, and checks
# the answer carries a citation that resolves. Exits non-zero the moment any
# step fails, so it cannot pass by being ignored.
#
# Usage: bash scripts/cold_clone_drill.sh [target-dir]
#
# The point is to catch what a developer's machine hides: an uncommitted file,
# a model that only exists in a local cache, a port assumed free, a step that
# lives in someone's shell history instead of the README.

set -euo pipefail

TARGET="${1:-/tmp/homelib-drill}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="homelib_drill"
COMPOSE=""   # set after the clone exists

# Ports deliberately offset from the defaults: the drill must not collide with,
# or silently reuse, a stack the developer already has running. Reusing one
# would let the drill "pass" against containers the clone never built.
export API_PORT="${API_PORT:-18000}"
export UI_PORT="${UI_PORT:-18501}"
export GRAFANA_PORT="${GRAFANA_PORT:-13001}"
export POSTGRES_PORT="${POSTGRES_PORT:-15432}"
export OLLAMA_PORT="${OLLAMA_PORT:-11534}"

step()  { printf '\n=== %s ===\n' "$1"; }
fail()  { printf '\n✗ DRILL FAILED: %s\n' "$1" >&2; exit 1; }

cleanup() {
    if [ -n "$COMPOSE" ]; then
        printf '\n=== tearing down ===\n'
        # shellcheck disable=SC2086
        $COMPOSE down -v --remove-orphans >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

step "clone into a directory with no prior state"
rm -rf "$TARGET"
git clone --quiet "$REPO_ROOT" "$TARGET" || fail "clone failed"
cd "$TARGET"
PINNED_SHA="$(git rev-parse HEAD)"
echo "cloned at $PINNED_SHA"

step "configure from .env.example only"
[ -f .env.example ] || fail ".env.example is not committed"
cp .env.example .env
{
    echo "API_PORT=$API_PORT"
    echo "UI_PORT=$UI_PORT"
    echo "GRAFANA_PORT=$GRAFANA_PORT"
    echo "POSTGRES_PORT=$POSTGRES_PORT"
    echo "OLLAMA_PORT=$OLLAMA_PORT"
} >> .env
COMPOSE="docker compose --env-file .env -f docker/docker-compose.yml -p $PROJECT"

step "committed data is present without any download"
[ -f data/corpus_snapshot.jsonl.gz ] || fail "corpus snapshot is not committed"
[ -f data/catalog.jsonl ]            || fail "catalog is not committed"
echo "snapshot sha256: $(shasum -a 256 data/corpus_snapshot.jsonl.gz | cut -d' ' -f1)"

step "bring the stack up"
$COMPOSE up -d --build || fail "compose up failed"

step "wait for every service to report healthy"
deadline=$((SECONDS + 600))
while true; do
    unhealthy="$($COMPOSE ps --format '{{.Name}} {{.Status}}' | grep -v 'healthy' || true)"
    [ -z "$unhealthy" ] && break
    [ "$SECONDS" -ge "$deadline" ] && fail "not all services healthy within 10 min:\n$unhealthy"
    sleep 5
done
$COMPOSE ps --format '{{.Name}} {{.Status}}'

step "seed the database"
$COMPOSE --profile seed run --rm ingest || fail "ingestion failed"

step "ask a real question and require a resolvable citation"
answer_json="$(curl -fsS -X POST "http://localhost:$API_PORT/v1/ask" \
    -H 'content-type: application/json' \
    -d '{"query":"What does the corpus say about the division of labour?"}')" \
    || fail "/v1/ask did not respond"

python3 - "$answer_json" "$API_PORT" <<'PY' || exit 1
import json, sys, urllib.request

payload, port = json.loads(sys.argv[1]), sys.argv[2]

if not payload.get("answer", "").strip():
    sys.exit("✗ empty answer")
citations = payload.get("citations") or []
if not citations:
    sys.exit("✗ answer carried no citations — an uncited answer is the failure this drill exists to catch")

# A citation is only worth anything if it resolves back to a real block.
c = citations[0]
url = f"http://localhost:{port}/v1/blocks/{c['chunk_id']}"
try:
    with urllib.request.urlopen(url, timeout=30) as r:
        json.load(r)
except Exception as exc:                                    # noqa: BLE001
    sys.exit(f"✗ first citation did not resolve via {url}: {exc}")

print(f"✓ answer with {len(citations)} citation(s); first resolves: "
      f"{c.get('book_title')} · {'/'.join(c.get('section_path') or []) or '(no section)'}")
print(f"  degraded={payload.get('degraded')} arm={payload.get('arm_used')}")
if payload.get("degraded"):
    sys.exit("✗ answer was served from a degraded path — the drill requires a healthy answer")
PY

step "monitoring recorded that request"
logged="$(curl -fsS -u "admin:$(grep '^GRAFANA_PASSWORD=' .env | cut -d= -f2)" \
    "http://localhost:$GRAFANA_PORT/api/dashboards/uid/homelib-overview" \
    | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["dashboard"]["panels"]))')" \
    || fail "Grafana dashboard not provisioned"
[ "$logged" -ge 5 ] || fail "dashboard has $logged panels, expected at least 5"
echo "dashboard provisioned with $logged panels"

printf '\n✓ DRILL PASSED — pinned commit %s\n' "$PINNED_SHA"
