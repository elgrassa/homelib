"""Crossroads doors rendered through Streamlit's own test harness.

`streamlit.testing.v1.AppTest` runs `apps/ui/app.py` as Streamlit would, so a
door whose renderer raises, or a door missing from the dispatch table, fails
here instead of in a reviewer's browser. The API is pointed at a closed port:
every door must degrade to an error box, never to a traceback.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from apps.ui.view_model import CROSSROADS_DOORS

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
CLOSED_PORT_API = "http://127.0.0.1:9"


@pytest.fixture(autouse=True)
def _selfhosted_against_closed_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "selfhosted")
    monkeypatch.setenv("API_URL", CLOSED_PORT_API)
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)


@pytest.mark.parametrize("door", CROSSROADS_DOORS)
def test_every_door_renders_without_exception(door: str) -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = door
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    captions = [c.value for c in at.caption]
    assert f"Open door: {door}" not in captions
    (rotunda,) = at.get("html")
    assert f"Facing: {door}" in rotunda.body
    assert "hl-collapsed" in rotunda.body
    assert door in [h.value for h in at.header]


def test_door_grid_has_one_button_per_door() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    # Select by key: the Ask door's own submit button is also labelled "Ask".
    labels = [at.button(key=f"door_{door}").label for door in CROSSROADS_DOORS]
    assert labels == list(CROSSROADS_DOORS)


def test_clicking_a_door_button_opens_that_door() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    target = "Roadmap"
    at.button(key=f"door_{target}").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["door"] == target
    assert f"Open door: {target}" not in [c.value for c in at.caption]
    # Door body renders above the rotunda band; room still faces the target.
    (rotunda,) = at.get("html")
    assert f"Facing: {target}" in rotunda.body
    assert "hl-collapsed" in rotunda.body
    assert "Roadmap" in [h.value for h in at.header]


def test_switching_doors_does_not_render_the_previous_door_body() -> None:
    """LIVE: Projection briefly kept Observatory/Ask controls until another rerun."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Ask"
    at.run()
    assert "Ask your library a question" in [widget.label for widget in at.text_input]

    at.button(key="door_Projection").click().run()

    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["door"] == "Projection"
    assert "Projection" in [header.value for header in at.header]
    assert "Ask your library a question" not in [widget.label for widget in at.text_input]
    # Same-run settle: Shelf-only controls must not linger under Projection.
    assert "Scene search" not in [widget.label for widget in at.text_input]


def test_door_query_param_opens_that_door_and_is_consumed() -> None:
    """The rotunda's Enter reloads the page on `?door=X`; the app must open X
    and drop the param so a later grid click is not overridden on rerun."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.query_params["door"] = "Shelf"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["door"] == "Shelf"
    assert "Open door: Shelf" not in [c.value for c in at.caption]
    assert "door" not in at.query_params
    (rotunda,) = at.get("html")
    assert "Facing: Shelf" in rotunda.body
    assert "Shelf" in [h.value for h in at.header]


def test_unknown_door_query_param_does_not_crash_the_crossroads() -> None:
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.query_params["door"] = "Rotunda"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["door"] == "Ask"
    assert "Open door: Ask" not in [c.value for c in at.caption]
    assert "Ask" in [h.value for h in at.header]


def test_roadmap_door_heading_is_not_labelled_v1() -> None:
    """The rotunda and the door heading must agree. 'Roadmap (v1)' leaked an
    internal store generation onto the public Crossroads."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Roadmap"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    headings = [h.value for h in at.header]
    assert "Roadmap" in headings
    assert not any("v1" in str(h).lower() for h in headings)


def test_projector_toggle_off_leaves_projector_mode() -> None:
    """`?projection=1` must open projector mode exactly once. Regression for the
    trap where `main()` re-asserted `projector_mode=True` on every rerun,
    making the in-tab toggle-off unable to stick (BUG 1)."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.query_params["projection"] = "1"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["door"] == "Projection"
    assert at.session_state["projector_mode"] is True
    # Chrome (and with it the door grid) is hidden while projector mode is on.
    with pytest.raises(KeyError):
        at.button(key="door_Ask")

    at.toggle(key="projector_mode").set_value(False).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["projector_mode"] is False
    assert "projection" not in at.query_params
    assert at.button(key="door_Ask").label == "Ask"


def test_source_param_consumed_once() -> None:
    """`?source=` must be consumed into session state once, not re-added on
    every rerun by the projector branch's stale guard (BUG 1b)."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.query_params["source"] = "shelf"
    at.session_state["door"] = "Projection"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["projection_source"] == "shelf"
    assert "source" not in at.query_params

    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "source" not in at.query_params


def test_projection_ordinal_resets_when_book_changes() -> None:
    """The Projection ordinal must be keyed per book, not global (BUG 2): a
    stale global `proj_ordinal` left over from a long book could otherwise be
    replayed against a much shorter one. The API is unreachable here, so this
    pins the new per-book key shape rather than exercising pagination."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Projection"
    at.session_state["projection_source"] = "shelf"
    at.session_state["proj_ordinal:walden"] = 300
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "proj_ordinal" not in at.session_state
