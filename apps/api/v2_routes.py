"""v2 product routes - mentor, scene, Coffee Table, progress, observatory (WP07-10)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from homelib_rag.mentor import (
    CreatePathRequest,
    MentorIntakeRequest,
    MentorIntakeResponse,
    PathResponse,
    build_path,
    mentor_intake,
)
from homelib_rag.scene_search import (
    ResourceNotFoundError,
    ResourceNotSearchableError,
    SceneMode,
    SceneSearchResponse,
    scene_search,
)
from pydantic import BaseModel, ConfigDict, Field

from apps.api import sqlite_deps
from apps.runtime_settings import read_app_mode
from apps.store import coffee_table as ct
from apps.store import observatory as obs
from apps.store import progress_ops as prog
from apps.store.sqlite import LOCAL_USER_ID, create_demo_session

router = APIRouter(tags=["v2"])


class SceneSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    mode: Literal["exact", "keyword", "semantic", "smart", "ask"] = "smart"
    chapter_id: str | None = None
    k: int = Field(default=5, ge=1, le=20)


class PlaylistAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept_item_ids: list[str] | None = None


class AddPlaylistItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str
    origin: ct.PlaylistOrigin = ct.PlaylistOrigin.MANUAL_SHELF


class PatchPlaylistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ordinal: int | None = None
    status: ct.PlaylistStatus | None = None


class PatchPlaylistItemsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PatchPlaylistItem]


class OkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True


class AudioCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_generate: bool = False
    preview_available: bool = False


class ResourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    book_id: str | None
    title: str
    authors: list[str]
    source: Literal["shelf", "discover"] = "shelf"
    rights_status: str
    can_index_text: bool
    full_text_available: bool
    format: str | None = None


class ResourceList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ResourceSummary]
    unique_count: int
    approximate_provider_counts: dict[str, int] = Field(default_factory=dict)
    degraded: bool = False


def _require_sqlite() -> None:
    if sqlite_deps.sqlite_path() is None:
        raise HTTPException(
            status_code=503,
            detail="HOMELIB_SQLITE_PATH is required for this v2 endpoint",
        )


def _principal(x_demo_session: str | None) -> str:
    _require_sqlite()
    mode = read_app_mode()
    with sqlite_deps.open_store() as conn:
        if mode.value == "demo":
            if x_demo_session:
                row = conn.execute(
                    "SELECT principal_id FROM demo_session WHERE id = ?",
                    (x_demo_session,),
                ).fetchone()
                if row is None:
                    raise HTTPException(status_code=401, detail="unknown demo session")
                return str(row[0])
            session = create_demo_session(conn)
            return session.principal_id
        return LOCAL_USER_ID


@router.post("/v1/mentor/intake", response_model=MentorIntakeResponse)
def post_mentor_intake(req: MentorIntakeRequest) -> MentorIntakeResponse:
    from apps.api.main import get_deps

    deps = get_deps()
    return mentor_intake(
        req.goal,
        req.interests,
        req.level,
        client=deps.llm_client,
        catalog=deps.catalog_search,
        shelf_search=lambda q, k: deps.retrieve(q, k, "hybrid")[0],
        # `Deps.get_block` already dispatches on HOMELIB_SQLITE_PATH
        # (apps/api/main.py's `_get_block`), so the Mentor agent loop's
        # `get_block` tool is store-safe without touching agent.py's own
        # Postgres-bound default (specs/agent-tools.md).
        get_block=deps.get_block,
    )


@router.post("/v1/paths", response_model=PathResponse)
def post_paths(req: CreatePathRequest) -> PathResponse:
    from apps.api.main import get_deps

    deps = get_deps()
    try:
        return build_path(
            req.title,
            req.kind,
            req.steps,
            catalog=deps.catalog_search,
            interests=[],
            goal=req.title,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/v1/resources/{resource_id}/search", response_model=SceneSearchResponse)
def post_scene_search(resource_id: str, req: SceneSearchRequest) -> SceneSearchResponse:
    _require_sqlite()
    try:
        with sqlite_deps.open_store() as conn:
            return scene_search(
                conn,
                resource_id,
                req.query,
                mode=SceneMode(req.mode),
                chapter_id=req.chapter_id,
                k=req.k,
            )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResourceNotSearchableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/v1/resources", response_model=ResourceList)
def get_resources(
    source: Literal["shelf", "discover"] | None = None,
    q: str | None = None,
) -> ResourceList:
    _require_sqlite()
    with sqlite_deps.open_store() as conn:
        sql = "SELECT book_id, title, authors, rights_status FROM books"
        params: list[Any] = []
        if q:
            sql += " WHERE title LIKE ?"
            params.append(f"%{q}%")
        sql += " ORDER BY title"
        rows = conn.execute(sql, params).fetchall()
    import json

    from apps.store.sqlite import can_index_text

    items: list[ResourceSummary] = []
    for row in rows:
        authors = json.loads(str(row[2])) if row[2] else []
        rights = str(row[3])
        indexable = can_index_text(rights)
        items.append(
            ResourceSummary(
                id=str(row[0]),
                book_id=str(row[0]),
                title=str(row[1]),
                authors=[str(a) for a in authors] if isinstance(authors, list) else [],
                source="shelf",
                rights_status=rights,
                can_index_text=indexable,
                full_text_available=indexable,
            )
        )
    if source == "discover":
        items = []
    return ResourceList(items=items, unique_count=len(items))


@router.get("/v1/playlists/current", response_model=ct.Playlist)
def get_playlist_current(
    x_demo_session: str | None = Header(default=None, alias="X-Demo-Session"),
) -> ct.Playlist:
    principal = _principal(x_demo_session)
    with sqlite_deps.open_store() as conn:
        return ct.get_playlist(conn, principal)


@router.post("/v1/playlists/current", response_model=ct.Playlist)
def post_playlist_accept(
    req: PlaylistAcceptRequest,
    x_demo_session: str | None = Header(default=None, alias="X-Demo-Session"),
) -> ct.Playlist:
    principal = _principal(x_demo_session)
    try:
        with sqlite_deps.open_store() as conn:
            return ct.accept_proposed(
                conn, principal_id=principal, accept_item_ids=req.accept_item_ids
            )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=f"unknown item {exc}") from exc


@router.post("/v1/playlists/current/items", response_model=ct.Playlist)
def post_playlist_item(
    req: AddPlaylistItemRequest,
    x_demo_session: str | None = Header(default=None, alias="X-Demo-Session"),
) -> ct.Playlist:
    principal = _principal(x_demo_session)
    with sqlite_deps.open_store() as conn:
        return ct.add_item(
            conn,
            principal_id=principal,
            resource_id=req.resource_id,
            origin=req.origin,
        )


@router.patch("/v1/playlists/current/items", response_model=ct.Playlist)
def patch_playlist_items(
    req: PatchPlaylistItemsRequest,
    x_demo_session: str | None = Header(default=None, alias="X-Demo-Session"),
) -> ct.Playlist:
    principal = _principal(x_demo_session)
    try:
        with sqlite_deps.open_store() as conn:
            return ct.patch_items(
                conn,
                principal_id=principal,
                updates=[i.model_dump(exclude_none=True) for i in req.items],
            )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=f"unknown item {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/v1/playlists/current/items/{item_id}", response_model=ct.Playlist)
def delete_playlist_item(
    item_id: str,
    x_demo_session: str | None = Header(default=None, alias="X-Demo-Session"),
) -> ct.Playlist:
    principal = _principal(x_demo_session)
    try:
        with sqlite_deps.open_store() as conn:
            return ct.remove_item(conn, principal_id=principal, item_id=item_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=f"unknown item {exc}") from exc


@router.post("/v1/progress", response_model=OkResponse)
def post_progress(
    event: prog.ProgressEvent,
    x_demo_session: str | None = Header(default=None, alias="X-Demo-Session"),
) -> OkResponse:
    principal = _principal(x_demo_session)
    try:
        with sqlite_deps.open_store() as conn:
            prog.upsert_progress(conn, principal_id=principal, event=event)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=f"unknown resource {exc}") from exc
    return OkResponse(ok=True)


@router.get("/v1/observatory", response_model=obs.ObservatoryResponse)
def get_observatory() -> obs.ObservatoryResponse:
    _require_sqlite()
    with sqlite_deps.open_store() as conn:
        return obs.build_observatory(conn)


@router.get("/v1/audio/capabilities", response_model=AudioCapabilities)
def get_audio_capabilities() -> AudioCapabilities:
    return AudioCapabilities(can_generate=False, preview_available=False)


@router.post("/v1/demo/session")
def post_demo_session() -> dict[str, str]:
    _require_sqlite()
    with sqlite_deps.open_store() as conn:
        session = create_demo_session(conn)
    return {"demo_session_id": session.id, "principal_id": session.principal_id}
