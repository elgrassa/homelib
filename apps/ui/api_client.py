"""HTTP client for the homelib public API.

This is the ONLY module under ``apps/ui`` that performs network calls. It
talks exclusively to the FastAPI surface documented in ``specs/api.md`` —
never to Postgres, never to ``homelib_core``/``homelib_rag`` internals. All
response shapes are re-declared locally (rather than imported from
``homelib_core.models``) so that this package's only external dependency for
data is ``pydantic`` + ``httpx``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel

DEFAULT_TIMEOUT_SECONDS = 10.0

# /v1/ask and /v1/roadmap are the LLM-touching endpoints: real latency is
# 13s warm even on a GPU host, and far more on a CPU-only compose stack
# (see homelib_rag.answer._TIMEOUT_SECONDS). The 10s default above is right
# for every other call but would time out the UI's headline feature against
# a working API, so these two calls opt into a much longer per-call timeout.
LLM_CALL_TIMEOUT_SECONDS = 300.0

# The demo-principal header the API reads (apps/api/v2_routes.py). The specs
# named it `X-Demo-Session-Id` before the route landed; the route is the contract.
DEMO_SESSION_HEADER = "X-Demo-Session"


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
    # C5 (specs/monitoring.md "Tracing"): optional so an API predating C5
    # (or one running without HOMELIB_SQLITE_PATH) still validates.
    trace_id: str | None = None
    # C4b (specs/monitoring.md "Demo answer cache"): always False outside
    # APP_MODE=demo.
    cache_hit: bool = False


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

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # Optional persistent client — used by the demo ASGI in-process path
        # so Ask shares one transport without a network hop.
        self._http_client = http_client
        # APP_MODE=demo principal (specs/principals.md). The API mints a fresh
        # anonymous principal for every header-less request, so a client that
        # never sends `X-Demo-Session` sees an empty Coffee Table after every
        # rerun. Set via `set_demo_session`/`create_demo_session`; None in
        # selfhosted, where the server ignores the header anyway.
        self.demo_session_id: str | None = None

    def _headers(self) -> dict[str, str]:
        if self.demo_session_id is None:
            return {}
        return {DEMO_SESSION_HEADER: self.demo_session_id}

    def _send(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None,
        timeout: float,
    ) -> httpx.Response:
        headers = self._headers()
        try:
            if self._http_client is not None:
                return self._http_client.request(
                    method, url, json=json, timeout=timeout, headers=headers
                )
            return httpx.request(method, url, json=json, timeout=timeout, headers=headers)
        except httpx.TimeoutException as exc:
            raise ApiUnavailableError(f"Request to {url} timed out") from exc
        except httpx.TransportError as exc:
            raise ApiUnavailableError(f"Could not reach the API at {url}") from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
        _allow_remint: bool = True,
    ) -> Any:
        url = f"{self._base_url}{path}"
        request_timeout = timeout if timeout is not None else self._timeout
        response = self._send(method, url, json=json, timeout=request_timeout)
        # Demo-gated, single retry: a 401 means the server no longer knows our
        # demo session (restart, TTL sweep). Mint once and resend. Gated on a
        # session id being set so a selfhosted 401 propagates unchanged rather
        # than minting a useless session.
        if response.status_code == 401 and _allow_remint and self.demo_session_id is not None:
            self.demo_session_id = None
            self.demo_session_id = self._mint_demo_session()
            response = self._send(method, url, json=json, timeout=request_timeout)
        if response.status_code >= 400:
            raise ApiClientError(_extract_detail(response), status_code=response.status_code)
        if not response.content:
            return None
        return response.json()

    def _mint_demo_session(self) -> str:
        data = self._request("POST", "/v1/demo/session", _allow_remint=False)
        if not isinstance(data, dict) or not data.get("demo_session_id"):
            raise ApiClientError("demo session response missing demo_session_id", status_code=502)
        return str(data["demo_session_id"])

    def create_demo_session(self) -> str:
        """Mint a demo principal via `POST /v1/demo/session` and use it from now on."""
        self.demo_session_id = self._mint_demo_session()
        return self.demo_session_id

    def set_demo_session(self, session_id: str | None) -> None:
        """Adopt an existing demo session id (e.g. one kept in Streamlit session
        state across reruns), or clear it with None."""
        self.demo_session_id = session_id

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        data = self._request(method, path, json=json, timeout=timeout)
        if not isinstance(data, dict):
            raise ApiClientError("expected JSON object", status_code=502)
        return data

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

    def get_book_block(self, book_id: str, *, ordinal: int = 0) -> Block:
        data = self._request("GET", f"/v1/books/{book_id}/blocks?ordinal={int(ordinal)}")
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

    def list_resources(self, *, q: str | None = None) -> dict[str, Any]:
        path = "/v1/resources" if not q else f"/v1/resources?q={q}"
        return self._request_json("GET", path)

    def mentor_intake(
        self,
        goal: str,
        interests: list[str] | None = None,
        level: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "goal": goal,
            "interests": interests or [],
            "level": level,
        }
        return self._request_json(
            "POST", "/v1/mentor/intake", json=payload, timeout=LLM_CALL_TIMEOUT_SECONDS
        )

    def get_playlist(self) -> dict[str, Any]:
        return self._request_json("GET", "/v1/playlists/current")

    def add_playlist_item(self, resource_id: str, origin: str = "manual_shelf") -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/v1/playlists/current/items",
            json={"resource_id": resource_id, "origin": origin},
        )

    def accept_playlist(self, accept_item_ids: list[str] | None = None) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/v1/playlists/current",
            json={"accept_item_ids": accept_item_ids},
        )

    def remove_playlist_item(self, item_id: str) -> dict[str, Any]:
        return self._request_json("DELETE", f"/v1/playlists/current/items/{item_id}")

    def save_progress(
        self,
        resource_id: str,
        *,
        kind: str = "read",
        char_offset: int | None = None,
        block_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/v1/progress",
            json={
                "resource_id": resource_id,
                "kind": kind,
                "char_offset": char_offset,
                "block_id": block_id,
            },
        )

    def scene_search(
        self,
        resource_id: str,
        query: str,
        *,
        mode: str = "smart",
        k: int = 5,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/v1/resources/{resource_id}/search",
            json={"query": query, "mode": mode, "k": k},
            timeout=LLM_CALL_TIMEOUT_SECONDS,
        )

    def get_observatory(self) -> dict[str, Any]:
        return self._request_json("GET", "/v1/observatory")

    def health(self) -> dict[str, Any]:
        return self._request_json("GET", "/health")


# WP08 HomelibClient seam — HttpClient is the live path; InProcessClient is
# for APP_MODE=demo / Community Cloud (injected service callables, no store
# imports under apps/ui).


@runtime_checkable
class HomelibClient(Protocol):
    def health(self) -> dict[str, Any]: ...

    def create_demo_session(self) -> str: ...

    def set_demo_session(self, session_id: str | None) -> None: ...

    def ask(
        self,
        query: str,
        *,
        k: int = 5,
        arm: Literal["lexical", "vector", "hybrid", "hybrid_rerank"] | None = None,
        rewrite: bool = False,
    ) -> AskResponse: ...


class HttpClient(ApiClient):
    """Selfhosted edition — FastAPI over HTTP with per-call timeouts."""


class InProcessClient:
    """Demo edition — same shapes as HttpClient, no network hop.

    Callables are injected for conformance tests so this module never imports
    SQLite, RAG, or provider SDKs (AST boundary in apps/ui/tests). Production
    demo wiring passes an ASGI-backed ``ApiClient`` as ``delegate`` from
    ``apps.inprocess_bridge`` (outside the UI package).
    """

    def __init__(
        self,
        *,
        health: Callable[[], dict[str, Any]] | None = None,
        ask: Callable[..., AskResponse] | None = None,
        delegate: ApiClient | None = None,
    ) -> None:
        if health is None and ask is None and delegate is None:
            raise TypeError("InProcessClient requires health/ask callables or a delegate")
        self._health = health
        self._ask = ask
        self._delegate = delegate
        self._demo_session_id: str | None = None

    def _require_delegate(self) -> ApiClient:
        if self._delegate is None:
            raise ApiUnavailableError("InProcessClient has no delegate for this call")
        return self._delegate

    def health(self) -> dict[str, Any]:
        if self._health is not None:
            return self._health()
        return self._require_delegate().health()

    def ask(
        self,
        query: str,
        *,
        k: int = 5,
        arm: Literal["lexical", "vector", "hybrid", "hybrid_rerank"] | None = None,
        rewrite: bool = False,
    ) -> AskResponse:
        if self._ask is not None:
            return self._ask(query, k=k, arm=arm, rewrite=rewrite)
        return self._require_delegate().ask(query, k=k, arm=arm, rewrite=rewrite)

    # Explicit forwards — mypy does not follow __getattr__ for the UI surface.

    @property
    def demo_session_id(self) -> str | None:
        if self._delegate is not None:
            return self._delegate.demo_session_id
        return self._demo_session_id

    def create_demo_session(self) -> str:
        return self._require_delegate().create_demo_session()

    def set_demo_session(self, session_id: str | None) -> None:
        if self._delegate is not None:
            self._delegate.set_demo_session(session_id)
        self._demo_session_id = session_id

    def get_block(self, block_id: str) -> Block:
        return self._require_delegate().get_block(block_id)

    def get_book_block(self, book_id: str, *, ordinal: int = 0) -> Block:
        return self._require_delegate().get_book_block(book_id, ordinal=ordinal)

    def submit_feedback(
        self,
        request_id: str,
        feedback: Literal["up", "down"],
        *,
        comment: str | None = None,
    ) -> None:
        self._require_delegate().submit_feedback(request_id, feedback, comment=comment)

    def build_roadmap(
        self,
        interests: list[str],
        level: Literal["beginner", "intermediate", "advanced"],
        goal: str,
        max_steps: int = 8,
    ) -> RoadmapResponse:
        return self._require_delegate().build_roadmap(interests, level, goal, max_steps=max_steps)

    def list_books(self) -> list[BookSummary]:
        return self._require_delegate().list_books()

    def list_resources(self, *, q: str | None = None) -> dict[str, Any]:
        return self._require_delegate().list_resources(q=q)

    def mentor_intake(
        self,
        goal: str,
        interests: list[str] | None = None,
        level: str | None = None,
    ) -> dict[str, Any]:
        return self._require_delegate().mentor_intake(goal, interests, level)

    def get_playlist(self) -> dict[str, Any]:
        return self._require_delegate().get_playlist()

    def add_playlist_item(self, resource_id: str, origin: str = "manual_shelf") -> dict[str, Any]:
        return self._require_delegate().add_playlist_item(resource_id, origin)

    def accept_playlist(self, accept_item_ids: list[str] | None = None) -> dict[str, Any]:
        return self._require_delegate().accept_playlist(accept_item_ids)

    def remove_playlist_item(self, item_id: str) -> dict[str, Any]:
        return self._require_delegate().remove_playlist_item(item_id)

    def save_progress(
        self,
        resource_id: str,
        *,
        kind: str = "read",
        char_offset: int | None = None,
        block_id: str | None = None,
    ) -> dict[str, Any]:
        return self._require_delegate().save_progress(
            resource_id, kind=kind, char_offset=char_offset, block_id=block_id
        )

    def scene_search(
        self,
        resource_id: str,
        query: str,
        *,
        mode: str = "smart",
        k: int = 5,
    ) -> dict[str, Any]:
        return self._require_delegate().scene_search(resource_id, query, mode=mode, k=k)

    def get_observatory(self) -> dict[str, Any]:
        return self._require_delegate().get_observatory()
