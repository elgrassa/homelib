#!/usr/bin/env python3
"""Score recent unjudged /v1/ask traffic with the LLM-as-judge (C6).

Usage:
  HOMELIB_SQLITE_PATH=data/homelib.sqlite uv run python scripts/judge_recent.py --n 50

Judges only rows with a matching `answer_log` entry, which exists only when
the API ran with `HOMELIB_LOG_ANSWERS=1` (off by default — see
specs/monitoring.md's privacy note). Writes `query_log.relevance` /
`judge_model` back; never re-judges an already-judged row (see
`apps.store.judge_ops.judge_recent_rows`, which holds the actual logic so it
can be unit-tested with a fake LLM under `apps/store/tests/`).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from apps.store.judge_ops import judge_recent_rows
from apps.store.sqlite import connect, migrate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=50, help="max unjudged rows to score")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: HOMELIB_SQLITE_PATH or data/homelib.sqlite)",
    )
    args = parser.parse_args()

    path = args.db or Path(os.environ.get("HOMELIB_SQLITE_PATH", "data/homelib.sqlite"))
    conn = connect(path)
    migrate(conn)
    judged = judge_recent_rows(conn, n=args.n)
    print(f"judged {len(judged)} of up to {args.n} unjudged rows in {path}")
    conn.close()


if __name__ == "__main__":
    main()
