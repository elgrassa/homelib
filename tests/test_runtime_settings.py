"""APP_MODE / demo-timeout config skeleton (WP00).

Behaviour: the process can read edition flags from the environment. This does
not implement FTS5, principals, or a live cloud demo.
"""

from __future__ import annotations

import pytest

from apps.runtime_settings import (
    CLOUD_DEMO_LLM_TIMEOUT_SECONDS,
    COMPOSE_LLM_TIMEOUT_SECONDS,
    AppMode,
    read_app_mode,
    read_llm_max_output_tokens,
    read_llm_timeout_seconds,
)


def test_demo_mode_reads_app_mode_env() -> None:
    assert read_app_mode({"APP_MODE": "demo"}) is AppMode.DEMO


def test_app_mode_defaults_to_selfhosted_when_unset() -> None:
    assert read_app_mode({}) is AppMode.SELFHOSTED


def test_unknown_app_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="APP_MODE"):
        read_app_mode({"APP_MODE": "canary"})


def test_llm_timeout_defaults_to_compose_300() -> None:
    assert read_llm_timeout_seconds({}) == COMPOSE_LLM_TIMEOUT_SECONDS == 300.0


def test_cloud_demo_timeout_constant_is_90() -> None:
    assert CLOUD_DEMO_LLM_TIMEOUT_SECONDS == 90.0


def test_llm_timeout_env_override() -> None:
    assert read_llm_timeout_seconds({"LLM_TIMEOUT_SECONDS": "90"}) == 90.0


def test_llm_max_output_tokens_defaults_to_product_doc() -> None:
    assert read_llm_max_output_tokens({}) == 800
    assert read_llm_max_output_tokens({"LLM_MAX_OUTPUT_TOKENS": "  "}) == 800
    assert read_llm_max_output_tokens({"LLM_MAX_OUTPUT_TOKENS": "400"}) == 400
