#!/usr/bin/env bash
# SQLite-only smoke: proves H1 (cited, non-degraded answer with no Postgres)
# and H3 (demo principal persists across calls when the header travels).
#
# Not the drill. This runs the API in-process against an already-seeded
# SQLite file with DATABASE_URL unset and APP_MODE=demo — the Streamlit
# Community Cloud shape — and needs an LLM endpoint (LLM_BASE_URL; defaults
# to a host Ollama). Usage:
#   HOMELIB_SQLITE_PATH=data/homelib.sqlite bash scripts/sqlite_only_smoke.sh
set -euo pipefail

DB="${HOMELIB_SQLITE_PATH:-data/homelib.sqlite}"
PORT="${SMOKE_PORT:-18011}"
export LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:11434/v1}"
export LLM_MODEL="${LLM_MODEL:-qwen2.5:7b-instruct}"
export LLM_API_KEY="${LLM_API_KEY:-ollama}"
export LLM_TIMEOUT_SECONDS="${LLM_TIMEOUT_SECONDS:-300}"
export HOMELIB_SQLITE_PATH="$DB"
export APP_MODE=demo
unset DATABASE_URL

[ -f "$DB" ] || { echo "✗ $DB missing — seed it first (just seed-sqlite / seed-sqlite-local)"; exit 1; }

uv run --frozen uvicorn apps.api.main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
    curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
    sleep 1
done

python3 - "$PORT" <<'PY'
import json, sys, urllib.request

port = sys.argv[1]
base = f"http://127.0.0.1:{port}"

def call(method, path, body=None, headers=None, timeout=330):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")

status, health = call("GET", "/health")
print("health:", json.dumps(health))
assert health["db"] is True and health["books"] == 18 and health["chunks"] == 9168, health
assert health["status"] == "ok", "health not ok (LLM unreachable or store empty?)"

# H1 — with DATABASE_URL unset, the answer path must still fill book titles.
status, ask = call("POST", "/v1/ask", {"query": "Who wrote Walden?", "rewrite": False, "k": 3})
print("ask:", json.dumps({k: ask.get(k) for k in ("degraded", "arm_used", "latency_ms")}),
      "citations:", len(ask.get("citations", [])), "answer:", (ask.get("answer") or "")[:80])
assert status == 200, ask
assert ask["degraded"] is False, "answer degraded — H1 regression or LLM down"
assert ask["citations"], "no citations"
cite = ask["citations"][0]
assert cite["book_title"], "citation has no server-side title (H1)"
status, block = call("GET", f"/v1/blocks/{cite['block_id']}")
assert status == 200 and block["book_id"] == cite["book_id"], (status, block)
print(f"citation resolves: {cite['book_title']!r} block {cite['block_id']}")

# H3 — a minted session is one principal; header-less is a fresh one each time.
status, minted = call("POST", "/v1/demo/session")
hdr = {"X-Demo-Session": minted["demo_session_id"]}
status, resources = call("GET", "/v1/resources", headers=hdr)
book_id = resources["items"][0]["id"]
status, added = call("POST", "/v1/playlists/current/items",
                     {"resource_id": book_id, "origin": "manual_shelf"}, headers=hdr)
assert status == 200, added
status, again = call("GET", "/v1/playlists/current", headers=hdr)
assert len(again["items"]) == 1, again
status, anon = call("GET", "/v1/playlists/current")
assert anon["items"] == [], anon
print("coffee table: 1 item with header, 0 without — demo principal persists")
print("✓ SQLITE-ONLY SMOKE PASSED")
PY
