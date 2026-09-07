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
from collections.abc import Mapping, MutableMapping
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
    return lines


def format_scene_hit_label(
    *,
    book_title: str,
    authors: list[str],
    section_path: list[str],
    page: int | None,
    ordinal: int,
) -> str:
    """Shelf scene-search line: book · author · section · page (or block N for txt)."""
    author = ", ".join(authors) if authors else "—"
    section = " / ".join(section_path) if section_path else "—"
    place = f"page {page}" if page is not None else f"block {ordinal + 1}"
    return f"{book_title} · {author} · {section} · {place}"


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
    """Coffee Table row: ordinal, book title (or resource id), status."""
    resource_id = str(item.get("resource_id") or "")
    title = titles.get(resource_id) or resource_id or "—"
    ordinal = item.get("ordinal")
    status = item.get("status") or "—"
    return f"{ordinal} {title} · {status}"


def format_book_choice_label(book: BookSummary) -> str:
    """Selectbox label for a shelf book — title, never the internal id."""
    return book.title or book.book_id


def observatory_chart_titles(payload: dict[str, Any]) -> list[str]:
    """Titles for Observatory charts, in API order."""
    charts = payload.get("charts") or []
    return [str(chart.get("title") or chart.get("id") or "") for chart in charts]


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
