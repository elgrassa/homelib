"""WP08 HomelibClient InProcess/Http conformance — specs/client.md named reds."""

from __future__ import annotations

import httpx
import pytest
import respx

from apps.ui.api_client import (
    DEFAULT_TIMEOUT_SECONDS,
    LLM_CALL_TIMEOUT_SECONDS,
    AskResponse,
    HomelibClient,
    HttpClient,
    InProcessClient,
    TokenUsage,
)

BASE_URL = "http://api.conformance.test"

_HEALTH = {
    "status": "ok",
    "db": True,
    "books": 2,
    "chunks": 4,
    "llm": {"provider": "ollama", "model": "test", "reachable": True},
}

_ASK_DEGRADED = AskResponse(
    request_id="req-deg",
    answer="fallback",
    citations=[],
    arm_used="lexical",
    degraded=True,
    latency_ms=12,
    tokens=TokenUsage(prompt=1, completion=2),
)


def _inprocess() -> InProcessClient:
    return InProcessClient(
        health=lambda: dict(_HEALTH),
        ask=lambda query, *, k=5, arm=None, rewrite=False: _ASK_DEGRADED.model_copy(
            update={"answer": query}
        ),
    )


@pytest.fixture(params=["http", "inprocess"])
def client(request: pytest.FixtureRequest) -> HomelibClient:
    if request.param == "inprocess":
        return _inprocess()
    return HttpClient(BASE_URL)


@respx.mock
def test_inprocess_http_conformance_health(client: HomelibClient) -> None:
    if isinstance(client, HttpClient):
        respx.get(f"{BASE_URL}/health").mock(return_value=httpx.Response(200, json=_HEALTH))
    body = client.health()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert "books" in body


@respx.mock
def test_inprocess_http_conformance_ask_degraded_flag(client: HomelibClient) -> None:
    if isinstance(client, HttpClient):
        respx.post(f"{BASE_URL}/v1/ask").mock(
            return_value=httpx.Response(200, json=_ASK_DEGRADED.model_dump())
        )
    response = client.ask("compound interest")
    assert isinstance(response, AskResponse)
    assert response.degraded is True
    assert response.arm_used == "lexical"


def test_http_client_ask_timeout_is_not_ten_seconds() -> None:
    assert LLM_CALL_TIMEOUT_SECONDS > DEFAULT_TIMEOUT_SECONDS
    assert LLM_CALL_TIMEOUT_SECONDS != 10.0
    assert LLM_CALL_TIMEOUT_SECONDS >= 60.0
