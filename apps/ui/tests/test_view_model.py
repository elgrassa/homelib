"""Behavioural tests for apps/ui/view_model.py.

These drive the pure helper functions directly — no Streamlit runtime, no
running API, no database, no browser — per specs/ui.md's named red tests and
the architectural invariant that the UI never touches the database or any
internal package directly.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apps.ui.api_client import (
    ApiClientError,
    ApiUnavailableError,
    AskResponse,
    BookSummary,
    Citation,
    RoadmapStep,
    TokenUsage,
)
from apps.ui.view_model import (
    CROSSROADS_DOORS,
    DEFAULT_API_URL,
    LibrarySummary,
    block_id_for_citation,
    format_api_error_message,
    format_ask_answer_body,
    needs_ask_shelf_fallback,
    format_citation_label,
    format_degraded_banner,
    get_api_url,
    has_voted,
    library_summary,
    normalize_door,
    normalize_level,
    observatory_chart_titles,
    parse_interests,
    playlist_visible_items,
    record_vote,
    resolve_prerequisite_titles,
    steps_in_order,
)

FORBIDDEN_MODULES = (
    "psycopg",
    "homelib_core",
    "homelib_rag",
    "sqlalchemy",
    "dlt",
    "sqlite3",
)
FORBIDDEN_MODULE_PREFIXES = ("apps.store",)


# --------------------------------------------------------------------------
# Test data builders.
# --------------------------------------------------------------------------


def _make_citation(
    *,
    chunk_id: str = "chunk-1",
    book_title: str = "Walden",
    section_path: list[str] | None = None,
    page: int | None = 12,
) -> Citation:
    return Citation(
        chunk_id=chunk_id,
        book_id="book-1",
        book_title=book_title,
        section_path=["Economy"] if section_path is None else section_path,
        page=page,
        quote="a quote",
    )


def _make_ask_response(*, degraded: bool, arm_used: str = "hybrid_rerank") -> AskResponse:
    return AskResponse(
        request_id="req-1",
        answer="an answer",
        citations=[_make_citation()],
        arm_used=arm_used,
        degraded=degraded,
        latency_ms=100,
        tokens=TokenUsage(prompt=10, completion=20),
    )


def _make_step(
    *,
    order: int,
    title: str,
    prerequisites: list[int] | None = None,
) -> RoadmapStep:
    return RoadmapStep(
        order=order,
        ol_key=None,
        book_id="book-1",
        title=title,
        authors=["An Author"],
        why="because",
        prerequisites=[] if prerequisites is None else prerequisites,
        est_effort="light",
    )


def _make_book(*, blocks: int, chunks: int) -> BookSummary:
    return BookSummary(
        book_id=f"book-{blocks}-{chunks}",
        title="A Book",
        authors=["An Author"],
        blocks=blocks,
        chunks=chunks,
        format="epub",
    )


# --------------------------------------------------------------------------
# Architectural invariant: no DB / internal-package imports anywhere in
# apps/ui, enforced statically over the actual source tree.
# --------------------------------------------------------------------------


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_ui_never_imports_database_or_internal_packages() -> None:
    ui_dir = Path(__file__).resolve().parent.parent
    offending: dict[str, set[str]] = {}
    for path in sorted(ui_dir.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        imported = _imported_modules(tree)
        hits: set[str] = set()
        for mod in imported:
            root = mod.split(".")[0]
            if root in FORBIDDEN_MODULES or mod in FORBIDDEN_MODULES:
                hits.add(mod)
            if any(mod == p or mod.startswith(p + ".") for p in FORBIDDEN_MODULE_PREFIXES):
                hits.add(mod)
        if hits:
            offending[str(path)] = hits
    assert not offending, f"forbidden imports found under apps/ui: {offending}"


def test_ui_boundary_forbids_store_and_provider_imports() -> None:
    """Named red from specs/client.md — alias of the AST walk above."""
    test_ui_never_imports_database_or_internal_packages()


def test_crossroads_doors_cover_thin_e2e_journey() -> None:
    """Crossroads → Ask (Wing) → Mentor → Roadmap → Coffee Table → Projection."""
    assert "Ask" in CROSSROADS_DOORS
    assert "Mentor" in CROSSROADS_DOORS
    assert "Roadmap" in CROSSROADS_DOORS
    assert "Coffee Table" in CROSSROADS_DOORS
    assert "Projection" in CROSSROADS_DOORS
    assert "Rotunda" not in CROSSROADS_DOORS
    app_src = (Path(__file__).resolve().parent.parent / "app.py").read_text()
    assert "render_projection_tab" in app_src
    assert "Enter projector mode" in app_src
    assert "Official preview" in app_src
    assert "MagicLib" in app_src


def test_every_door_has_a_renderer_and_vice_versa() -> None:
    """The door grid and the dispatch table are the same set — no unreachable
    renderer (Roadmap was built and never wired) and no door that renders
    nothing. Behavioural: reads the table, not the source text."""
    from apps.ui.app import DOOR_RENDERERS

    assert set(DOOR_RENDERERS) == set(CROSSROADS_DOORS)
    assert list(DOOR_RENDERERS) == list(CROSSROADS_DOORS)
    for door, renderer in DOOR_RENDERERS.items():
        assert callable(renderer), door


# --------------------------------------------------------------------------
# Degraded-answer banner.
# --------------------------------------------------------------------------


def test_degraded_response_renders_banner() -> None:
    degraded = _make_ask_response(degraded=True, arm_used="lexical")

    banner = format_degraded_banner(degraded)

    assert banner == "Answered with a degraded backend: lexical"


def test_healthy_response_has_no_banner() -> None:
    healthy = _make_ask_response(degraded=False)

    assert format_degraded_banner(healthy) is None


def test_ask_answer_body_refuses_when_llm_returns_empty() -> None:
    """Inventory questions often get answer=\"\" — that must not render blank."""
    body = format_ask_answer_body(
        "", LibrarySummary(book_count=18, total_blocks=729, total_chunks=9168)
    )
    assert "do not answer" in body.lower()
    assert "18 books" in body
    assert "what is on the shelf" in body.lower()
    assert format_ask_answer_body("Henry David Thoreau", None) == "Henry David Thoreau"


