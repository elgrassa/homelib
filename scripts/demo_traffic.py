#!/usr/bin/env python3
"""Generate demo query_log traffic for Observatory charts (WP10).

Usage:
  HOMELIB_SQLITE_PATH=data/homelib.sqlite uv run python scripts/demo_traffic.py --n 40
"""

from __future__ import annotations

import argparse
import hashlib
import uuid
from pathlib import Path

from apps.store.sqlite import connect, migrate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=40, help="number of synthetic query_log rows")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: HOMELIB_SQLITE_PATH or data/homelib.sqlite)",
    )
    args = parser.parse_args()
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
