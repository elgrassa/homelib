"""Streamlit UI. Talks only to the public API, never to the database.

This module is a *rendering shell* and nothing else: every function here calls
the pure helpers in ``apps.ui.view_model`` and issues ``st.*`` calls, but makes
no decisions of its own. All the logic — formatting, aggregation, state
transitions — lives in ``view_model.py``, which is fully unit-tested.

That separation is why this file is the one module excluded from the coverage
floor (see ``[tool.coverage.run] omit`` in pyproject.toml): it cannot be
exercised without a live Streamlit runtime, and pretending otherwise would mean
writing tests that assert nothing. Anything worth asserting belongs in
``view_model.py``, where the floor does apply.

``main()`` is only invoked when the file is executed via
``streamlit run apps/ui/app.py`` (guarded by ``if __name__ == "__main__"``),
so importing this module in tests never touches the Streamlit runtime.
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

from apps.ui.api_client import (
    ApiClient,
    ApiClientError,
    ApiUnavailableError,
    AskResponse,
)
from apps.ui.view_model import (
    LEVELS,
    block_id_for_citation,
    format_api_error_message,
    format_citation_label,
    format_degraded_banner,
    get_api_url,
    has_voted,
    library_summary,
    normalize_level,
    parse_interests,
    record_vote,
    resolve_prerequisite_titles,
    steps_in_order,
)


def render_ask_tab(client: ApiClient) -> None:
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


def _cast_vote(client: ApiClient, request_id: str, feedback: Literal["up", "down"]) -> None:
    try:
        client.submit_feedback(request_id, feedback)
    except (ApiClientError, ApiUnavailableError) as exc:
        st.error(format_api_error_message(exc))
    else:
        feedback_sent: set[str] = st.session_state.setdefault("feedback_sent", set())
        st.session_state["feedback_sent"] = record_vote(feedback_sent, request_id)


def render_roadmap_tab(client: ApiClient) -> None:
    st.header("Roadmap")
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


def render_library_tab(client: ApiClient) -> None:
    st.header("Library")
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


def main() -> None:
    st.set_page_config(page_title="homelib", page_icon="📚", layout="wide")
    st.title("homelib")
    client = ApiClient(get_api_url())

    ask_tab, roadmap_tab, library_tab = st.tabs(["Ask", "Roadmap", "Library"])
    with ask_tab:
        render_ask_tab(client)
    with roadmap_tab:
        render_roadmap_tab(client)
    with library_tab:
        render_library_tab(client)


if __name__ == "__main__":
    main()
