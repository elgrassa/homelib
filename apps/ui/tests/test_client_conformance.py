"""WP08 HomelibClient InProcess/Http conformance — specs/client.md named reds."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from apps.ui.api_client import (
    DEFAULT_TIMEOUT_SECONDS,
    DEMO_SESSION_HEADER,
    LLM_CALL_TIMEOUT_SECONDS,
    ApiClient,
    ApiClientError,
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


# ── H3: demo principal must travel with every call, on both clients ─────────
#
# The API mints a fresh anonymous principal for any header-less request in
# APP_MODE=demo, so a client that never sent `X-Demo-Session` saw an empty
# Coffee Table after every Streamlit rerun. These pin the header on the
# playlist/progress calls for HttpClient (respx) AND InProcessClient wrapping
# an ApiClient over httpx.MockTransport — the production demo wiring shape.

_PLAYLIST = {"playlist_id": "p1", "items": []}


def _recording_transport(seen: list[tuple[str, str, dict[str, str]]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, dict(request.headers)))
        if request.url.path == "/v1/demo/session":
            return httpx.Response(200, json={"demo_session_id": "sess-minted", "principal_id": "p"})
        return httpx.Response(200, json=_PLAYLIST)

    return httpx.MockTransport(handler)


@pytest.fixture(params=["http", "inprocess"])
def demo_client(request: pytest.FixtureRequest) -> tuple[HomelibClient, list[Any]]:
    seen: list[tuple[str, str, dict[str, str]]] = []
    transport = _recording_transport(seen)
    api = ApiClient(BASE_URL, http_client=httpx.Client(transport=transport))
    if request.param == "inprocess":
        return InProcessClient(delegate=api), seen
    http = HttpClient(BASE_URL, http_client=httpx.Client(transport=transport))
    return http, seen


def test_demo_session_header_sent_on_playlist_and_progress_calls(
    demo_client: tuple[HomelibClient, list[Any]],
) -> None:
    client, seen = demo_client
    client.set_demo_session("sess-1")
    client.get_playlist()
    client.add_playlist_item("book-1")
    client.save_progress("book-1", kind="read", char_offset=10)
    client.get_progress(kind="read")
    paths = [(m, p.split("?", 1)[0]) for m, p, _ in seen]
    assert paths == [
        ("GET", "/v1/playlists/current"),
        ("POST", "/v1/playlists/current/items"),
        ("POST", "/v1/progress"),
        ("GET", "/v1/progress"),
    ]
    assert all(h.get(DEMO_SESSION_HEADER.lower()) == "sess-1" for _, _, h in seen)


def test_create_demo_session_returns_id_on_both_clients(
    demo_client: tuple[HomelibClient, list[Any]],
) -> None:
    client, seen = demo_client
    assert client.create_demo_session() == "sess-minted"
    assert seen[-1][:2] == ("POST", "/v1/demo/session")
    client.get_playlist()
    assert seen[-1][2].get(DEMO_SESSION_HEADER.lower()) == "sess-minted"


def test_request_retries_once_with_fresh_session_on_401_in_demo() -> None:
    """Server forgot our session (restart/TTL): mint once, resend once."""
    calls: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        header = request.headers.get(DEMO_SESSION_HEADER.lower())
        calls.append((request.url.path, header))
        if request.url.path == "/v1/demo/session":
            return httpx.Response(200, json={"demo_session_id": "fresh", "principal_id": "p"})
        if header == "stale":
            return httpx.Response(401, json={"detail": "unknown demo session"})
        return httpx.Response(200, json=_PLAYLIST)

    api = ApiClient(BASE_URL, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    api.set_demo_session("stale")
    assert api.get_playlist() == _PLAYLIST
    assert calls == [
        ("/v1/playlists/current", "stale"),
        ("/v1/demo/session", None),
        ("/v1/playlists/current", "fresh"),
    ]
    assert api.demo_session_id == "fresh"


def test_request_does_not_remint_on_401_in_selfhosted() -> None:
    """No demo session set (selfhosted): a 401 is an error, not a remint trigger."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(401, json={"detail": "nope"})

    api = ApiClient(BASE_URL, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ApiClientError) as excinfo:
        api.get_playlist()
    assert excinfo.value.status_code == 401
    assert calls == ["/v1/playlists/current"]


def test_401_retry_happens_at_most_once() -> None:
    """A server that keeps rejecting even the fresh session must not loop."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v1/demo/session":
            return httpx.Response(200, json={"demo_session_id": "fresh", "principal_id": "p"})
        return httpx.Response(401, json={"detail": "still no"})

    api = ApiClient(BASE_URL, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    api.set_demo_session("stale")
    with pytest.raises(ApiClientError):
        api.get_playlist()
    assert calls == ["/v1/playlists/current", "/v1/demo/session", "/v1/playlists/current"]


def test_create_demo_session_raises_on_malformed_response() -> None:
    """A 200 without `demo_session_id` is a broken server, not a session."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"principal_id": "p"})

    api = ApiClient(BASE_URL, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ApiClientError) as excinfo:
        api.create_demo_session()
    assert excinfo.value.status_code == 502
    assert api.demo_session_id is None
