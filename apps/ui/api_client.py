"""HTTP client for the homelib public API.

This is the ONLY module under ``apps/ui`` that performs network calls. It
talks exclusively to the FastAPI surface documented in ``specs/api.md`` —
never to Postgres, never to ``homelib_core``/``homelib_rag`` internals. All
response shapes are re-declared locally (rather than imported from
``homelib_core.models``) so that this package's only external dependency for
data is ``pydantic`` + ``httpx``.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel

DEFAULT_TIMEOUT_SECONDS = 10.0

# /v1/ask and /v1/roadmap are the LLM-touching endpoints: real latency is
# 13s warm even on a GPU host, and far more on a CPU-only compose stack
# (see homelib_rag.answer._TIMEOUT_SECONDS). The 10s default above is right
# for every other call but would time out the UI's headline feature against
# a working API, so these two calls opt into a much longer per-call timeout.
LLM_CALL_TIMEOUT_SECONDS = 300.0


class ApiClientError(Exception):
    """Raised for a 4xx/5xx response from the API.

    ``detail`` carries the API's error envelope message (``{"detail": str}``,
    per specs/api.md) so callers can show it to the user verbatim.
    """

    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class ApiUnavailableError(Exception):
    """Raised when the API cannot be reached at all (timeout/connection)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TokenUsage(BaseModel):
    prompt: int
    completion: int


class Citation(BaseModel):
    chunk_id: str
    block_id: str = ""
    book_id: str
    book_title: str
    section_path: list[str]
    page: int | None = None
    quote: str


class AskResponse(BaseModel):
    request_id: str
    answer: str
    citations: list[Citation]
    arm_used: str
    degraded: bool
    latency_ms: int
    tokens: TokenUsage


class Provenance(BaseModel):
    format: str
    page: int | None = None
    spine_index: int | None = None
    anchor: str | None = None
    source_sha256: str


class Block(BaseModel):
    block_id: str
    book_id: str
    ordinal: int
    section_path: list[str]
    text: str
    char_start: int
    char_end: int
    provenance: Provenance


class RoadmapStep(BaseModel):
    order: int
    ol_key: str | None = None
    book_id: str | None = None
    title: str
    authors: list[str]
    why: str
    prerequisites: list[int]
    est_effort: Literal["light", "medium", "deep"]


class RoadmapResponse(BaseModel):
    request_id: str
    steps: list[RoadmapStep]
    rationale: str


class BookSummary(BaseModel):
    book_id: str
    title: str
    authors: list[str]
    blocks: int
    chunks: int
    format: str


def _extract_detail(response: httpx.Response) -> str:
    """Best-effort extraction of the ``{"detail": str}`` error envelope."""
    try:
        data = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])
    return response.text or f"HTTP {response.status_code}"


class ApiClient:
    """Thin synchronous client over the homelib public API."""

    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        request_timeout = timeout if timeout is not None else self._timeout
        try:
            response = httpx.request(method, url, json=json, timeout=request_timeout)
        except httpx.TimeoutException as exc:
            raise ApiUnavailableError(f"Request to {url} timed out") from exc
        except httpx.TransportError as exc:
            raise ApiUnavailableError(f"Could not reach the API at {url}") from exc
        if response.status_code >= 400:
            raise ApiClientError(_extract_detail(response), status_code=response.status_code)
        if not response.content:
            return None
        return response.json()

    def ask(
        self,
        query: str,
        *,
        k: int = 5,
        arm: Literal["lexical", "vector", "hybrid", "hybrid_rerank"] | None = None,
        # Matches AskRequest's server-side default (apps/api/schemas.py):
        # ADR-001 measured query rewriting and rejected it. A caller here
        # that omits `rewrite` must not silently re-enable it by sending
        # `true` regardless of the server default.
        rewrite: bool = False,
    ) -> AskResponse:
        payload = {"query": query, "k": k, "arm": arm, "rewrite": rewrite}
        data = self._request("POST", "/v1/ask", json=payload, timeout=LLM_CALL_TIMEOUT_SECONDS)
        return AskResponse.model_validate(data)

    def get_block(self, block_id: str) -> Block:
        data = self._request("GET", f"/v1/blocks/{block_id}")
        return Block.model_validate(data)

    def submit_feedback(
        self,
        request_id: str,
        feedback: Literal["up", "down"],
        *,
        comment: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "request_id": request_id,
            "feedback": feedback,
            "comment": comment,
        }
        self._request("POST", "/v1/feedback", json=payload)

    def build_roadmap(
        self,
        interests: list[str],
        level: Literal["beginner", "intermediate", "advanced"],
        goal: str,
        max_steps: int = 8,
    ) -> RoadmapResponse:
        payload = {
            "interests": interests,
            "level": level,
            "goal": goal,
            "max_steps": max_steps,
        }
        data = self._request("POST", "/v1/roadmap", json=payload, timeout=LLM_CALL_TIMEOUT_SECONDS)
        return RoadmapResponse.model_validate(data)

    def list_books(self) -> list[BookSummary]:
        data = self._request("GET", "/v1/books")
        return [BookSummary.model_validate(item) for item in data]
