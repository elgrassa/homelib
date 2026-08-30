"""Demo CLI: `POST /v1/ask` against a running homelib API — see specs/api.md.

Usage (via justfile, the canonical entry point):

    just demo-ask "how did henry ford organize the assembly line?"

Or directly:

    uv run python scripts/demo_ask.py --query "..." [--k 5] [--arm hybrid_rerank]

Requires a running `apps.api.main:app` (e.g. `just up`) — this script is a
manual/CI verification aid, not part of the `pytest` suite (no network calls
happen when this module is merely imported).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
_TIMEOUT_SECONDS = 60.0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask homelib a question via POST /v1/ask.")
    parser.add_argument("--query", required=True, help="the question to ask")
    parser.add_argument("--k", type=int, default=5, help="number of chunks to retrieve")
    parser.add_argument(
        "--arm",
        choices=["lexical", "vector", "hybrid", "hybrid_rerank"],
        default=None,
        help="retrieval arm to force; omit to use the production default",
    )
    parser.add_argument("--no-rewrite", action="store_true", help="skip the LLM query-rewrite step")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("HOMELIB_API_URL", DEFAULT_BASE_URL),
        help="base URL of a running homelib API (default: %(default)s)",
    )
    return parser.parse_args(argv)


def _print_result(query: str, body: dict[str, object]) -> None:
    print(f"Q: {query}")
    print(f"A: {body['answer']}")
    print(
        f"arm_used={body['arm_used']} degraded={body['degraded']} latency_ms={body['latency_ms']}"
    )
    print("Citations:")
    citations = body.get("citations")
    assert isinstance(citations, list)
    for citation in citations:
        page = f" p.{citation['page']}" if citation.get("page") is not None else ""
        section = " / ".join(citation.get("section_path") or [])
        print(f"  - {citation['book_title']} ({section}{page}): {citation['quote']!r}")
    print()
    print(json.dumps(body, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    payload: dict[str, object] = {
        "query": args.query,
        "k": args.k,
        "rewrite": not args.no_rewrite,
    }
    if args.arm is not None:
        payload["arm"] = args.arm

    url = f"{args.base_url.rstrip('/')}/v1/ask"
    try:
        response = httpx.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"error calling {url}: {exc}", file=sys.stderr)
        return 1

    _print_result(args.query, response.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
