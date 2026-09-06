"""Rotunda: pure-string behaviour of the rotating room (specs/rotunda.md).

No screenshot-of-CSS tests here — the before/after screenshots attached to the
PR are the design gate. These pin what must hold for the room to *navigate*:
every door has an Enter that reloads the page on `?door=`, unknown doors cannot
crash the Crossroads, and a hostile label cannot break out of the script.
"""

from __future__ import annotations

import pytest

from apps.ui.rotunda import (
    DOOR_COPY,
    build_rotunda_html,
    door_from_query,
)
from apps.ui.view_model import CROSSROADS_DOORS, normalize_door


def test_rotunda_door_labels_match_crossroads_doors() -> None:
    doc = build_rotunda_html(CROSSROADS_DOORS, CROSSROADS_DOORS[0])
    for door in CROSSROADS_DOORS:
        assert f'data-door="{door}"' in doc
    # The HTML fixture's six wings are not the product's doors.
    for wing in ("AI Engineering", "Surprise Me", "Ideas in Common"):
        assert wing not in doc


def test_rotunda_html_emits_door_param_link_for_every_door() -> None:
    doc = build_rotunda_html(CROSSROADS_DOORS, "Ask")
    for door in CROSSROADS_DOORS:
        assert f'href="?door={door}"' in doc, door
    assert "window.location.assign('?door='" in doc


def test_rotunda_is_an_inline_fragment_not_an_iframe_document() -> None:
    """Streamlit's iframe sandbox has no `allow-top-navigation`, so a
    `target="_parent"` Enter is a SecurityError there (seen in Chrome,
    2026-09-05). The room must stay an inline fragment: no document shell,
    no parent targets, no unscoped rules that would restyle the page."""
    doc = build_rotunda_html(CROSSROADS_DOORS, "Ask")
    assert 'target="_parent"' not in doc
    assert "window.parent" not in doc
    for shell in ("<!doctype", "<html", "<head>", "<body"):
        assert shell not in doc.lower(), shell
    css = doc[doc.index("<style>") : doc.index("</style>")]
    rules = [
        line.strip()
        for line in css.splitlines()
        if "{" in line and not line.strip().startswith(("@", "/*", "*"))
    ]
    # @keyframes step selectors (from/to/0%) are not page-scoped rules.
    unscoped = [
        r
        for r in rules
        if not r.startswith("#hl-rotunda")
        and not r.startswith(("from ", "to ", "from{", "to{"))
        and "%" not in r.split("{", 1)[0]
    ]
    assert not unscoped, unscoped


def test_rotunda_has_no_search_arm() -> None:
    """specs/rotunda.md: the fixture's regex 'search' is not a retrieval arm."""
    doc = build_rotunda_html(CROSSROADS_DOORS, "Ask")
    assert "<form" not in doc
    assert "<input" not in doc
    assert "Reveal a path" not in doc


def test_static_grid_still_rendered_when_reduced_motion() -> None:
    """Reduced motion disables the rotation transition; every Enter link is
    still emitted, so the room stays navigable without any animation."""
    doc = build_rotunda_html(CROSSROADS_DOORS, "Mentor", reduced_motion=True)
    assert 'class="hl-rotunda hl-reduced"' in doc
    assert "prefers-reduced-motion: reduce" in doc
    assert doc.count('class="hl-enter-link"') == len(CROSSROADS_DOORS)


def test_rotunda_active_door_is_the_visible_enter_link() -> None:
    doc = build_rotunda_html(CROSSROADS_DOORS, "Projection")
    assert 'data-door="Projection">Enter Projection</a>' in doc
    assert 'data-door="Ask" hidden>Enter Ask</a>' in doc
    assert "Facing: Projection" in doc


def test_rotunda_enter_sets_session_door() -> None:
    """The `?door=` a followed Enter link produces resolves to that door."""
    for door in CROSSROADS_DOORS:
        assert door_from_query({"door": door}, "Ask", CROSSROADS_DOORS) == door
    assert door_from_query({}, "Shelf", CROSSROADS_DOORS) == "Shelf"


def test_unknown_door_param_falls_back_via_normalize_door() -> None:
    """A stale or tampered `?door=Rotunda` must not raise on a reviewer's
    screen: the current door stays and it still normalizes."""
    kept = door_from_query({"door": "Rotunda"}, "Ask", CROSSROADS_DOORS)
    assert kept == "Ask"
    assert normalize_door(kept) == "Ask"
    with pytest.raises(ValueError):
        normalize_door("Rotunda")


def test_rotunda_html_neutralises_script_close() -> None:
    hostile = "</script><script>alert(1)</script>"
    doc = build_rotunda_html(("Ask", hostile), "Ask")
    # The label reaches the inline JSON only with every `<` escaped …
    assert "\\u003c/script>\\u003cscript>alert(1)\\u003c/script>" in doc
    # … and the server-rendered anchors HTML-escape it.
    assert "&lt;/script&gt;" in doc
    assert doc.count("</script>") == 1


def test_rotunda_script_text_contains_no_markup_like_characters() -> None:
    """Streamlit renders the fragment through DOMPurify with SAFE_FOR_XML, which
    removes any element whose text matches `<` + word char. A single `<` in a
    comment or in injected JSON silently deletes the script — and with it every
    door in the room (seen 2026-09-05: `?door=<name>` in a comment)."""
    doc = build_rotunda_html((*CROSSROADS_DOORS, "a<b", "</x>"), "Ask")
    start = doc.index("<script>") + len("<script>")
    end = doc.index("</script>")
    assert "<" not in doc[start:end]


def test_rotunda_magic_effects_are_scoped_and_respect_reduced_motion() -> None:
    """Mockup language (gold bloom, teal seal, motes) must stay inside #hl-rotunda
    and shut off under prefers-reduced-motion / hl-reduced."""
    doc = build_rotunda_html(CROSSROADS_DOORS, "Ask")
    assert "hl-seal-pulse" in doc
    assert "hl-door-glow" in doc
    assert "hl-motes" in doc
    assert "--hl-teal:" in doc
    assert "min-height: 460px" in doc
    reduced = build_rotunda_html(CROSSROADS_DOORS, "Ask", reduced_motion=True)
    assert "hl-reduced" in reduced
    assert "animation: none" in reduced


def test_rotunda_rejects_unknown_active_and_single_door() -> None:
    with pytest.raises(ValueError):
        build_rotunda_html(CROSSROADS_DOORS, "Rotunda")
    with pytest.raises(ValueError):
        build_rotunda_html(("Ask",), "Ask")


def test_every_crossroads_door_has_copy() -> None:
    for door in CROSSROADS_DOORS:
        assert door in DOOR_COPY, f"write a line of intent for the {door} door"
