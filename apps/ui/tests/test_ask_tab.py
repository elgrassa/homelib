"""Ask door — empty query vs unreachable, never-blank empty answer."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from apps.ui.api_client import AskResponse, TokenUsage

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
CLOSED_PORT_API = "http://127.0.0.1:9"


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
    assert any("degraded" in w.lower() for w in warnings)
    visible = " ".join(str(getattr(block, "value", block)) for block in at.markdown)
    visible += " ".join(str(getattr(block, "value", block)) for block in at.text)
    assert "do not answer" in visible.lower() or "passages do not answer" in visible.lower()
