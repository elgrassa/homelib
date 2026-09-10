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


def test_mentor_propose_path_with_empty_goal_asks_for_a_goal() -> None:
    """Blank Goal + Propose path must not silently no-op.

    BrokenMentor.har showed the Mentor form still sitting there after a click
    with no error and no proposal — `if submitted and goal.strip()` dropped
    the submit on an empty Goal without saying so. A filled Goal against the
    closed-port API must still surface the unreachable error instead.
    """
    empty = AppTest.from_file(str(APP_PATH), default_timeout=30)
    empty.session_state["door"] = "Mentor"
    empty.run()
    empty.button(key="mentor_propose").click().run()
    assert not empty.exception, [e.value for e in empty.exception]
    empty_errors = [e.value for e in empty.error]
    assert empty_errors
    assert any("goal" in e.lower() for e in empty_errors)
    assert not any("unreachable" in e.lower() for e in empty_errors)

    filled = AppTest.from_file(str(APP_PATH), default_timeout=30)
    filled.session_state["door"] = "Mentor"
    filled.run()
    filled.text_input(key="mentor_goal").set_value("Land AI engineer job")
    filled.button(key="mentor_propose").click().run()
    assert not filled.exception, [e.value for e in filled.exception]
    filled_errors = [e.value for e in filled.error]
    assert filled_errors
    assert any("unreachable" in e.lower() for e in filled_errors)
    assert not any("goal" in e.lower() for e in filled_errors)


def test_mentor_tab_renders_area_wing_path_and_citations() -> None:
    """A complete intake is the Mentor door's whole product: area, wing,
    proposed path, and citations that name the book — not rationale alone.
    The live door looked empty after Propose path because those fields were
    dropped even when the API returned them."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Mentor"
    at.session_state["last_mentor"] = _seeded_mentor_response(
        proposed_area={"name": "Career", "copy": "Ship an AI engineering portfolio."},
        proposed_wing={"name": "Machine learning", "area_name": "Career", "copy": "Models."},
        proposed_path={
            "title": "Path to the job",
            "kind": "learning",
            "steps": [{"order": 1, "title": "Read Walden", "why": "attention"}],
        },
        citations=[
            {
                "chunk_id": "c1",
                "block_id": "b1",
                "book_id": "walden",
                "book_title": "Walden",
                "section_path": ["Economy"],
                "page": 3,
                "quote": "I went to the woods",
            }
        ],
    )
    at.run()

    assert not at.exception, [e.value for e in at.exception]
    assert "Path to the job" in [s.value for s in at.subheader]
    visible = " ".join(
        str(getattr(block, "value", block))
        for group in (at.markdown, at.text, at.caption)
        for block in group
    )
    assert "Career" in visible
    assert "Machine learning" in visible
    assert "Read Walden" in visible
    expanders = at.get("expander")
    labels = [getattr(item, "label", None) or getattr(item, "value", "") for item in expanders]
    assert any("Walden" in str(label) for label in labels)
    buttons = at.button
    button_labels = [getattr(item, "label", None) or getattr(item, "value", "") for item in buttons]
    assert any("Show full source block" in str(label) for label in button_labels)


def test_mentor_preset_button_loads_curated_ai_path_without_api() -> None:
    """Preset chips seed a path locally — no mentor_intake call required."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Mentor"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.button(key="mentor_preset_ai-engineer").click().run()
    assert not at.exception, [e.value for e in at.exception]
    last = at.session_state["last_mentor"]
    assert last["preset_id"] == "ai-engineer"
    assert last["proposed_path"]["title"]
    assert any("AI engineer" in s.value for s in at.subheader)
    assert "production LLM" in str(at.session_state["mentor_goal"])
