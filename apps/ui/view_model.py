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

import html
import json
import os
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlparse

from apps.runtime_settings import AppMode, read_app_mode
from apps.ui.api_client import (
    ApiClientError,
    ApiUnavailableError,
    AskResponse,
    BookSummary,
    Citation,
    HttpClient,
    InProcessClient,
    RoadmapStep,
)

if TYPE_CHECKING:
    from streamlit.runtime.state import SessionStateProxy

DEFAULT_API_URL = "http://localhost:8000"

# Streamlit Community Cloud secrets → os.environ (OpenAIClient / factory read env).
DEMO_ENV_KEYS: frozenset[str] = frozenset(
    {
        "APP_MODE",
        "API_URL",
        "HOMELIB_SQLITE_PATH",
        "HOMELIB_BUILD_SHA",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_OUTPUT_TOKENS",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "HOMELIB_DEMO_LLM_DAILY_LIMIT",
        "EMBED_MODEL",
        "HOMELIB_DEFAULT_ARM",
    }
)

Level = Literal["beginner", "intermediate", "advanced"]
LEVELS: tuple[Level, ...] = ("beginner", "intermediate", "advanced")


@dataclass(frozen=True)
class MentorPreset:
    """Curated Mentor starter (public curriculum shape — not shelf-grounded RAG)."""

    preset_id: str
    button_label: str
    goal: str
    interests: str
    level: Level
    response: Mapping[str, Any]