def test_ask_answer_body_appends_shelf_help_for_nonempty_abstention() -> None:
    """Non-empty passage abstentions must still show shelf counts / next action."""
    abstention = "None of the provided passages answer this question."
    assert needs_ask_shelf_fallback(abstention) is True
    body = format_ask_answer_body(
        abstention, LibrarySummary(book_count=18, total_blocks=729, total_chunks=9168)
    )
    assert abstention in body
    assert "18 books" in body
    assert "what is on the shelf" in body.lower()
    assert needs_ask_shelf_fallback("Henry David Thoreau") is False


# --------------------------------------------------------------------------
# Double-vote prevention.
# --------------------------------------------------------------------------


def test_double_vote_is_prevented() -> None:
    feedback_sent: set[str] = set()
    assert has_voted(feedback_sent, "req-1") is False

    feedback_sent = record_vote(feedback_sent, "req-1")
    assert has_voted(feedback_sent, "req-1") is True

    # A second attempt to record the same vote must not create a duplicate
    # or otherwise change the outcome — the UI disables the button once
    # has_voted is True, so this models "what if it were called anyway".
    feedback_sent = record_vote(feedback_sent, "req-1")
    assert feedback_sent == {"req-1"}


def test_vote_on_one_request_id_does_not_affect_another() -> None:
    feedback_sent = record_vote(set(), "req-1")

    assert has_voted(feedback_sent, "req-2") is False


# --------------------------------------------------------------------------
# Roadmap ordering + prerequisite title resolution.
# --------------------------------------------------------------------------


def test_roadmap_steps_render_in_order() -> None:
    steps = [
        _make_step(order=3, title="C"),
        _make_step(order=1, title="A"),
        _make_step(order=2, title="B"),
    ]

    ordered = steps_in_order(steps)

    assert [step.order for step in ordered] == [1, 2, 3]
    assert [step.title for step in ordered] == ["A", "B", "C"]


def test_resolve_prerequisite_titles_uses_titles_not_integers() -> None:
    steps = [
        _make_step(order=1, title="Basics", prerequisites=[]),
        _make_step(order=2, title="Intermediate", prerequisites=[1]),
        _make_step(order=3, title="Advanced", prerequisites=[1, 2]),
    ]

    titles = resolve_prerequisite_titles(steps)

    assert titles[1] == []
    assert titles[2] == ["Basics"]
    assert titles[3] == ["Basics", "Intermediate"]


# --------------------------------------------------------------------------
# Library tab summary.
# --------------------------------------------------------------------------


def test_library_tab_summary_matches_book_list() -> None:
    books = [
        _make_book(blocks=10, chunks=4),
        _make_book(blocks=20, chunks=8),
        _make_book(blocks=5, chunks=1),
    ]

    summary = library_summary(books)

    assert summary.book_count == 3
    assert summary.total_blocks == sum(book.blocks for book in books) == 35
    assert summary.total_chunks == sum(book.chunks for book in books) == 13


