"""Mentor door tool-use caption — `streamlit.testing.v1.AppTest`, same
harness as `test_app_doors.py`. No network: `last_mentor` is seeded directly
into session state, exactly the shape `client.mentor_intake(...)` returns
once `MentorIntakeResponse.tool_calls`/`rounds_used` are populated by the
`run_agent` loop on the Mentor path (specs/agent-tools.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
CLOSED_PORT_API = "http://127.0.0.1:9"


@pytest.fixture(autouse=True)
def _selfhosted_against_closed_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "selfhosted")
    monkeypatch.setenv("API_URL", CLOSED_PORT_API)
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)


def _seeded_mentor_response(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": "r1",
        "proposed_area": None,
        "proposed_wing": None,
        "proposed_path": None,
        "rationale": "Grounded in shelf evidence.",
        "citations": [],
        "degraded": False,
        "high_stakes_notice": None,
        "tool_calls": ["search_shelf", "get_block"],
        "rounds_used": 2,
    }
    payload.update(overrides)
    return payload


def test_mentor_tab_shows_tool_use_caption_when_tools_were_called() -> None:
    """A Mentor response whose `tool_calls` is non-empty renders a caption
    naming the tools in call order and the round count they took."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Mentor"
    at.session_state["last_mentor"] = _seeded_mentor_response()
    at.run()

    assert not at.exception, [e.value for e in at.exception]
    captions = [c.value for c in at.caption]
    assert "Tools used: search_shelf → get_block (2 rounds)" in captions


def test_mentor_tab_omits_tool_use_caption_when_no_tools_were_called() -> None:
    """An empty `tool_calls` (e.g. abstention, or an LLM-unreachable degrade)
    renders no tool-use caption at all."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Mentor"
    at.session_state["last_mentor"] = _seeded_mentor_response(tool_calls=[], rounds_used=0)
    at.run()

    assert not at.exception, [e.value for e in at.exception]
    captions = [c.value for c in at.caption]
    assert not any(c.startswith("Tools used:") for c in captions)
