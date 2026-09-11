"""Ask door — empty query vs unreachable, never-blank empty answer."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from apps.ui.api_client import AskResponse, TokenUsage

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
CLOSED_PORT_API = "http://127.0.0.1:9"


def test_repeated_citation_source_keeps_both_quotes_and_opens_either_button() -> None:
    at = AppTest.from_string(
        """
from types import SimpleNamespace
from apps.ui.app import _render_citation_expanders
from apps.ui.api_client import Citation
c = Citation(chunk_id="same-chunk", book_id="test-book", book_title="Test book",
             section_path=["Chapter"], quote="First quote")
client = SimpleNamespace(get_block=lambda _: SimpleNamespace(text="Full source text"))
_render_citation_expanders(client, [c, c.model_copy(update={"quote": "Second quote"})])
""",
        default_timeout=30,
    ).run()
    assert not at.exception, [e.value for e in at.exception]
    assert {m.value for m in at.markdown} >= {"First quote", "Second quote"}
    keys = [b.key for b in at.button]
    assert len(keys) == len(set(keys)) == 2
    for key in keys:
        at.button(key=key).click().run()
        assert not at.exception, [e.value for e in at.exception]
        assert any(t.value == "Full source text" for t in at.text)


@pytest.fixture(autouse=True)
def _selfhosted_against_closed_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "selfhosted")
    monkeypatch.setenv("API_URL", CLOSED_PORT_API)
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)


def test_ask_empty_query_shows_error_not_silent_noop() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Ask"
    at.run()
    at.button(key="ask_submit").click().run()
    assert not at.exception, [e.value for e in at.exception]
    errors = [e.value for e in at.error]
    assert errors
    assert any("question" in e.lower() for e in errors)
    assert not any("unreachable" in e.lower() for e in errors)


def test_ask_filled_query_against_closed_port_is_unreachable_without_question_error() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Ask"
    at.run()
    at.text_input(key="ask_query").set_value("what do you have?")
    at.button(key="ask_submit").click().run()
    assert not at.exception, [e.value for e in at.exception]
    errors = [e.value for e in at.error]
    assert errors
    assert any("unreachable" in e.lower() for e in errors)
    assert not any("question" in e.lower() for e in errors)


def test_ask_empty_answer_renders_refuse_not_blank() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Ask"
    at.session_state["last_ask"] = AskResponse(
        request_id="req-empty",
        answer="",
        citations=[],
        arm_used="hybrid_rerank",
        degraded=False,
        latency_ms=12,
        tokens=TokenUsage(prompt=1, completion=0),
    )
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    visible = " ".join(str(getattr(block, "value", block)) for block in at.markdown)
    visible += " ".join(str(getattr(block, "value", block)) for block in at.text)
    assert "do not answer" in visible.lower() or "passages do not answer" in visible.lower()


def test_ask_empty_degraded_answer_renders_refuse_and_degraded_banner() -> None:
    """#A1 inventory miss after Groq json_validate: empty degraded body must
    still show refuse (not a blank door) plus the degraded banner."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Ask"
    at.session_state["last_ask"] = AskResponse(
        request_id="req-empty-degraded",
        answer="",
        citations=[],
        arm_used="hybrid_rerank",
        degraded=True,
        latency_ms=12,
        tokens=TokenUsage(prompt=0, completion=0),
    )
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    warnings = [w.value for w in at.warning]
    assert any("verified answer" in w.lower() or "no verified" in w.lower() for w in warnings)
    visible = " ".join(str(getattr(block, "value", block)) for block in at.markdown)
    visible += " ".join(str(getattr(block, "value", block)) for block in at.text)
    assert "do not answer" in visible.lower() or "passages do not answer" in visible.lower()


def test_ask_empty_answer_renders_catalog_links_from_session() -> None:
    """Shelf miss + Discover payload in session → Open lawful source links."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Ask"
    at.session_state["last_ask"] = AskResponse(
        request_id="req-catalog",
        answer="",
        citations=[],
        arm_used="hybrid_rerank",
        degraded=False,
        latency_ms=12,
        tokens=TokenUsage(prompt=1, completion=0),
    )
    at.session_state["last_ask_query"] = "meditations"
    at.session_state["last_ask_catalog"] = {
        "items": [
            {
                "title": "Meditations",
                "authors": ["Marcus Aurelius"],
                "provider_url": "https://openlibrary.org/works/OL100W",
            }
        ],
        "unique_count": 1,
        "degraded": False,
    }
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    visible = " ".join(str(getattr(block, "value", block)) for block in at.markdown)
    assert "open lawful source" in visible.lower()
    assert "meditations" in visible.lower()
    assert "openlibrary.org" in visible.lower()


def test_ask_nonempty_abstention_renders_catalog_links_from_session() -> None:
    """A textual passage refusal gets the same lawful next step as an empty answer."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Ask"
    at.session_state["last_ask"] = AskResponse(
        request_id="req-catalog-abstention",
        answer="None of the provided passages answer this question.",
        citations=[],
        arm_used="hybrid_rerank",
        degraded=False,
        latency_ms=12,
        tokens=TokenUsage(prompt=10, completion=5),
    )
    at.session_state["last_ask_query"] = "meditations"
    at.session_state["last_ask_catalog"] = {
        "items": [
            {
                "title": "Meditations",
                "authors": ["Marcus Aurelius"],
                "provider_url": "https://openlibrary.org/works/OL100W",
            }
        ],
        "unique_count": 1,
        "degraded": False,
    }

    at.run()

    assert not at.exception, [e.value for e in at.exception]
    visible = " ".join(str(getattr(block, "value", block)) for block in at.markdown)
    assert "open lawful source" in visible.lower()
    assert "meditations" in visible.lower()