def test_library_tab_summary_of_empty_list_is_zeroed() -> None:
    summary = library_summary([])

    assert summary == library_summary([])
    assert summary.book_count == 0
    assert summary.total_blocks == 0
    assert summary.total_chunks == 0


# --------------------------------------------------------------------------
# Error message formatting — readable, never a stack trace.
# --------------------------------------------------------------------------


def test_format_api_error_message_for_unreachable_backend() -> None:
    exc = ApiUnavailableError("connection refused")

    message = format_api_error_message(exc)

    assert "unreachable" in message
    assert "connection refused" in message


def test_format_api_error_message_for_4xx_response() -> None:
    exc = ApiClientError("block not found", status_code=404)

    message = format_api_error_message(exc)

    assert "404" in message
    assert "block not found" in message


# --------------------------------------------------------------------------
# Small remaining helpers.
# --------------------------------------------------------------------------


def test_parse_interests_splits_and_strips_and_drops_empties() -> None:
    assert parse_interests(" stoicism, discipline ,, business ") == [
        "stoicism",
        "discipline",
        "business",
    ]


def test_parse_interests_on_empty_string_is_empty_list() -> None:
    assert parse_interests("") == []


def test_format_citation_label_includes_book_section_and_page() -> None:
    citation = _make_citation(book_title="Walden", section_path=["Economy"], page=12)

    assert format_citation_label(citation) == "Walden · Economy · page 12"


def test_format_citation_label_handles_missing_page_and_section() -> None:
    citation = _make_citation(book_title="Walden", section_path=[], page=None)

    assert format_citation_label(citation) == "Walden · — · page —"


def test_format_scene_hit_label_includes_book_author_section_and_page() -> None:
    from apps.ui.view_model import format_scene_hit_label

    label = format_scene_hit_label(
        book_title="Acres of Diamonds",
        authors=["Russell H. Conwell"],
        section_path=["Chapter I"],
        page=12,
        ordinal=3,
    )
    assert label == "Acres of Diamonds · Russell H. Conwell · Chapter I · page 12"


def test_format_scene_hit_label_falls_back_to_block_when_page_missing() -> None:
    """Gutenberg txt blocks have no Provenance.page — show block ordinal instead."""
    from apps.ui.view_model import format_scene_hit_label

    label = format_scene_hit_label(
        book_title="Acres of Diamonds",
        authors=["Russell H. Conwell"],
        section_path=[],
        page=None,
        ordinal=4,
    )
    assert label == "Acres of Diamonds · Russell H. Conwell · — · block 5"


def test_format_shelf_read_markdown_keeps_space_before_bold_url() -> None:
    from apps.ui.view_model import format_shelf_read_markdown

    line = format_shelf_read_markdown("http://127.0.0.1:8502/read/walden", port=8502)
    assert "host **" in line
    assert "host**" not in line
    assert "http://127.0.0.1:8502/read/walden" in line


def test_ask_metric_captions_include_latency_and_token_breakdown() -> None:
    from apps.ui.view_model import ask_metric_captions

    ask = _make_ask_response(degraded=False).model_copy(
        update={
            "latency_ms": 1234,
            "tokens": TokenUsage(prompt=90, completion=10),
            "trace_id": "abc",
        }
    )
    lines = ask_metric_captions(ask)
    assert lines[0] == "latency: 1234 ms"
    assert lines[1] == "tokens: 90 prompt + 10 completion = 100"
    assert "trace: abc" in lines
    assert "served from cache" not in lines


def test_ask_metric_captions_mark_cache_hit() -> None:
    from apps.ui.view_model import ask_metric_captions

    ask = _make_ask_response(degraded=False).model_copy(update={"cache_hit": True})
    assert "served from cache" in ask_metric_captions(ask)


def test_block_id_for_citation_uses_the_block_id_not_the_chunk_id() -> None:
    """`/v1/blocks/{id}` is keyed on block ids; a chunk_id 404s there.

    The previous version of this test asserted the chunk_id was returned, and
    passed happily while the "show full source" button was broken end to end.
    A test can only be as right as the contract it encodes.
    """
    citation = _make_citation(chunk_id="chunk-42")
    citation.block_id = "blk-7"

    assert block_id_for_citation(citation) == "blk-7"


def test_normalize_level_accepts_every_known_level() -> None:
    for level in ("beginner", "intermediate", "advanced"):
        assert normalize_level(level) == level


