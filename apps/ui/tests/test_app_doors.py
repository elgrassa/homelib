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
    assert f"Open door: {door}" in captions


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
    assert f"Open door: {target}" in [c.value for c in at.caption]
