"""Demo CLI: `POST /v1/roadmap` against a running homelib API — see specs/api.md.

Usage (via justfile, the canonical entry point):

    just demo-roadmap "stoicism,productivity"

Or directly:

    uv run python scripts/demo_roadmap.py --interests "stoicism,productivity" \\
        [--level beginner] [--goal "..."] [--max-steps 8]

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
_TIMEOUT_SECONDS = 120.0  # roadmap generation may include one LLM repair round trip


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a personalized reading roadmap via POST /v1/roadmap."
    )
    parser.add_argument("--interests", required=True, help="comma-separated list of interests")
    parser.add_argument(
        "--level", choices=["beginner", "intermediate", "advanced"], default="beginner"
    )
    parser.add_argument(
        "--goal", default="build a well-grounded personal reading plan", help="the stated goal"
    )
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("HOMELIB_API_URL", DEFAULT_BASE_URL),
        help="base URL of a running homelib API (default: %(default)s)",
    )
    return parser.parse_args(argv)


def _print_result(interests: list[str], level: str, goal: str, body: dict[str, object]) -> None:
    print(f"Interests: {', '.join(interests)} | Level: {level} | Goal: {goal}")
    print(f"Rationale: {body['rationale']}")
    steps = body.get("steps")
    assert isinstance(steps, list)
    for step in steps:
        prereqs = f" (after steps {step['prerequisites']})" if step.get("prerequisites") else ""
        authors = ", ".join(step.get("authors") or [])
        print(f"  {step['order']}. {step['title']} — {authors} [{step['est_effort']}]{prereqs}")
        print(f"     why: {step['why']}")
    print()
    print(json.dumps(body, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    interests = [i.strip() for i in args.interests.split(",") if i.strip()]

    payload: dict[str, object] = {
        "interests": interests,
        "level": args.level,
        "goal": args.goal,
        "max_steps": args.max_steps,
    }

    url = f"{args.base_url.rstrip('/')}/v1/roadmap"
    try:
        response = httpx.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"error calling {url}: {exc}", file=sys.stderr)
        return 1

    _print_result(interests, args.level, args.goal, response.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
