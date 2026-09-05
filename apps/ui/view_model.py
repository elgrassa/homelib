"""Pure view-model helpers for the Streamlit UI.

Everything in this module is a plain function over plain data: formatting,
aggregation and state transitions, with no ``st.*`` call anywhere. That is the
whole point of the split. ``app.py`` is a rendering shell that cannot be
executed without a Streamlit runtime, so it is exempt from the coverage floor;
this module holds the decisions, so it is *not* exempt and every function here
is covered by ``tests/test_view_model.py``.

Keeping the boundary in the filesystem rather than in a comment is what makes
it enforceable: deleting a test here fails the build, which is exactly the
guarantee a comment cannot give.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from apps.runtime_settings import AppMode, read_app_mode
from apps.ui.api_client import (
    ApiClientError,
    ApiUnavailableError,
    AskResponse,
    BookSummary,
    Citation,
    HomelibClient,
    HttpClient,
    RoadmapStep,
)

DEFAULT_API_URL = "http://localhost:8000"

# Streamlit Community Cloud secrets → os.environ (OpenAIClient / factory read env).
DEMO_ENV_KEYS: frozenset[str] = frozenset(
    {
        "APP_MODE",
        "API_URL",
        "HOMELIB_SQLITE_PATH",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_OUTPUT_TOKENS",
        "EMBED_MODEL",
        "HOMELIB_DEFAULT_ARM",
    }
)

Level = Literal["beginner", "intermediate", "advanced"]
LEVELS: tuple[Level, ...] = ("beginner", "intermediate", "advanced")


def get_api_url() -> str:
    """Read ``API_URL`` from the environment, defaulting to localhost:8000."""
    return os.environ.get("API_URL", DEFAULT_API_URL)


def apply_streamlit_secrets_to_environ(secrets: Mapping[str, Any]) -> None:
    """Copy known demo keys from Streamlit secrets into ``os.environ`` if unset."""
    for key in DEMO_ENV_KEYS:
        if key in os.environ and os.environ[key].strip() != "":
            continue
        if key not in secrets:
            continue
        value = secrets[key]
        if value is None:
            continue
        os.environ[key] = str(value)


def wants_inprocess_client(environ: Mapping[str, str] | None = None) -> bool:
    """True for Cloud/local demo: ``APP_MODE=demo`` and no ``API_URL``.

    Compose always injects ``API_URL=http://api:8000``, so the UI stays on
    HTTP even if ``APP_MODE=demo`` leaks from ``.env.example``.
    """
    env = os.environ if environ is None else environ
    api_url = (env.get("API_URL") or "").strip()
    if api_url:
        return False
    return read_app_mode(env) is AppMode.DEMO


def build_homelib_client() -> HomelibClient:
    """Factory: demo → InProcessClient; else HttpClient(API_URL)."""
    if wants_inprocess_client():
        raw = os.environ.get("HOMELIB_SQLITE_PATH", "").strip()
        if not raw:
            raise RuntimeError(
                "APP_MODE=demo requires HOMELIB_SQLITE_PATH "
                "(seed SQLite path, e.g. data/homelib.sqlite)"
            )
        # Heavy store/RAG imports live outside apps/ui (AST boundary).
        from apps.inprocess_bridge import build_inprocess_client

        return build_inprocess_client()
    return HttpClient(get_api_url())


def format_api_error_message(exc: ApiClientError | ApiUnavailableError) -> str:
    """A readable message for any client failure — never a stack trace."""
    if isinstance(exc, ApiUnavailableError):
        return f"The homelib API is unreachable: {exc.message}"
    return f"The API returned an error ({exc.status_code}): {exc.detail}"


def format_degraded_banner(response: AskResponse) -> str | None:
    """Banner text for a degraded answer, or ``None`` for a healthy one.

    A degraded answer must never be presented as if it were a normal one, so
    the caller must always check this before rendering ``response.answer``.
    """
    if not response.degraded:
        return None
    return f"Answered with a degraded backend: {response.arm_used}"


def has_voted(feedback_sent: set[str], request_id: str) -> bool:
    """Whether ``request_id`` has already had feedback submitted for it."""
    return request_id in feedback_sent


def record_vote(feedback_sent: set[str], request_id: str) -> set[str]:
    """Return a new set with ``request_id`` marked as voted (pure)."""
    return feedback_sent | {request_id}


def block_id_for_citation(citation: Citation) -> str:
    """The block id to resolve for a citation's "show full source" action.

    This used to return ``chunk_id``, because the Citation shape carried no
    block id — and ``GET /v1/blocks/{block_id}`` is keyed on block ids, so the
    button 404'd every time. Nothing caught it: the UI test asserted the
    derivation returned the chunk_id, which it faithfully did. The cold-clone
    drill found it by trying to resolve a real citation end to end.

    The seam the original author left here is what made the fix one line.
    """
    return citation.block_id


def format_citation_label(citation: Citation) -> str:
    """``book_title · section_path · page`` label for a citation expander."""
    section = " / ".join(citation.section_path) if citation.section_path else "—"
    page = str(citation.page) if citation.page is not None else "—"
    return f"{citation.book_title} · {section} · page {page}"


def parse_interests(raw: str) -> list[str]:
    """Split a free-text, comma-separated interests field into a clean list."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_level(value: str) -> Level:
    """Validate a raw selectbox value against the known roadmap levels.

    ``st.selectbox`` returns a plain ``str`` even when seeded from a tuple of
    literals, so this is the single place that narrows it back to the
    ``Level`` type the API client expects.
    """
    for level in LEVELS:
        if value == level:
            return level
    raise ValueError(f"unknown level: {value!r}")


def steps_in_order(steps: list[RoadmapStep]) -> list[RoadmapStep]:
    """Roadmap steps sorted by their declared ``order``."""
    return sorted(steps, key=lambda step: step.order)


def resolve_prerequisite_titles(steps: list[RoadmapStep]) -> dict[int, list[str]]:
    """Map each step's ``order`` to the titles of its prerequisite steps."""
    title_by_order = {step.order: step.title for step in steps}
    return {
        step.order: [
            title_by_order[prereq] for prereq in step.prerequisites if prereq in title_by_order
        ]
        for step in steps
    }


@dataclass(frozen=True)
class LibrarySummary:
    book_count: int
    total_blocks: int
    total_chunks: int


def library_summary(books: list[BookSummary]) -> LibrarySummary:
    """Ingest-stats readout: totals across every book in ``books``."""
    return LibrarySummary(
        book_count=len(books),
        total_blocks=sum(book.blocks for book in books),
        total_chunks=sum(book.chunks for book in books),
    )


# Crossroads static doors (WP08) — labels only; navigation is a pure choice.
CROSSROADS_DOORS: tuple[str, ...] = (
    "Ask",
    "Mentor",
    "Coffee Table",
    "Shelf",
    "Observatory",
    "Projection",
)


def normalize_door(value: str) -> str:
    """Validate a Crossroads door selection against the static door grid."""
    for door in CROSSROADS_DOORS:
        if value == door:
            return door
    raise ValueError(f"unknown door: {value!r}")


def playlist_visible_items(playlist: dict[str, Any]) -> list[dict[str, Any]]:
    """Items shown on the Coffee Table (exclude removed)."""
    items = playlist.get("items") or []
    return [item for item in items if item.get("status") != "removed"]


def observatory_chart_titles(payload: dict[str, Any]) -> list[str]:
    """Titles for Observatory charts, in API order."""
    charts = payload.get("charts") or []
    return [str(chart.get("title") or chart.get("id") or "") for chart in charts]
