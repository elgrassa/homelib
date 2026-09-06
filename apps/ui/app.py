"""Streamlit UI. Talks only to the public API, never to the database.

Rendering shell only — decisions live in ``view_model.py``.
WP08 thin e2e: Crossroads doors → Ask / Mentor / Coffee Table / Shelf /
Observatory / Projection.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Literal

import streamlit as st

from apps.ui.api_client import (
    ApiClient,
    ApiClientError,
    ApiUnavailableError,
    AskResponse,
    InProcessClient,
)
from apps.ui.rotunda import build_rotunda_html, door_from_query
from apps.ui.view_model import (
    CROSSROADS_DOORS,
    DEFAULT_OFFICIAL_LANGUAGE,
    DEFAULT_PROJECTION_SOURCE,
    LEVELS,
    apply_streamlit_secrets_to_environ,
    block_id_for_citation,
    build_homelib_client,
    build_official_preview_stage_html,
    clean_read_url,
    ensure_demo_session,
    format_api_error_message,
    format_citation_label,
    format_degraded_banner,
    has_voted,
    library_summary,
    load_official_preview_books,
    normalize_door,
    normalize_level,
    normalize_official_language,
    normalize_projection_source,
    observatory_chart_titles,
    parse_interests,
    persist_demo_session,
    playlist_visible_items,
    projection_wants_chrome_hidden,
    record_vote,
    resolve_prerequisite_titles,
    steps_in_order,
)

Client = ApiClient | InProcessClient


def render_ask_tab(client: Client) -> None:
    st.header("Ask")
    query = st.text_input("Ask your library a question", key="ask_query")
    k = st.slider("Number of results", min_value=1, max_value=10, value=5, key="ask_k")
    if st.button("Ask", key="ask_submit") and query.strip():
        try:
            response = client.ask(query, k=k)
        except (ApiClientError, ApiUnavailableError) as exc:
            st.error(format_api_error_message(exc))
        else:
            st.session_state["last_ask"] = response

    last_ask: AskResponse | None = st.session_state.get("last_ask")
    if last_ask is None:
        return

    banner = format_degraded_banner(last_ask)
    if banner is not None:
        st.warning(banner)
    st.write(last_ask.answer)

    feedback_sent: set[str] = st.session_state.setdefault("feedback_sent", set())
    voted = has_voted(feedback_sent, last_ask.request_id)
    up_col, down_col = st.columns(2)
    with up_col:
        if st.button("👍", key=f"vote_up_{last_ask.request_id}", disabled=voted):
            _cast_vote(client, last_ask.request_id, "up")
    with down_col:
        if st.button("👎", key=f"vote_down_{last_ask.request_id}", disabled=voted):
            _cast_vote(client, last_ask.request_id, "down")

    for citation in last_ask.citations:
        with st.expander(format_citation_label(citation)):
            st.write(citation.quote)
            block_key = f"block_{citation.chunk_id}"
            if st.button("Show full source block", key=f"load_{block_key}"):
                try:
                    block = client.get_block(block_id_for_citation(citation))
                except (ApiClientError, ApiUnavailableError) as exc:
                    st.error(format_api_error_message(exc))
                else:
                    st.session_state[block_key] = block.text
            block_text = st.session_state.get(block_key)
            if block_text is not None:
                st.text(block_text)


def _cast_vote(client: Client, request_id: str, feedback: Literal["up", "down"]) -> None:
    try:
        client.submit_feedback(request_id, feedback)
    except (ApiClientError, ApiUnavailableError) as exc:
        st.error(format_api_error_message(exc))
    else:
        feedback_sent: set[str] = st.session_state.setdefault("feedback_sent", set())
        st.session_state["feedback_sent"] = record_vote(feedback_sent, request_id)


def render_mentor_tab(client: Client) -> None:
    st.header("Mentor")
    with st.form("mentor_form"):
        goal = st.text_input("Goal", key="mentor_goal")
        interests_raw = st.text_input("Interests (comma-separated)", key="mentor_interests")
        level = st.selectbox("Level", LEVELS, key="mentor_level")
        submitted = st.form_submit_button("Propose path")
    if submitted and goal.strip():
        try:
            response = client.mentor_intake(
                goal.strip(), parse_interests(interests_raw), normalize_level(level)
            )
        except (ApiClientError, ApiUnavailableError) as exc:
            st.error(format_api_error_message(exc))
        else:
            st.session_state["last_mentor"] = response

    last = st.session_state.get("last_mentor")
    if last is None:
        return
    if last.get("degraded"):
        st.warning("Mentor returned a degraded proposal.")
    if last.get("high_stakes_notice"):
        st.info(last["high_stakes_notice"])
    st.write(last.get("rationale") or "")
    path = last.get("proposed_path")
    if path:
        st.subheader(path.get("title") or "Proposed path")
        for step in path.get("steps") or []:
            st.write(f"{step.get('order', '?')}. {step.get('title', '')} — {step.get('why', '')}")


def render_coffee_table_tab(client: Client) -> None:
    st.header("Coffee Table")
    try:
        resources = client.list_resources()
        playlist = client.get_playlist()
    except (ApiClientError, ApiUnavailableError) as exc:
        st.error(format_api_error_message(exc))
        return

    items = playlist_visible_items(playlist)
    if items:
        for item in items:
            cols = st.columns([4, 1, 1])
            cols[0].write(
                f"`{item.get('ordinal')}` {item.get('resource_id')} · {item.get('status')}"
            )
            if cols[1].button(
                "Accept", key=f"acc_{item['id']}", disabled=item.get("status") != "proposed"
            ):
                try:
                    client.accept_playlist([item["id"]])
                    st.rerun()
                except (ApiClientError, ApiUnavailableError) as exc:
                    st.error(format_api_error_message(exc))
            if cols[2].button("Remove", key=f"rm_{item['id']}"):
                try:
                    client.remove_playlist_item(item["id"])
                    st.rerun()
                except (ApiClientError, ApiUnavailableError) as exc:
                    st.error(format_api_error_message(exc))
    else:
        st.write("Coffee Table is empty.")

    shelf = resources.get("items") or []
    if shelf:
        choice = st.selectbox(
            "Add from shelf",
            options=[r["id"] for r in shelf],
            format_func=lambda rid: next(
                (f"{r['title']} ({rid})" for r in shelf if r["id"] == rid), rid
            ),
            key="coffee_add_select",
        )
        if st.button("Add to Coffee Table", key="coffee_add"):
            try:
                client.add_playlist_item(choice)
                st.rerun()
            except (ApiClientError, ApiUnavailableError) as exc:
                st.error(format_api_error_message(exc))


def render_library_tab(client: Client) -> None:
    st.header("Shelf")
    try:
        books = client.list_books()
    except (ApiClientError, ApiUnavailableError) as exc:
        st.error(format_api_error_message(exc))
        return

    summary = library_summary(books)
    st.write(
        f"{summary.book_count} books · {summary.total_blocks} blocks · "
        f"{summary.total_chunks} chunks"
    )
    st.table(
        [
            {
                "title": book.title,
                "authors": ", ".join(book.authors),
                "blocks": book.blocks,
                "chunks": book.chunks,
                "format": book.format,
            }
            for book in books
        ]
    )

    st.subheader("Scene search")
    if not books:
        return
    book_id = st.selectbox("Book", options=[b.book_id for b in books], key="scene_book")
    scene_q = st.text_input("Open the scene where…", key="scene_q")
    if st.button("Search scenes", key="scene_go") and scene_q.strip():
        try:
            result = client.scene_search(book_id, scene_q.strip())
        except (ApiClientError, ApiUnavailableError) as exc:
            st.error(format_api_error_message(exc))
        else:
            for hit in result.get("hits") or []:
                st.write(f"**{hit.get('open_anchor')}** — {hit.get('quote', '')[:200]}")


def render_observatory_tab(client: Client) -> None:
    st.header("Observatory")
    try:
        payload = client.get_observatory()
    except (ApiClientError, ApiUnavailableError) as exc:
        st.error(format_api_error_message(exc))
        st.caption("Requires HOMELIB_SQLITE_PATH on the API.")
        return
    titles = observatory_chart_titles(payload)
    st.write(f"App mode: {payload.get('app_mode')} · {len(titles)} charts")
    for chart in payload.get("charts") or []:
        st.subheader(chart.get("title") or chart.get("id"))
        points = chart.get("points") or []
        if not points:
            st.write("(no data yet — run `uv run python scripts/demo_traffic.py --n 40`)")
            continue
        st.bar_chart(
            {
                "bucket": [p.get("bucket") for p in points],
                "value": [p.get("value") for p in points],
            },
            x="bucket",
            y="value",
        )


def render_projection_tab(client: Client) -> None:
    """WP09 projection: This shelf pages or Official Pottermore preview (demo default)."""
    if "projection_source" not in st.session_state:
        st.session_state["projection_source"] = DEFAULT_PROJECTION_SOURCE
    if "official_language" not in st.session_state:
        st.session_state["official_language"] = DEFAULT_OFFICIAL_LANGUAGE

    source = normalize_projection_source(str(st.session_state.get("projection_source", "")))
    st.session_state["projection_source"] = source

    source_label = st.radio(
        "Projector source",
        options=("official", "shelf"),
        format_func=lambda v: "Official preview" if v == "official" else "This shelf",
        index=0 if source == "official" else 1,
        horizontal=True,
        key="projection_source_radio",
    )
    st.session_state["projection_source"] = normalize_projection_source(source_label)
    source = st.session_state["projection_source"]

    projector = st.toggle("Enter projector mode", key="projector_mode")
    if projection_wants_chrome_hidden(
        projector_mode=projector,
        query_projection=st.query_params.get("projection"),
    ):
        st.markdown(
            "<style>"
            "header[data-testid='stHeader']{display:none!important}"
            "[data-testid='stToolbar']{display:none!important}"
            "#MainMenu{visibility:hidden}"
            "footer{visibility:hidden}"
            "</style>",
            unsafe_allow_html=True,
        )

    if source == "official":
        _render_official_preview(projector)
        return
    _render_shelf_projection(client, projector)


def _render_official_preview(projector: bool) -> None:
    st.caption("Preview on Pottermore Publishing — not on this shelf. Metadata only.")
    lang = st.selectbox(
        "Language",
        options=("uk", "en"),
        format_func=lambda v: "Ukrainian" if v == "uk" else "English",
        index=0 if st.session_state.get("official_language") == "uk" else 1,
        key="official_lang_select",
    )
    st.session_state["official_language"] = normalize_official_language(lang)
    books = load_official_preview_books(st.session_state["official_language"])
    if not books:
        st.info("No official previews in English yet. Switch to Ukrainian for Pottermore HP.")
        return
    book = st.selectbox(
        "Book",
        options=books,
        format_func=lambda b: b.title,
        key="official_book",
    )
    st.link_button("Open lawful source (new tab)", book.reader_url)
    # Publisher sets X-Frame-Options / CSP frame-ancestors — never iframe.
    # Click opens a named browser window (same target on re-click).
    st.html(
        build_official_preview_stage_html(book, projector=projector),
        unsafe_allow_javascript=True,
    )
    st.caption(
        "AirPlay mirrors this stage. Speech: open the reader window, then Safari "
        "Listen to Page (aA) or Speak Screen."
    )


def _render_shelf_projection(client: Client, projector: bool) -> None:
    st.header("Projection" if not projector else "")
    try:
        books = client.list_books()
    except (ApiClientError, ApiUnavailableError) as exc:
        st.error(format_api_error_message(exc))
        return
    if not books:
        st.write("No books on the shelf.")
        return
    # Never mix Pottermore titles into the shelf picker.
    book = st.selectbox(
        "Book",
        options=books,
        format_func=lambda b: b.title,
        key="proj_book",
    )
    ordinal = int(st.session_state.get("proj_ordinal", 0))
    cols = st.columns([1, 1, 2])
    with cols[0]:
        if st.button("Previous", key="proj_prev", use_container_width=True) and ordinal > 0:
            ordinal -= 1
    with cols[1]:
        if st.button("Next", key="proj_next", use_container_width=True):
            ordinal += 1
    st.session_state["proj_ordinal"] = ordinal

    try:
        block = client.get_book_block(book.book_id, ordinal=ordinal)
    except (ApiClientError, ApiUnavailableError) as exc:
        if ordinal > 0:
            st.session_state["proj_ordinal"] = max(0, ordinal - 1)
            st.warning("End of book — stepped back one page.")
            try:
                block = client.get_book_block(
                    book.book_id, ordinal=st.session_state["proj_ordinal"]
                )
            except (ApiClientError, ApiUnavailableError) as exc2:
                st.error(format_api_error_message(exc2))
                return
        else:
            st.error(format_api_error_message(exc))
            return

    if st.button("Save progress", key="proj_save"):
        try:
            client.save_progress(
                book.book_id, char_offset=block.char_start, block_id=block.block_id
            )
            st.success("Progress saved.")
        except (ApiClientError, ApiUnavailableError) as exc:
            st.error(format_api_error_message(exc))

    font = "2.2rem" if projector else "1.15rem"
    section = " / ".join(block.section_path) if block.section_path else ""
    st.markdown(
        f"<div style='font-size:{font};line-height:1.65;max-width:48rem;"
        f"aspect-ratio:16/9;padding:1.5rem;background:#fffaf0;border:1px solid #cab995;"
        f"border-radius:12px;overflow:auto'>"
        f"<p><strong>{book.title}</strong>"
        f"{(' — ' + section) if section else ''}</p>"
        f"<p>{block.text}</p>"
        f"<p style='font-size:0.85rem;color:#756758'>Page {block.ordinal + 1}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )
    read_hint = clean_read_url(book.book_id, ordinal=block.ordinal)
    st.caption(
        f"Speak Screen works on this stage. For Safari Listen to Page open the clean "
        f"article at the same host{read_hint} (UI container port 8502)."
    )


def render_roadmap_tab(client: Client) -> None:
    st.header("Roadmap (v1)")
    with st.form("roadmap_form"):
        interests_raw = st.text_input("Interests (comma-separated)", key="roadmap_interests")
        level = st.selectbox("Level", LEVELS, key="roadmap_level")
        goal = st.text_input("Goal", key="roadmap_goal")
        max_steps = st.number_input(
            "Max steps", min_value=1, max_value=20, value=8, key="roadmap_max_steps"
        )
        submitted = st.form_submit_button("Build roadmap")

    if submitted:
        interests = parse_interests(interests_raw)
        try:
            response = client.build_roadmap(
                interests, normalize_level(level), goal, max_steps=int(max_steps)
            )
        except (ApiClientError, ApiUnavailableError) as exc:
            st.error(format_api_error_message(exc))
        else:
            st.session_state["last_roadmap"] = response

    last_roadmap = st.session_state.get("last_roadmap")
    if last_roadmap is None:
        return

    st.write(last_roadmap.rationale)
    prereq_titles = resolve_prerequisite_titles(last_roadmap.steps)
    for step in steps_in_order(last_roadmap.steps):
        with st.expander(f"{step.order}. {step.title}"):
            st.write(f"Authors: {', '.join(step.authors) or '—'}")
            st.write(step.why)
            prereqs = prereq_titles.get(step.order, [])
            st.write(f"Prerequisites: {', '.join(prereqs) if prereqs else 'none'}")
            st.write(f"Estimated effort: {step.est_effort}")


# One entry per Crossroads door, in grid order. `CROSSROADS_DOORS` is the
# single source of the door set; this table must cover it exactly (pinned by
# `test_every_door_has_a_renderer_and_vice_versa`). The previous `elif` chain
# let `render_roadmap_tab` exist for a week without any door reaching it.
DOOR_RENDERERS: dict[str, Callable[[Client], None]] = {
    "Ask": render_ask_tab,
    "Mentor": render_mentor_tab,
    "Roadmap": render_roadmap_tab,
    "Coffee Table": render_coffee_table_tab,
    "Shelf": render_library_tab,
    "Observatory": render_observatory_tab,
    "Projection": render_projection_tab,
}


def main() -> None:
    st.set_page_config(page_title="MagicLib — HomeLib", page_icon="📚", layout="wide")
    # Community Cloud puts LLM_*/APP_MODE in st.secrets, not os.environ.
    with contextlib.suppress(Exception):
        apply_streamlit_secrets_to_environ(dict(st.secrets))
    client = build_homelib_client()
    # Demo principal survives reruns in session state; no-op in selfhosted.
    # A failed mint must not take the whole page down: the doors still render
    # and the Coffee Table door reports the same error on its own request.
    try:
        ensure_demo_session(client, st.session_state)
    except (ApiClientError, ApiUnavailableError) as exc:
        st.warning(format_api_error_message(exc))

    if "door" not in st.session_state:
        st.session_state["door"] = CROSSROADS_DOORS[0]
    # The rotunda's Enter is a same-document link to `?door=<label>`
    # (its script cannot touch session state; the page reloads instead).
    # Consume the param once so a later grid click is not overridden on rerun.
    if "door" in st.query_params:
        st.session_state["door"] = door_from_query(
            st.query_params.to_dict(), st.session_state["door"], CROSSROADS_DOORS
        )
        del st.query_params["door"]
    if "source" in st.query_params:
        st.session_state["projection_source"] = normalize_projection_source(
            st.query_params.get("source")
        )
        del st.query_params["source"]
    if st.query_params.get("projection") in {"1", "true", "yes"}:
        st.session_state["door"] = "Projection"
        st.session_state["projector_mode"] = True

    door = normalize_door(st.session_state["door"])
    projector_active = bool(st.session_state.get("projector_mode")) and door == "Projection"
    hide_nav = projection_wants_chrome_hidden(
        projector_mode=projector_active,
        query_projection=st.query_params.get("projection"),
    )

    if not hide_nav:
        st.title("MagicLib")
        st.caption(
            "HomeLib — a private academic shelf you can ask, with citations that open the page. "
            f"{len(CROSSROADS_DOORS)} Crossroads doors."
        )
        # The rotating room (specs/rotunda.md), rendered inline: Streamlit's
        # iframe sandbox blocks parent navigation, so the fragment shares this
        # page and Enter is a plain `?door=` link. The button grid beneath stays
        # the accessible path. The slot is reserved above the grid but filled
        # after it, so a grid click and the room agree within the same run.
        rotunda_slot = st.empty()
        cols = st.columns(len(CROSSROADS_DOORS))
        for col, door_label in zip(cols, CROSSROADS_DOORS, strict=True):
            if col.button(door_label, key=f"door_{door_label}"):
                st.session_state["door"] = normalize_door(door_label)
        # unsafe_allow_javascript is safe: the HTML is built from CROSSROADS_DOORS
        # and DOOR_COPY only — never from user input.
        rotunda_slot.html(
            build_rotunda_html(CROSSROADS_DOORS, normalize_door(st.session_state["door"])),
            unsafe_allow_javascript=True,
        )
        door = normalize_door(st.session_state["door"])
        st.caption(f"Open door: {door}")
        st.divider()
    else:
        st.markdown(
            "<style>"
            "header[data-testid='stHeader']{display:none!important}"
            "[data-testid='stToolbar']{display:none!important}"
            "#MainMenu{visibility:hidden}"
            "footer{visibility:hidden}"
            "</style>",
            unsafe_allow_html=True,
        )

    try:
        DOOR_RENDERERS[door](client)
    finally:
        # A 401 remint inside any call must reach the next rerun (view_model).
        persist_demo_session(client, st.session_state)


if __name__ == "__main__":
    main()