def _mentor_path_steps(rows: Sequence[tuple[str, str, str | None]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for order, (title, why, url) in enumerate(rows):
        step: dict[str, Any] = {"order": order, "title": title, "why": why}
        if url:
            step["url"] = url
        steps.append(step)
    return steps


def mentor_presets() -> tuple[MentorPreset, ...]:
    """Starter chips for Mentor. Public study order only — no private PrepOS vault.

    These load a curated proposal without calling the LLM: the demo shelf is
    public-domain literature, so an evidence-grounded Mentor run cannot ship a
    modern AI-engineer curriculum from full text. Callers must label the path
    as curated. Do not reuse the golden abstention goal "Land AI engineer job".
    """
    ai_steps = _mentor_path_steps(
        (
            (
                "Neural networks visual intuition",
                "3Blue1Brown neural-network playlist — geometric intuition before code.",
                "https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi",
            ),
            (
                "How modern LLMs are trained and used",
                "Karpathy Deep Dive lecture — training loop and inference shape.",
                "https://youtu.be/7xTGNNLPyMI",
            ),
            (
                "Building a transformer from scratch",
                "Karpathy Zero to Hero + GPT-2 reproduce — mechanism-level depth.",
                "https://www.youtube.com/playlist?list=PLAqhIrjkxbuWI23v9cThsA9GvCAUhRvKZ",
            ),
            (
                "Prompting and structured outputs",
                "Anthropic Academy / Claude API + MCP — tools and structured replies.",
                "https://www.anthropic.com/learn",
            ),
            (
                "RAG pipelines and hybrid retrieval",
                "LLM Zoomcamp RAG modules — retrieve, rerank, cite; matches this app's Ask path.",
                "https://www.youtube.com/playlist?list=PL3MmuxUbc_hIoBpuc900htYF4uhEAbaT-",
            ),
            (
                "Agents, tools, and Model Context Protocol",
                "Tool-using agents and MCP contracts — Mentor's own tool loop is a tiny cousin.",
                None,
            ),
            (
                "Evaluating RAG and agents",
                "Evals as the differentiator — faithfulness, citation validity, harnesses.",
                None,
            ),
            (
                "Tracing, cost, and LLM observability",
                "Langfuse/OTel-style traces and cost/latency judgment (Observatory door).",
                None,
            ),
            (
                "Serving, batching, and inference efficiency",
                "vLLM / batching literacy — production cost and latency trade-offs.",
                None,
            ),
            (
                "Guardrails and prompt-injection defenses",
                "OWASP LLM Top 10 topics — treat untrusted text as untrusted input.",
                None,
            ),
        )
    )
    sdet_steps = _mentor_path_steps(
        (
            (
                "Kafka fundamentals for testers",
                "Topics, consumer groups, offsets — enough to design stream tests.",
                None,
            ),
            (
                "Testing Kafka and async boundaries",
                "Contract the producer/consumer seam; avoid flaky sleeps.",
                None,
            ),
            (
                "Exactly-once, outbox, and idempotency",
                "Failure modes that only show under retry and duplicate delivery.",
                None,
            ),
            (
                "Schema evolution and compatibility",
                "Schema Registry / Avro-Protobuf compatibility rules as test oracles.",
                None,
            ),
            (
                "Consumer-driven contracts (Pact / SCC)",
                "Break the monolith of end-to-end for service pairs.",
                None,
            ),
            (
                "Deterministic simulation and chaos",
                "Jepsen-style thinking and controlled fault injection.",
                None,
            ),
            (
                "Load (k6) and resilience",
                "SLOs, soak, and what to assert when the system bends.",
                None,
            ),
            (
                "Distributed tracing (OpenTelemetry)",
                "Trace-based debugging across services — pair with load and Kafka labs.",
                None,
            ),
        )
    )
    return (
        MentorPreset(
            preset_id="ai-engineer",
            button_label="AI engineer study path",
            goal=(
                "Build production LLM systems with citation-grade RAG, tool-using "
                "agents, evaluation harnesses, and cost/latency observability"
            ),
            interests="transformers, RAG, agents, MCP, evals, LLMOps, AI security",
            level="intermediate",
            response={
                "request_id": "preset-ai-engineer",
                "proposed_area": {
                    "name": "AI Engineering",
                    "copy": "Production LLM systems — mechanism depth, not framework tourism.",
                },
                "proposed_wing": {
                    "name": "Applied GenAI",
                    "copy": "RAG → agents → evals → ops, in that dependency order.",
                },
                "proposed_path": {
                    "title": "AI engineer — curated public study path",
                    "steps": ai_steps,
                },
                "rationale": (
                    "Curated public curriculum (Track E shape). The demo shelf is "
                    "public-domain literature, so this path is not shelf-grounded RAG — "
                    "use Discover / external links for modern sources. Accept to Coffee "
                    "Table only queues steps that already match a full-text shelf title."
                ),
                "citations": [],
                "degraded": False,
                "high_stakes_notice": None,
                "tool_calls": [],
                "rounds_used": 0,
                "failure_category": None,
                "preset_id": "ai-engineer",
            },
        ),
        MentorPreset(
            preset_id="sdet",
            button_label="SDET / distributed testing path",
            goal=(
                "Senior distributed-systems testing: contracts, Kafka/async, "
                "schema evolution, load, and trace-based debugging"
            ),
            interests="Kafka, contract testing, schema registry, OpenTelemetry, k6, chaos",
            level="intermediate",
            response={
                "request_id": "preset-sdet",
                "proposed_area": {
                    "name": "Software quality engineering",
                    "copy": "Distributed systems testing for production services.",
                },
                "proposed_wing": {
                    "name": "SDET / test automation",
                    "copy": "Contracts and observability before brittle UI e2e.",
                },
                "proposed_path": {
                    "title": "SDET — curated public study path",
                    "steps": sdet_steps,
                },
                "rationale": (
                    "Curated public SDET spine (Kafka → contracts → load → OTel). "
                    "Not shelf-grounded on the demo corpus — treat as a study outline; "
                    "pair with labs outside this shelf."
                ),
                "citations": [],
                "degraded": False,
                "high_stakes_notice": None,
                "tool_calls": [],
                "rounds_used": 0,
                "failure_category": None,
                "preset_id": "sdet",
            },
        ),
    )


def mentor_preset_by_id(preset_id: str) -> MentorPreset | None:
    for preset in mentor_presets():
        if preset.preset_id == preset_id:
            return preset
    return None


def apply_mentor_preset(
    session_state: MutableMapping[str, Any],
    preset_id: str,
) -> bool:
    """Fill Mentor form keys and seed ``last_mentor`` from a curated preset."""
    preset = mentor_preset_by_id(preset_id)
    if preset is None:
        return False
    session_state["mentor_goal"] = preset.goal
    session_state["mentor_interests"] = preset.interests
    session_state["mentor_level"] = preset.level
    session_state["last_mentor"] = dict(preset.response)
    session_state["last_mentor_goal"] = preset.goal
    session_state.pop("last_mentor_catalog", None)
    session_state.pop("mentor_pending", None)
    return True


def get_api_url() -> str:
    """Read ``API_URL`` from the environment, defaulting to localhost:8000."""
    return os.environ.get("API_URL", DEFAULT_API_URL)


def resolve_build_sha(
    *,
    environ: Mapping[str, str] | None = None,
    git_short_sha: Callable[[], str] | None = None,
) -> str:
    """Short revision for the Crossroads caption (Cloud deploy verification).

    Prefer an explicit ``HOMELIB_BUILD_SHA`` (Streamlit secrets / CI inject),
    then ``SOURCE_VERSION`` / ``GIT_COMMIT`` when a host provides them, then
    a filesystem read of ``.git/HEAD`` for local and Compose checkouts.
    Returns ``unknown`` when none are available (e.g. an unpacked Cloud
    bundle without git metadata).
    """
    env = os.environ if environ is None else environ
    for key in ("HOMELIB_BUILD_SHA", "SOURCE_VERSION", "GIT_COMMIT"):
        raw = (env.get(key) or "").strip()
        if raw:
            return raw[:12] if len(raw) > 12 else raw
    probe = git_short_sha if git_short_sha is not None else _read_git_short_sha
    try:
        sha = probe().strip()
    except Exception:
        return "unknown"
    return sha or "unknown"


def _read_git_short_sha() -> str:
    """Read HEAD SHA from ``.git`` without spawning a process (ruff S603/S607)."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        git_dir = parent / ".git"
        if not git_dir.exists():
            continue
        if git_dir.is_file():
            # worktree: `.git` is a file pointing at the real gitdir
            raw = git_dir.read_text(encoding="utf-8").strip()
            if raw.startswith("gitdir:"):
                git_dir = (parent / raw.split(":", 1)[1].strip()).resolve()
            else:
                continue
        head_path = git_dir / "HEAD"
        head = head_path.read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            sha = (git_dir / ref).read_text(encoding="utf-8").strip()
        else:
            sha = head
        if len(sha) >= 7:
            return sha[:7]
    raise FileNotFoundError("no .git HEAD")


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


def build_homelib_client() -> HttpClient | InProcessClient:
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


DEMO_SESSION_KEY = "demo_session_id"


def ensure_demo_session(
    client: HttpClient | InProcessClient,
    session_state: MutableMapping[str, Any] | SessionStateProxy,
    app_mode: AppMode | None = None,
) -> str | None:
    """Mint the demo principal once per browser session and re-attach it on
    every rerun (``build_homelib_client`` returns a fresh client each time).

    In ``selfhosted`` the header is meaningless to the server, so the client is
    explicitly cleared — a leaked ``APP_MODE=demo`` cannot make it send one.
    """
    mode = read_app_mode() if app_mode is None else app_mode
    if mode is not AppMode.DEMO:
        client.set_demo_session(None)
        return None
    raw = session_state.get(DEMO_SESSION_KEY)
    session_id = str(raw) if raw else client.create_demo_session()
    session_state[DEMO_SESSION_KEY] = session_id
    client.set_demo_session(session_id)
    return session_id


def persist_demo_session(
    client: HttpClient | InProcessClient,
    session_state: MutableMapping[str, Any] | SessionStateProxy,
) -> None:
    """Write a reminted demo id back to session state once the doors have run.

    ``ApiClient._request`` mints a fresh session on a 401 (server restart, TTL
    sweep) and uses it for the rest of the run — but the next rerun re-attaches
    whatever ``ensure_demo_session`` stored. Without this write-back the stale
    id is sent again, 401s again, and every rerun lands on a brand-new
    principal: the Coffee Table empties after each click. Call it after
    rendering, in ``finally``, so a door that raised still hands the fresh id on.
    """
    current = client.demo_session_id
    if current and session_state.get(DEMO_SESSION_KEY) != current:
        session_state[DEMO_SESSION_KEY] = current


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
    reason = getattr(response, "degraded_reason", None) or ""
    if reason == "citation_mismatch":
        return "No verified answer: the model's quote didn't match the source text."
    if reason == "uncited_claim":
        return "No verified answer: the model claimed a fact without a passage citation."
    if reason == "rate_limited":
        return "No verified answer: the language model is rate-limited right now."
    if reason == "llm_unreachable":
        return "No verified answer: the language model could not be reached."
    if reason == "malformed_llm_output":
        return "No verified answer: the model returned an unusable response."
    return "No verified answer could be produced from the shelf right now."


def format_degraded_trace_caption(response: AskResponse) -> str | None:
    """Diagnostics line for a degraded ask — arm + reason code for the caption row."""
    if not response.degraded:
        return None
    reason = getattr(response, "degraded_reason", None) or "degraded"
    return f"trace: arm={response.arm_used} · reason={reason}"


def format_discover_link_markdown(
    items: list[Mapping[str, Any]] | None,
    *,
    limit: int = 5,
) -> str:
    """Lawful catalog links for Ask refuse / Mentor abstain (ADR-008).

    Renders metadata + provider URLs only — never claims remote full text as
    local corpus. Empty/missing items → empty string (caller skips render).
    """
    if not items:
        return ""
    lines = [
        "Lawful catalog sources (open the link; HomeLib does not ingest "
        "these into the Ask reading shelf):"
    ]
    shown = 0
    for raw in items:
        if shown >= limit:
            break
        if not isinstance(raw, Mapping):
            continue
        url = str(raw.get("provider_url") or "").strip()
        if not url:
            continue
        title = str(raw.get("title") or "").strip() or "Untitled"
        authors = raw.get("authors") or []
        author_bit = ""
        if isinstance(authors, list) and authors:
            author_bit = " — " + ", ".join(str(a) for a in authors if a)
        lines.append(f"- **{title}**{author_bit} · [Open lawful source]({url})")
        shown += 1
    if shown == 0:
        return ""
    return "\n".join(lines)


def format_library_summary_line(summary: LibrarySummary) -> str:
    """One-line Shelf / Ask inventory readout."""
    return (
        f"{summary.book_count} books · {summary.total_blocks} blocks · "
        f"{summary.total_chunks} chunks"
    )


def needs_ask_shelf_fallback(answer: str) -> bool:
    """True when Ask should fetch shelf counts / next-step help.

    Empty bodies and non-empty passage abstentions both hide useful next
    actions unless the UI appends inventory context.
    """
    text = answer.strip()
    if not text:
        return True
    lowered = text.lower()
    markers = (
        "passages do not answer",
        "none of the provided passages",
        "none of the passages",
        "don't have information",
        "do not have information",
        "cannot answer",
        "not enough information",
        "no relevant passage",
    )
    return any(m in lowered for m in markers)


def format_ask_answer_body(answer: str, summary: LibrarySummary | None = None) -> str:
    """Never-blank Ask body. Empty LLM answers and passage abstentions get an
    explicit refuse line plus optional shelf counts — ``st.write("")`` is
    invisible and looks like a dead door; a lone abstention hides next steps.
    """
    text = answer.strip()
    if text and not needs_ask_shelf_fallback(text):
        return text
    lines: list[str] = []
    if text:
        lines.append(text)
    else:
        lines.append(
            "The shelf passages do not answer that. Try a question about a book "
            "on the shelf (for example: Who wrote Walden?)."
        )
    if summary is not None and summary.book_count > 0:
        lines.append(
            f"This shelf currently has {summary.book_count} books · "
            f"{summary.total_blocks} blocks · {summary.total_chunks} chunks."
        )
        lines.append("Ask what is on the shelf, or a question about a title listed there.")
    return "\n\n".join(lines)


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
    """Citation location without pretending page metadata exists for TXT."""
    parts = [citation.book_title]
    if citation.section_path:
        parts.append(" / ".join(citation.section_path))
    if citation.page is not None:
        parts.append(f"page {citation.page}")
    elif not citation.section_path:
        parts.append("source block")
    return " · ".join(parts)


def ask_metric_captions(ask: AskResponse) -> list[str]:
    """Session-scoped Ask monitoring lines (latency, tokens, cache, trace).

    Uses only fields on ``AskResponse`` — never durable ``answer_log`` plaintext.
    USD cost lives on Observatory / ``query_log.cost_usd`` when
    ``LLM_PRICE_PER_1K_*`` is set; the Ask door shows token counts always.
    """
    lines = [f"latency: {ask.latency_ms} ms"]
    prompt = ask.tokens.prompt
    completion = ask.tokens.completion
    lines.append(f"tokens: {prompt} prompt + {completion} completion = {prompt + completion}")
    if ask.cache_hit:
        lines.append("served from cache")
    if ask.trace_id:
        lines.append(f"trace: {ask.trace_id}")
    degraded_trace = format_degraded_trace_caption(ask)
    if degraded_trace is not None:
        lines.append(degraded_trace)
    return lines


def format_scene_hit_label(
    *,
    book_title: str,
    authors: list[str],
    section_path: list[str],
    page: int | None,
    ordinal: int,
) -> str:
    """Shelf scene-search line: book · author · section · page (or passage N for txt)."""
    author = ", ".join(authors) if authors else "—"
    section = " / ".join(section_path) if section_path else "—"
    place = f"page {page}" if page is not None else f"passage {ordinal + 1}"
    return f"{book_title} · {author} · {section} · {place}"


def display_step_order(order: object) -> str:
    """Render plan/roadmap step order as 1-based for visitors (audit W07)."""
    if isinstance(order, bool) or not isinstance(order, int):
        try:
            order = int(str(order))
        except (TypeError, ValueError):
            return "?" if order is None else str(order)
    return str(order + 1)


def projection_resume_book_index(
    books: Sequence[BookSummary],
    *,
    pending_book_id: str | None,
    saved_resource_id: str | None,
) -> int:
    """Choose Projection selectbox index: handoff wins, else last-read (audit S03)."""
    target = pending_book_id or saved_resource_id
    if not target:
        return 0
    for idx, book in enumerate(books):
        if book.book_id == target:
            return idx
    return 0


def resolve_shelf_resource_ids(
    shelf_items: Sequence[Mapping[str, Any]],
    *,
    titles: Sequence[str] = (),
    book_ids: Sequence[str] = (),
) -> tuple[list[str], list[str]]:
    """Map plan step titles/book_ids to shelf resource ids (audit W03).

    Returns ``(resolved_ids, unresolved_labels)``. Prefer exact ``book_id``
    matches; otherwise casefold title equality against shelf rows. Does not
    invent resources for metadata-only catalog hits.
    """
    by_id = {
        str(item["id"]): item
        for item in shelf_items
        if isinstance(item, Mapping) and item.get("id")
    }
    title_to_id: dict[str, str] = {}
    for item_id, item in by_id.items():
        title = str(item.get("title") or "").strip().casefold()
        if title and title not in title_to_id:
            title_to_id[title] = item_id

    resolved: list[str] = []
    seen: set[str] = set()
    unresolved: list[str] = []

    for book_id in book_ids:
        rid = str(book_id).strip()
        if not rid:
            continue
        if rid in by_id and rid not in seen:
            resolved.append(rid)
            seen.add(rid)
        elif rid not in by_id:
            unresolved.append(rid)

    for title in titles:
        label = str(title).strip()
        if not label:
            continue
        match = title_to_id.get(label.casefold())
        if match is None:
            unresolved.append(label)
        elif match not in seen:
            resolved.append(match)
            seen.add(match)

    return resolved, unresolved


def format_shelf_read_markdown(read_hint: str, *, port: int) -> str:
    """Shelf hit link copy. Spaces around ``**`` are required or Streamlit
    glues 'host' onto the URL.
    """
    return f"Open at the same host **{read_hint}** (clean article / Listen to Page — port {port})."


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
    "Roadmap",
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


def format_playlist_item_line(item: Mapping[str, Any], titles: Mapping[str, str]) -> str:
    """Coffee Table row: one-based position, book title (or resource id), status."""
    resource_id = str(item.get("resource_id") or "")
    title = titles.get(resource_id) or resource_id or "—"
    ordinal = item.get("ordinal")
    position = ordinal + 1 if isinstance(ordinal, int) else "—"
    status = item.get("status") or "—"
    return f"{position}. {title} · {status}"


def playlist_item_can_accept(item: Mapping[str, Any]) -> bool:
    """Only Mentor-proposed rows need an explicit acceptance action."""
    return item.get("status") == "proposed"


def format_book_choice_label(book: BookSummary) -> str:
    """Selectbox label for a shelf book — title, never the internal id."""
    return book.title or book.book_id


def observatory_chart_titles(payload: dict[str, Any]) -> list[str]:
    """Titles for Observatory charts, in API order."""
    charts = payload.get("charts") or []
    return [str(chart.get("title") or chart.get("id") or "") for chart in charts]


def observatory_bar_chart(points: Sequence[Mapping[str, Any]]) -> Any:
    """Altair bar chart with a finite y domain — no Vega Infinite-extent / bind.

    LIVE #51: ``st.bar_chart`` emitted Infinite extent for value_start/value_end
    and scale-binding warnings on Observatory. Explicit ordinal x + quantitative
    y with domainMin/domainMax keeps Vega stable; series colors p50/p95.
    """
    import altair as alt

    rows: list[dict[str, str | float]] = [
        {
            "bucket": str(point.get("bucket") or "—"),
            "value": float(point.get("value") or 0),
            "series": str(point.get("series") or "value"),
        }
        for point in points
    ]
    if not rows:
        rows = [{"bucket": "—", "value": 0.0, "series": "value"}]
    values = [float(row["value"]) for row in rows]
    y_max = max(values) if values else 1.0
    y_max = max(y_max, 1.0)
    # Group by series (p50/p95 share bucket="all") and disable stacking so
    # Vega does not invent value_start/value_end extents of ±Infinity.
    return (
        alt.Chart(alt.Data(values=rows))  # type: ignore[no-untyped-call]
        .mark_bar()
        .encode(
            x=alt.X("bucket:N", title="Bucket"),
            xOffset=alt.XOffset("series:N"),
            y=alt.Y(
                "value:Q",
                title="Value",
                scale=alt.Scale(domain=[0, y_max]),
                stack=None,
            ),
            color=alt.Color("series:N", title="Series", legend=alt.Legend()),
            tooltip=["bucket:N", "series:N", "value:Q"],
        )
        .properties(height=280)
    )


# Projection — This shelf vs Official preview (not a Crossroads door).
ProjectionSource = Literal["shelf", "official"]
ProjectionLanguage = Literal["en", "uk"]
# Demo default: shelf. Official preview (Pottermore Ukrainian HP) is opt-in via
# ?source=official — the public capstone/Cloud demo must not default to a
# publisher-hosted preview.
DEFAULT_PROJECTION_SOURCE: ProjectionSource = "shelf"
DEFAULT_OFFICIAL_LANGUAGE: ProjectionLanguage = "uk"
POTTERMORE_HOST = "www.pottermorepublishing.com"

# Opt-in two-page viewer + /pdf proxy on :8502. Off by default: the public
# demo (Streamlit Cloud) has no :8502 companion and the capstone repo ships
# publisher links only; the owner enables it in .env on the LAN box.
OFFICIAL_VIEWER_ENV = "HOMELIB_OFFICIAL_VIEWER"
DEFAULT_READ_PORT = 8502


def official_viewer_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """True only when ``HOMELIB_OFFICIAL_VIEWER`` is explicitly on."""
    env = os.environ if environ is None else environ
    return (env.get(OFFICIAL_VIEWER_ENV) or "").strip().lower() in {"1", "true", "yes", "on"}


def official_preview_caption(*, projector: bool, viewer_enabled: bool) -> str:
    """User-facing caption under the official preview stage (audit W08)."""
    if projector:
        return (
            "Tap Reading / Listen for Ukrainian text (Safari Speak Screen / Listen to Page). "
            "Prev/Next turns the open book on this stage."
        )
    if viewer_enabled:
        return (
            "Enter projector mode for the internal two-page book and Reading / Listen. "
            "Or open the Pottermore PDF / HTML reader above."
        )
    return (
        "Open the Pottermore PDF or HTML reader above. "
        "Reading / Listen appear when the internal viewer is enabled."
    )


def read_port(environ: Mapping[str, str] | None = None) -> int:
    """Companion :8502 port for links (``READ_PORT``; default 8502; bad → default)."""
    env = os.environ if environ is None else environ
    raw = (env.get("READ_PORT") or "").strip()
    if not raw:
        return DEFAULT_READ_PORT
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_READ_PORT


POTTERMORE_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "pottermore_uk_hp_preview.json"
)


def is_allowlisted_official_url(url: str) -> bool:
    """``https://`` + exact (lower-cased) ``POTTERMORE_HOST`` — no substring match.

    A substring check (``POTTERMORE_HOST not in url``) would let a lookalike
    host through (``www.pottermorepublishing.com.evil.tld``) or a spoof in the
    query string (``https://evil.example/?x=www.pottermorepublishing.com``).
    """
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "") == POTTERMORE_HOST


def normalize_projection_source(value: str | None) -> ProjectionSource:
    """Missing/empty → ``DEFAULT_PROJECTION_SOURCE``; unknown → shelf (fail-closed)."""
    if value is None or value == "":
        return DEFAULT_PROJECTION_SOURCE
    if value == "official":
        return "official"
    if value == "shelf":
        return "shelf"
    return "shelf"


def normalize_official_language(value: str | None) -> ProjectionLanguage:
    """Official-preview language; unknown → Ukrainian (demo default)."""
    if value == "en":
        return "en"
    return "uk"


@dataclass(frozen=True)
class OfficialPreviewBook:
    id: str
    title: str
    authors: tuple[str, ...]
    reader_url: str
    pdf_url: str


def load_official_preview_books(
    language: ProjectionLanguage,
    *,
    fixture_path: Path | None = None,
) -> list[OfficialPreviewBook]:
    """Metadata-only publisher previews. English has none yet; Ukrainian = Pottermore HP."""
    if language != "uk":
        return []
    path = fixture_path if fixture_path is not None else POTTERMORE_FIXTURE_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    books: list[OfficialPreviewBook] = []
    for entry in raw.get("books") or []:
        reader = str(entry["reader_url"])
        pdf = str(entry["pdf_url"])
        if not is_allowlisted_official_url(reader) or not is_allowlisted_official_url(pdf):
            raise ValueError(f"official preview URL host must be {POTTERMORE_HOST}")
        authors = entry.get("authors") or []
        books.append(
            OfficialPreviewBook(
                id=str(entry["id"]),
                title=str(entry["title"]),
                authors=tuple(str(a) for a in authors),
                reader_url=reader,
                pdf_url=pdf,
            )
        )
    return books


def projection_wants_chrome_hidden(
    *,
    projector_mode: bool,
    query_projection: str | None,
) -> bool:
    """Explicit projector only — never infer from viewport (AirPlay reports iPad size)."""
    if projector_mode:
        return True
    return query_projection in {"1", "true", "yes"}


def clean_read_url(book_id: str, *, ordinal: int = 0, read_port: int = 8502) -> str:
    """Relative hint for the clean article page (LAN host is the Streamlit host)."""
    return f":{read_port}/read/{book_id}?ordinal={int(ordinal)}"


def build_official_preview_stage_html(
    book: OfficialPreviewBook,
    *,
    projector: bool = False,
    read_port: int = 8502,
    viewer_enabled: bool | None = None,
) -> str:
    """16:9 Official preview stage.

    ``viewer_enabled`` gates the internal two-page viewer: ``None`` resolves it
    via ``official_viewer_enabled()`` (the owner's LAN opt-in). When the viewer
    is NOT enabled, both projector and non-projector modes return the
    links-only stage — the public capstone/Cloud demo must never emit
    ``:8502``/``/book/``/``location.assign``. Only when the viewer is enabled
    AND ``projector`` is True does this embed our ``:{{read_port}}/book/{{id}}``
    two-page spread (allowlisted PDF proxy — Pottermore sets X-Frame-Options so
    their URL cannot be iframed). CTAs use real ``<a href>`` / same-tab
    ``location.assign`` (iPad-safe; no ``window.open``). Never ingests PDF
    bytes (ADR-008).
    """
    enabled = official_viewer_enabled() if viewer_enabled is None else viewer_enabled
    title = html.escape(book.title)
    authors = html.escape(", ".join(book.authors))
    pdf_href = html.escape(book.pdf_url, quote=True)
    reader_href = html.escape(book.reader_url, quote=True)
    book_id_js = json.dumps(book.id)
    port_js = json.dumps(int(read_port))
    font = "1.35rem" if projector else "1.15rem"

    if projector and enabled:
        return f"""
<div style="width:100%;border:1px solid #cab995;border-radius:12px;overflow:hidden;
 background:#1a140c;box-sizing:border-box;color:#fffaf0;
 font-family:Georgia,'Times New Roman',serif;font-size:{font}">
  <div style="padding:0.75rem 1rem 0.35rem">
    <p style="margin:0;font-size:0.85rem;color:#d4c4a8">
      Official preview · open book · metadata only
    </p>
    <h2 style="margin:0.2rem 0 0;font-weight:500;font-size:1.25em">{title}</h2>
    <p style="margin:0.2rem 0 0.75rem;color:#d4c4a8">{authors}</p>
  </div>
  <iframe id="hl-official-book" title="{title}"
    style="width:100%;aspect-ratio:16/9;min-height:420px;border:0;background:#1a140c"
    allow="fullscreen"></iframe>
  <p style="margin:0;padding:0.75rem 1rem;display:flex;flex-wrap:wrap;gap:0.75rem;
   font-family:system-ui,sans-serif;font-size:0.95rem">
    <button type="button" id="hl-official-read"
      style="font:inherit;padding:0.65rem 1.1rem;min-height:44px;cursor:pointer;
       background:#e2b85f;color:#1a140c;border:0;border-radius:8px;font-weight:600">
      Reading / Listen
    </button>
    <a id="hl-official-book-link" href="#"
      style="padding:0.65rem 1.1rem;min-height:44px;display:inline-flex;align-items:center;
       text-decoration:none;background:#8a5b13;color:#fffaf0;border-radius:8px">
      Open book (Prev/Next)
    </a>
    <a href="{pdf_href}" target="_blank" rel="noopener noreferrer"
      style="padding:0.65rem 1.1rem;min-height:44px;display:inline-flex;align-items:center;
       text-decoration:none;background:transparent;color:#e2b85f;border:1px solid #8a5b13;
       border-radius:8px">Publisher PDF</a>
  </p>
  <p style="margin:0;padding:0 1rem 1rem;font:0.9rem system-ui,sans-serif;color:#d4c4a8">
    Tap <strong>Reading / Listen</strong> for Ukrainian text (Safari Speak Screen / Listen to Page).
    Use Prev/Next in the book for a two-page spread.
  </p>
  <script>
  (function () {{
    var id = {book_id_js};
    var port = {port_js};
    var url = location.protocol + "//" + location.hostname + ":" + port
      + "/book/" + encodeURIComponent(id);
    var readUrl = url + "?read=1";
    var frame = document.getElementById("hl-official-book");
    var link = document.getElementById("hl-official-book-link");
    var readBtn = document.getElementById("hl-official-read");
    if (frame) frame.src = url;
    if (link) link.href = url;
    if (readBtn) {{
      readBtn.onclick = function () {{ location.assign(readUrl); }};
    }}
  }})();
  </script>
</div>
"""

    # Non-projector keeps the original explanatory copy; projector drops the
    # (now-nonexistent, viewer-disabled) "enter projector mode for the
    # internal two-page book" sentence in favour of naming what actually
    # happens: publisher pages open in a new tab, Safari Listen to Page there.
    if projector:
        speech = (
            "<p style='margin:0 0 1.25rem'>Publisher pages refuse iframes, so they open in a "
            "new tab. Safari Listen to Page / Speak Screen works there.</p>"
        )
    else:
        speech = (
            "<p style='margin:0 0 1.25rem'>Publisher pages refuse iframes. Open the lawful "
            "Ukrainian PDF or HTML reader, then use Safari Listen to Page / Speak Screen.</p>"
        )
    footer = (
        '<p style="margin:1rem 0 0;font-size:0.9rem;color:#5c4a3a">'
        "Publisher pages open in a new tab; Safari Listen to Page works there.</p>"
    )
    primary = (
        f"<a href='{pdf_href}' target='_blank' rel='noopener noreferrer' "
        f"style='font:inherit;font-size:1em;padding:0.65rem 1.1rem;min-height:44px;"
        f"display:inline-flex;align-items:center;text-decoration:none;"
        f"background:#8a5b13;color:#fffaf0;border-radius:8px'>"
        f"Open Ukrainian PDF</a>"
    )
    secondary = (
        f"<a href='{reader_href}' target='_blank' rel='noopener noreferrer' "
        f"style='font:inherit;font-size:1em;padding:0.65rem 1.1rem;min-height:44px;"
        f"display:inline-flex;align-items:center;text-decoration:none;"
        f"background:transparent;color:#8a5b13;border:1px solid #8a5b13;"
        f"border-radius:8px'>"
        f"Open HTML reader</a>"
    )
    return f"""
<div style="aspect-ratio:16/9;width:100%;border:1px solid #cab995;border-radius:12px;
 overflow:auto;background:#fffaf0;padding:1.5rem;box-sizing:border-box;font-size:{font};
 line-height:1.55;color:#241c16;font-family:Georgia,'Times New Roman',serif">
  <p style="margin:0 0 0.35rem;font-size:0.85rem;color:#5c4a3a">
    Official preview · Pottermore Publishing · metadata only
  </p>
  <h2 style="margin:0 0 0.35rem;font-weight:500;font-size:1.35em">{title}</h2>
  <p style="margin:0 0 1rem;color:#5c4a3a">{authors}</p>
  {speech}
  <p style="margin:0;display:flex;flex-wrap:wrap;gap:0.75rem">
    {primary}
    {secondary}
  </p>
  {footer}
</div>
"""