def test_normalize_level_rejects_an_unknown_value() -> None:
    # st.selectbox hands back a plain str, so a typo or a widget key collision
    # would otherwise flow straight into the API request body unchecked.
    try:
        normalize_level("expert")
    except ValueError as exc:
        assert "expert" in str(exc)
    else:  # pragma: no cover - the assert below is the real failure message
        raise AssertionError("normalize_level accepted an unknown level")


def test_get_api_url_defaults_to_localhost(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("API_URL", raising=False)

    assert get_api_url() == DEFAULT_API_URL


def test_get_api_url_honours_the_environment(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("API_URL", "http://api:8000")

    assert get_api_url() == "http://api:8000"


def test_normalize_door_accepts_crossroads_labels() -> None:
    for door in CROSSROADS_DOORS:
        assert normalize_door(door) == door


def test_normalize_door_rejects_unknown() -> None:
    try:
        normalize_door("Rotunda")
    except ValueError as exc:
        assert "Rotunda" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("normalize_door accepted an unknown door")


def test_playlist_visible_items_skips_removed() -> None:
    visible = playlist_visible_items(
        {
            "items": [
                {"id": "a", "status": "queued"},
                {"id": "b", "status": "removed"},
            ]
        }
    )
    assert [i["id"] for i in visible] == ["a"]


def test_observatory_chart_titles_preserve_order() -> None:
    titles = observatory_chart_titles(
        {"charts": [{"title": "A", "id": "a"}, {"id": "b"}, {"title": "C"}]}
    )
    assert titles == ["A", "b", "C"]


# ── H3: demo session minted once per browser session, re-attached per rerun ──


class _SessionFake:
    def __init__(self) -> None:
        self.mints = 0
        self.set_calls: list[str | None] = []

    def create_demo_session(self) -> str:
        self.mints += 1
        return f"sess-{self.mints}"

    def set_demo_session(self, session_id: str | None) -> None:
        self.set_calls.append(session_id)


def test_ensure_demo_session_mints_once_and_reuses_state() -> None:
    from apps.runtime_settings import AppMode
    from apps.ui.view_model import DEMO_SESSION_KEY, ensure_demo_session

    fake = _SessionFake()
    state: dict[str, object] = {}
    first = ensure_demo_session(fake, state, AppMode.DEMO)  # type: ignore[arg-type]
    second = ensure_demo_session(fake, state, AppMode.DEMO)  # type: ignore[arg-type]
    assert first == second == "sess-1"
    assert fake.mints == 1
    assert state[DEMO_SESSION_KEY] == "sess-1"
    assert fake.set_calls == ["sess-1", "sess-1"]


def test_ensure_demo_session_is_a_noop_that_clears_in_selfhosted() -> None:
    from apps.runtime_settings import AppMode
    from apps.ui.view_model import DEMO_SESSION_KEY, ensure_demo_session

    fake = _SessionFake()
    state: dict[str, object] = {}
    assert ensure_demo_session(fake, state, AppMode.SELFHOSTED) is None  # type: ignore[arg-type]
    assert fake.mints == 0
    assert fake.set_calls == [None]
    assert DEMO_SESSION_KEY not in state


def test_persist_demo_session_keeps_a_reminted_id_for_the_next_rerun() -> None:
    """Server forgot the session (TTL sweep): the client remints on the 401,
    the fresh id must reach session state, and the next rerun must attach the
    fresh id — not the stale one — so the Coffee Table stays on one principal."""
    import httpx

    from apps.runtime_settings import AppMode
    from apps.ui.api_client import DEMO_SESSION_HEADER, HttpClient
    from apps.ui.view_model import DEMO_SESSION_KEY, ensure_demo_session, persist_demo_session

    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        header = request.headers.get(DEMO_SESSION_HEADER.lower())
        if request.url.path == "/v1/demo/session":
            return httpx.Response(200, json={"demo_session_id": "fresh", "principal_id": "p"})
        seen.append(header)
        if header == "stale":
            return httpx.Response(401, json={"detail": "unknown demo session"})
        return httpx.Response(200, json={"playlist_id": "p1", "items": []})

    def client() -> HttpClient:
        return HttpClient(
            "http://api", http_client=httpx.Client(transport=httpx.MockTransport(handler))
        )

    state: dict[str, object] = {DEMO_SESSION_KEY: "stale"}
    first = client()
    ensure_demo_session(first, state, AppMode.DEMO)
    first.get_playlist()
    persist_demo_session(first, state)
    assert state[DEMO_SESSION_KEY] == "fresh"

    second = client()
    ensure_demo_session(second, state, AppMode.DEMO)
    second.get_playlist()
    assert seen == ["stale", "fresh", "fresh"]
