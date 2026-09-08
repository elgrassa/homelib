"""The Crossroads rotunda — the rotating room of doors (specs/rotunda.md).

Pure module: builds the HTML fragment that `apps/ui/app.py` renders inline
with `st.html(..., unsafe_allow_javascript=True)`. No Streamlit import, no
network, no state — so every behaviour here is a plain string assertion.

Why the shape is what it is:

* The fragment is **inline, not an iframe**. The first cut mounted it through
  `st.iframe` / `components.v1.html`; Streamlit sandboxes that iframe
  (`allow-scripts allow-same-origin …` without `allow-top-navigation`), so an
  `<a target="_parent">` and `window.parent.location` both fail with a
  SecurityError — verified in Chrome on 2026-09-05. Inline, **Enter is a
  same-document link** `<a href="?door=X">`: Streamlit reloads, `app.py` reads
  `?door=` into session state through `door_from_query`, and the static grid
  beneath the room stays the accessible path — animation is never the only
  way in.
* `unsafe_allow_javascript` is safe here because the document is built only
  from `CROSSROADS_DOORS` and `DOOR_COPY` — never from user input, query
  parameters or LLM output — and labels are HTML-escaped / `</`-neutralised.
* The door set is injected from Python (`CROSSROADS_DOORS`), never hard-coded
  in the HTML fixture, so the rotunda and the grid cannot disagree.
* The template is derived from `docs/mockups/homelib-magic-library-standalone.html`
  and the MagicLib stills (gold bloom, teal floor seal, candle vignette). Rules
  stay scoped under `#hl-rotunda` because the fragment shares the page CSS.
  The room is a **dark jewel on the parchment Streamlit shell** — Projection /
  Speak Screen keep the light page theme.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

__all__ = ["DOOR_COPY", "build_rotunda_html", "door_from_query"]

_TEMPLATE_PATH = Path(__file__).with_name("rotunda_template.html")

# One line of intent per door. Unknown doors fall back to a neutral line so a
# new door added to CROSSROADS_DOORS renders before anyone writes its copy.
DOOR_COPY: Mapping[str, str] = {
    "Ask": "Ask across the shelf and get an answer that cites the passage it came from.",
    "Mentor": "Tell the mentor what you want to learn; it proposes a shelf path or refuses.",
    "Roadmap": "Interests, level and goal in — an ordered reading roadmap out.",
    "Coffee Table": "The books you have set aside to read next, in your order.",
    "Shelf": "What is on the shelf: titles, block and chunk counts, and scene search.",
    "Observatory": "Charts over every question asked here, plus your thumbs.",
    "Projection": "Open a chapter on the big page and read it end to end.",
}
_FALLBACK_COPY = "Step through to open this part of the library."


def _json_for_script(value: object) -> str:
    """JSON that is safe inside an inline `<script>`.

    Every `<` becomes the JSON escape `\\u003c`: a `</` in a door label could
    otherwise close the script element early, and Streamlit's sanitizer
    (DOMPurify, SAFE_FOR_XML) drops the *whole* script when its text contains
    `<` followed by a word character — the room would silently lose its doors.
    """
    return json.dumps(value).replace("<", "\\u003c")


def door_from_query(params: Mapping[str, str], current: str, doors: Sequence[str]) -> str:
    """Resolve the door an Enter link asked for.

    `?door=X` arrives when the rotunda's Enter link is followed. A value that
    is not a known door (typo, stale link, tampering) is ignored and the
    current door stays — never an exception on a reviewer's screen.
    """
    requested = params.get("door")
    if requested is None:
        return current
    return requested if requested in doors else current


def build_rotunda_html(
    doors: Sequence[str],
    active: str,
    *,
    reduced_motion: bool = False,
    collapsed: bool = False,
) -> str:
    """Return the rotunda fragment that `app.py` renders with `st.html`.

    `active` must be one of `doors`; it is the door facing the viewer on load.
    `reduced_motion=True` disables the rotation transition from the Python
    side (the CSS media query does the same for users who asked their OS).
    `collapsed=True` shrinks the room to a navigation band and hides the
    duplicate Enter card once a door's content is already on screen.
    The markup lives in `rotunda_template.html` next to this module — CSS and
    JS are not Python, and a 100-column linter should not shape a gradient.
    """
    if active not in doors:
        raise ValueError(f"active door {active!r} is not in {tuple(doors)!r}")
    if len(doors) < 2:
        raise ValueError("the rotunda needs at least two doors")

    active_index = list(doors).index(active)
    # The static Enter links: one per door, rendered server-side so the
    # navigation exists even before the script runs (and is testable as text).
    # When collapsed, omit Enter for the already-open door (primary action is
    # inside that door's body).
    enter_links = "\n".join(
        f'<a class="hl-enter-link" href="?door={html.escape(d, quote=True)}" '
        f'data-door="{html.escape(d, quote=True)}"'
        f"{' hidden' if collapsed or i != active_index else ''}>Enter {html.escape(d)}</a>"
        for i, d in enumerate(doors)
    )
    motion = " hl-reduced" if reduced_motion else ""
    collapse = " hl-collapsed" if collapsed else ""
    replacements = {
        "__MOTION_CLASS__": f"{motion}{collapse}",
        "__ACTIVE_ESCAPED__": html.escape(active),
        "__ACTIVE_COPY_ESCAPED__": html.escape(DOOR_COPY.get(active, _FALLBACK_COPY)),
        "__ENTER_LINKS__": enter_links,
        "__LABELS_JSON__": _json_for_script(list(doors)),
        "__COPY_JSON__": _json_for_script({d: DOOR_COPY.get(d, _FALLBACK_COPY) for d in doors}),
        "__ACTIVE_INDEX__": str(active_index),
    }
    doc = _TEMPLATE_PATH.read_text(encoding="utf-8")
    for token, value in replacements.items():
        doc = doc.replace(token, value)
    return doc
