"""Request/response shapes for `apps/api` — see specs/api.md.

`AskResponse`/`Citation`/`TokenUsage` (specs/answer.md) and
`RoadmapResponse`/`RoadmapStep` (specs/roadmap.md) are constructed and
validated inside `homelib_rag`, not here — this module imports and re-exports
them so every endpoint's `response_model` and every test import can come from
one place, but never redefines their fields (the single source of truth for
those shapes is the `homelib_rag` module that builds them). Request shapes and
API-only response shapes (`Health`, `IngestResponse`, `BookSummary`, ...) are
owned by this module because nothing under `homelib_rag`/`homelib_core`
constructs them.
"""

from __future__ import annotations

from typing import Literal, Self

from homelib_core.models import Block, ExtractionResult
from homelib_rag.answer import AskResponse, Citation, TokenUsage
from homelib_rag.roadmap import Level, RoadmapResponse, RoadmapStep
from pydantic import BaseModel, ConfigDict, model_validator

__all__ = [
    "AskRequest",
    "AskResponse",
    "Block",
    "BookSummary",
    "Citation",
    "FeedbackRequest",
    "Health",
    "IngestRequest",
    "IngestResponse",
    "LLMHealth",
    "Level",
    "OkResponse",
    "RoadmapRequest",
    "RoadmapResponse",
    "RoadmapStep",
    "TokenUsage",
]

Arm = Literal["lexical", "vector", "hybrid", "hybrid_rerank"]


class LLMHealth(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    model: str
    reachable: bool


class Health(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    db: bool
    llm: LLMHealth
    books: int
    chunks: int


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    k: int = 5
    arm: Arm | None = None
    rewrite: bool = True


class RoadmapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interests: list[str]
    level: Level
    goal: str
    max_steps: int = 8


class IngestRequest(BaseModel):
    """Discriminated by which of `path`/`source` is set — see specs/api.md:
    `POST /v1/ingest` takes `{path: str} | {source: "snapshot"}`."""

    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    source: Literal["snapshot"] | None = None

    @model_validator(mode="after")
    def _exactly_one_of_path_or_source(self) -> Self:
        if (self.path is None) == (self.source is None):
            raise ValueError("exactly one of `path` or `source` must be set")
        return self


class IngestResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    book_id: str
    blocks: int
    chunks: int
    extraction: ExtractionResult


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    feedback: Literal["up", "down"]
    comment: str | None = None


class OkResponse(BaseModel):
    ok: Literal[True] = True


class BookSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    book_id: str
    title: str
    authors: list[str]
    blocks: int
    chunks: int
    format: str
