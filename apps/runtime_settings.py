"""Edition / runtime flags from the environment.

`APP_MODE` and timeout defaults. When `HOMELIB_SQLITE_PATH` is set, the API
wires health/books/ask logging onto the SQLite store (see apps/api/sqlite_deps).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum

# Compose / reviewer CPU-Ollama (v1 commit 467b6bc). Product §7.2's 90s is the
# cloud-demo default, not the in-VM default.
COMPOSE_LLM_TIMEOUT_SECONDS = 300.0
CLOUD_DEMO_LLM_TIMEOUT_SECONDS = 90.0
DEFAULT_LLM_MAX_OUTPUT_TOKENS = 800


class AppMode(StrEnum):
    DEMO = "demo"
    SELFHOSTED = "selfhosted"


def read_app_mode(environ: Mapping[str, str] | None = None) -> AppMode:
    env = os.environ if environ is None else environ
    raw = env.get("APP_MODE", AppMode.SELFHOSTED.value).strip().lower()
    try:
        return AppMode(raw)
    except ValueError as exc:
        allowed = ", ".join(repr(m.value) for m in AppMode)
        raise ValueError(f"APP_MODE must be one of {allowed}; got {raw!r}") from exc


def read_llm_timeout_seconds(environ: Mapping[str, str] | None = None) -> float:
    env = os.environ if environ is None else environ
    raw = env.get("LLM_TIMEOUT_SECONDS")
    if raw is None or raw.strip() == "":
        return COMPOSE_LLM_TIMEOUT_SECONDS
    return float(raw)


def read_llm_max_output_tokens(environ: Mapping[str, str] | None = None) -> int:
    env = os.environ if environ is None else environ
    raw = env.get("LLM_MAX_OUTPUT_TOKENS")
    if raw is None or raw.strip() == "":
        return DEFAULT_LLM_MAX_OUTPUT_TOKENS
    return int(raw)
