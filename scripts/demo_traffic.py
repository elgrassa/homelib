#!/usr/bin/env python3
"""Generate demo query_log traffic for Observatory charts (WP10).

Usage:
  HOMELIB_SQLITE_PATH=data/homelib.sqlite uv run python scripts/demo_traffic.py --n 40

  # C4b (specs/monitoring.md "Demo answer cache"): fire each of a small set of
  # real questions once against a RUNNING API in APP_MODE=demo, so its
  # answer_cache is warm before reviewers/visitors arrive. Requires a live
  # server (this hits the network), unlike the synthetic --n path above.
  uv run python scripts/demo_traffic.py --warm-cache --api-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import hashlib
import uuid
from pathlib import Path

from apps.store.sqlite import connect, migrate

# A small, representative set of demo questions — not the full eval set,
# just enough that a Community Cloud visitor's first few asks are usually
# already warm. Kept short deliberately: --warm-cache makes one real LLM
# call per entry.
_WARM_CACHE_QUESTIONS = (
    "What is the division of labour?",
    "How does specialization increase productivity?",
    "What did Adam Smith say about markets?",
)


def _warm_cache(api_url: str) -> None:
    import httpx

    base = api_url.rstrip("/")
    with httpx.Client(timeout=300.0) as client:
        for question in _WARM_CACHE_QUESTIONS:
            try:
                resp = client.post(f"{base}/v1/ask", json={"query": question})
                resp.raise_for_status()
                body = resp.json()
                print(f"warmed {question!r} (cache_hit={body.get('cache_hit')})")
            except httpx.HTTPError as exc:
                print(f"failed to warm {question!r}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=40, help="number of synthetic query_log rows")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: HOMELIB_SQLITE_PATH or data/homelib.sqlite)",
    )
    parser.add_argument(
        "--warm-cache",
        action="store_true",
        help="ask each of a small fixed question set once against a running API "
        "(APP_MODE=demo) instead of inserting synthetic query_log rows",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL for --warm-cache (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    if args.warm_cache:
        _warm_cache(args.api_url)
        return

    import os

    path = args.db or Path(os.environ.get("HOMELIB_SQLITE_PATH", "data/homelib.sqlite"))
    conn = connect(path)
    migrate(conn)
    arms = ("lexical", "vector", "hybrid", "hybrid_rerank")
    with conn:
        for i in range(args.n):
            q = f"demo traffic question {i}"
            prefix = hashlib.sha256(q.encode()).hexdigest()[:16]
            conn.execute(
                "INSERT INTO query_log ("
                "request_id, ts, latency_ms, arm, k, rerank, rewrite, model, "
                "tokens_prompt, tokens_completion, query_sha256_prefix, degraded, feedback"
                ") VALUES (?, datetime('now', ?), ?, ?, 5, ?, 0, 'demo', ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    f"-{i} minutes",
                    80 + (i % 40) * 7,
                    arms[i % len(arms)],
                    1 if "rerank" in arms[i % len(arms)] else 0,
                    100 + i,
                    40 + (i % 10),
                    prefix,
                    1 if i % 7 == 0 else 0,
                    "up" if i % 3 else ("down" if i % 5 == 0 else None),
                ),
            )
    print(f"inserted {args.n} query_log rows into {path}")
    conn.close()


if __name__ == "__main__":
    main()
