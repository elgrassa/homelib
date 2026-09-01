"""Behavioural tests for apps/ui/api_client.py against a stubbed transport.

Every ApiClient method is exercised for its success path; representative
error paths (404, timeout, connection error, non-JSON error body) are
covered via the methods where they are most meaningful per specs/api.md.
No real network call is ever made — respx intercepts httpx at the transport
layer.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from apps.ui.api_client import (
    DEFAULT_TIMEOUT_SECONDS,
    LLM_CALL_TIMEOUT_SECONDS,
    ApiClient,
    ApiClientError,
    ApiUnavailableError,
)

BASE_URL = "http://api.test"


@pytest.fixture
def client() -> ApiClient:
    return ApiClient(BASE_URL)


# --------------------------------------------------------------------------
# Success paths — one per client method.
# --------------------------------------------------------------------------


@respx.mock
def test_ask_success(client: ApiClient) -> None:
    respx.post(f"{BASE_URL}/v1/ask").mock(
        return_value=httpx.Response(
            200,
            json={
                "request_id": "req-1",
                "answer": "42",
                "citations": [
                    {
                        "chunk_id": "chunk-1",
                        "book_id": "book-1",
                        "book_title": "Meditations",
                        "section_path": ["Book II"],
                        "page": 12,
                        "quote": "You have power over your mind.",
                    }
                ],
                "arm_used": "hybrid_rerank",
                "degraded": False,
                "latency_ms": 120,
                "tokens": {"prompt": 10, "completion": 20},
            },
        )
    )

    response = client.ask("what is the meaning of life?", k=3)

    assert response.request_id == "req-1"
    assert response.answer == "42"
    assert response.degraded is False
    assert response.citations[0].book_title == "Meditations"
    sent = respx.calls.last.request
    assert sent.url == f"{BASE_URL}/v1/ask"


@respx.mock
def test_get_block_success(client: ApiClient) -> None:
    respx.get(f"{BASE_URL}/v1/blocks/abc123").mock(
        return_value=httpx.Response(
            200,
            json={
                "block_id": "abc123",
                "book_id": "book-1",
                "ordinal": 4,
                "section_path": ["Chapter 1"],
                "text": "full block text",
                "char_start": 0,
                "char_end": 16,
                "provenance": {
                    "format": "epub",
                    "page": None,
                    "spine_index": 2,
                    "anchor": "s1",
                    "source_sha256": "deadbeef",
                },
            },
        )
    )

    block = client.get_block("abc123")

    assert block.block_id == "abc123"
    assert block.text == "full block text"
    assert block.provenance.format == "epub"


@respx.mock
def test_submit_feedback_success(client: ApiClient) -> None:
    route = respx.post(f"{BASE_URL}/v1/feedback").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    result = client.submit_feedback("req-1", "up")

    assert result is None
    assert route.called
    payload = route.calls.last.request.content
    assert b'"feedback":"up"' in payload


@respx.mock
def test_build_roadmap_success(client: ApiClient) -> None:
    respx.post(f"{BASE_URL}/v1/roadmap").mock(
        return_value=httpx.Response(
            200,
            json={
                "request_id": "req-2",
                "rationale": "start broad, then specialize",
                "steps": [
                    {
                        "order": 1,
                        "ol_key": "/works/OL1W",
                        "book_id": "book-1",
                        "title": "Meditations",
                        "authors": ["Marcus Aurelius"],
                        "why": "foundational stoicism",
                        "prerequisites": [],
                        "est_effort": "light",
                    }
                ],
            },
        )
    )

    response = client.build_roadmap(["stoicism"], "beginner", "build discipline")

    assert response.request_id == "req-2"
    assert response.steps[0].title == "Meditations"
    assert response.steps[0].est_effort == "light"


@respx.mock
def test_list_books_success(client: ApiClient) -> None:
    respx.get(f"{BASE_URL}/v1/books").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "book_id": "book-1",
                    "title": "Meditations",
                    "authors": ["Marcus Aurelius"],
                    "blocks": 100,
                    "chunks": 40,
                    "format": "epub",
                },
                {
                    "book_id": "book-2",
                    "title": "Walden",
                    "authors": ["Henry David Thoreau"],
                    "blocks": 80,
                    "chunks": 30,
                    "format": "txt",
                },
            ],
        )
    )

    books = client.list_books()

    assert [book.book_id for book in books] == ["book-1", "book-2"]
    assert books[0].blocks == 100


# --------------------------------------------------------------------------
# Per-call timeout overrides.
#
# /v1/ask and /v1/roadmap are the LLM-touching endpoints: real latency is
# 13s warm even on a GPU host, past DEFAULT_TIMEOUT_SECONDS (10s) — the UI's
# headline feature must not time out against a working API. Every other call
# keeps the short default. httpx stores a per-request timeout override on
# `request.extensions["timeout"]`, which is what these assert against.
# --------------------------------------------------------------------------


@respx.mock
def test_ask_uses_the_long_llm_call_timeout(client: ApiClient) -> None:
    respx.post(f"{BASE_URL}/v1/ask").mock(
        return_value=httpx.Response(
            200,
            json={
                "request_id": "req-1",
                "answer": "42",
                "citations": [],
                "arm_used": "hybrid_rerank",
                "degraded": False,
                "latency_ms": 120,
                "tokens": {"prompt": 10, "completion": 20},
            },
        )
    )

    client.ask("what is the meaning of life?")

    sent = respx.calls.last.request
    assert sent.extensions["timeout"]["read"] == LLM_CALL_TIMEOUT_SECONDS


@respx.mock
def test_build_roadmap_uses_the_long_llm_call_timeout(client: ApiClient) -> None:
    respx.post(f"{BASE_URL}/v1/roadmap").mock(
        return_value=httpx.Response(
            200, json={"request_id": "req-2", "rationale": "r", "steps": []}
        )
    )

    client.build_roadmap(["stoicism"], "beginner", "build discipline")

    sent = respx.calls.last.request
    assert sent.extensions["timeout"]["read"] == LLM_CALL_TIMEOUT_SECONDS


@respx.mock
def test_get_books_uses_the_default_timeout(client: ApiClient) -> None:
    respx.get(f"{BASE_URL}/v1/books").mock(return_value=httpx.Response(200, json=[]))

    client.list_books()

    sent = respx.calls.last.request
    assert sent.extensions["timeout"]["read"] == DEFAULT_TIMEOUT_SECONDS


@respx.mock
def test_ask_defaults_rewrite_to_false(client: ApiClient) -> None:
    """Matches AskRequest's server-side default (apps/api/schemas.py):
    ADR-001 measured query rewriting and rejected it, so a caller here that
    omits `rewrite` must not silently re-enable it."""
    route = respx.post(f"{BASE_URL}/v1/ask").mock(
        return_value=httpx.Response(
            200,
            json={
                "request_id": "req-1",
                "answer": "42",
                "citations": [],
                "arm_used": "hybrid_rerank",
                "degraded": False,
                "latency_ms": 120,
                "tokens": {"prompt": 10, "completion": 20},
            },
        )
    )

    client.ask("what is the meaning of life?")

    payload = route.calls.last.request.content
    assert b'"rewrite":false' in payload


# --------------------------------------------------------------------------
# Error paths.
# --------------------------------------------------------------------------


@respx.mock
def test_get_block_not_found_raises_api_client_error(client: ApiClient) -> None:
    respx.get(f"{BASE_URL}/v1/blocks/missing").mock(
        return_value=httpx.Response(404, json={"detail": "block not found"})
    )

    with pytest.raises(ApiClientError) as exc_info:
        client.get_block("missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "block not found"


@respx.mock
def test_submit_feedback_unknown_request_id_raises_404(client: ApiClient) -> None:
    respx.post(f"{BASE_URL}/v1/feedback").mock(
        return_value=httpx.Response(404, json={"detail": "unknown request_id"})
    )

    with pytest.raises(ApiClientError) as exc_info:
        client.submit_feedback("does-not-exist", "down")

    assert exc_info.value.status_code == 404
    assert "unknown request_id" in exc_info.value.detail


@respx.mock
def test_ask_bad_request_raises_api_client_error(client: ApiClient) -> None:
    respx.post(f"{BASE_URL}/v1/ask").mock(
        return_value=httpx.Response(422, json={"detail": "query must not be empty"})
    )

    with pytest.raises(ApiClientError) as exc_info:
        client.ask("")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "query must not be empty"


@respx.mock
def test_error_without_json_body_falls_back_to_text(client: ApiClient) -> None:
    respx.get(f"{BASE_URL}/v1/books").mock(
        return_value=httpx.Response(500, text="internal server error")
    )

    with pytest.raises(ApiClientError) as exc_info:
        client.list_books()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "internal server error"


@respx.mock
def test_ask_timeout_raises_api_unavailable_error(client: ApiClient) -> None:
    respx.post(f"{BASE_URL}/v1/ask").mock(side_effect=httpx.TimeoutException("timed out"))

    with pytest.raises(ApiUnavailableError) as exc_info:
        client.ask("hello")

    assert "timed out" in exc_info.value.message


@respx.mock
def test_list_books_connection_error_raises_api_unavailable_error(client: ApiClient) -> None:
    respx.get(f"{BASE_URL}/v1/books").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(ApiUnavailableError) as exc_info:
        client.list_books()

    assert "Could not reach the API" in exc_info.value.message


@respx.mock
def test_build_roadmap_connection_error_raises_api_unavailable_error(client: ApiClient) -> None:
    respx.post(f"{BASE_URL}/v1/roadmap").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(ApiUnavailableError):
        client.build_roadmap(["history"], "advanced", "become an expert")


def test_base_url_trailing_slash_is_normalized() -> None:
    trailing = ApiClient(f"{BASE_URL}/")
    assert trailing._base_url == BASE_URL


@respx.mock
def test_error_body_without_a_detail_key_still_yields_a_message(client: ApiClient) -> None:
    # Not every 4xx comes from FastAPI's {"detail": ...} envelope — a reverse
    # proxy or a middleware can return arbitrary JSON. The client must still
    # produce something a human can read rather than an empty string.
    respx.post(f"{BASE_URL}/v1/ask").mock(
        return_value=httpx.Response(429, json={"error": "slow down"})
    )

    with pytest.raises(ApiClientError) as exc_info:
        client.ask("hello")

    assert exc_info.value.status_code == 429
    assert "slow down" in exc_info.value.detail


@respx.mock
def test_empty_response_body_is_returned_as_none(client: ApiClient) -> None:
    # /v1/feedback answers 204 with no body; calling .json() on that raises.
    respx.post(f"{BASE_URL}/v1/feedback").mock(return_value=httpx.Response(204))

    assert client.submit_feedback("req-1", "up") is None
