"""The 2026 gap report is a promise list: every numbered item in its
"FIXES gap LLM Zoomcamp 2026" section must end in a resolution."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAP_REPORT = REPO_ROOT / "docs" / "zoomcamp-2026-gap-report.md"
_ITEM = re.compile(r"^(\d+)\. \*\*(.+?)\*\*(.*)$")


def _fixes_items() -> list[tuple[int, str, str]]:
    body = GAP_REPORT.read_text(encoding="utf-8")
    start = body.index("## FIXES gap LLM Zoomcamp 2026")
    section = body[start:]
    items: list[tuple[int, str, str]] = []
    for line in section.splitlines():
        m = _ITEM.match(line)
        if m:
            items.append((int(m.group(1)), m.group(2), m.group(3)))
    return items


def test_gap_report_items_are_all_resolved() -> None:
    """Behavioural: no numbered FIXES item may still carry a `**TODO**`; each
    must state `**DONE:**` (what changed, test, number) or
    `**Explanation_Skipped:**` (why the technique was deliberately not
    adopted). A reviewer reading the list gets a verdict on every gap, never
    an IOU — and this test is what turns a forgotten item into a red build.
    """
    items = _fixes_items()
    assert len(items) >= 17, f"expected the 17 catalogued items, found {len(items)}"
    unresolved = [f"{n}. {title}" for n, title, rest in items if "**TODO**" in rest]
    assert unresolved == [], "unresolved gap-report items:\n" + "\n".join(unresolved)
    missing_verdict = [
        f"{n}. {title}"
        for n, title, rest in items
        if "**DONE:**" not in rest and "**Explanation_Skipped:**" not in rest
    ]
    assert missing_verdict == [], "items without a verdict:\n" + "\n".join(missing_verdict)


def test_gap_report_is_linked_from_readme_and_course_map() -> None:
    """The report is only useful if a reviewer can find it from the two
    documents they actually open first."""
    for doc in ("README.md", "docs/course-map.md"):
        text = (REPO_ROOT / doc).read_text(encoding="utf-8")
        assert "zoomcamp-2026-gap-report.md" in text, f"{doc} does not link the gap report"
