"""Guards on the public snapshot itself.

This repo is developed on a private Forgejo instance and published as a
public GitHub snapshot for the LLM Zoomcamp capstone. These tests assert
that tracked, reviewer-facing docs carry no internal infrastructure
references (host names, runner paths, personal emails) and no links into
`docs/handoffs/`, which is local working notes and becomes untracked in
this same PR.

Scoped with `git ls-files` (not a filesystem walk) so untracked files —
including the owner-only runbook this PR adds under `docs/handoffs/` — are
never checked: they are not part of what gets published.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Literal internal-infrastructure references that must never appear in a
# tracked, reviewer-facing doc. Deliberately narrow (exact hosts/paths), not
# a broad word list, so it fails on real leaks and not on prose.
_INTERNAL_HOST_PATTERN = re.compile(
    r"minips\.local|localhost:2222|ExternalSSDMini|~/CI/Forgejo|@gmail\.com"
)

_HANDOFF_LINK_PATTERN = re.compile(r"docs/handoffs/|handoffs/2026-")

# Public-facing surface: the reviewer never needs to open anything outside
# these paths to judge the submission. `docs/handoffs/` and `graphify-out/`
# are excluded — the former is local working notes (untracked by the end of
# this PR), the latter is a generated code-graph snapshot, neither is
# reviewer-facing prose.
_PUBLIC_DOC_PATHSPECS = (
    "README.md",
    "CHECKLIST.md",
    "docs/**",
    ":!docs/handoffs/**",
    "specs/**",
    "justfile",
    ".forgejo/**",
)


def _tracked_public_doc_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "--", *_PUBLIC_DOC_PATHSPECS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths = [REPO_ROOT / line for line in output.splitlines() if line.strip()]
    # Belt-and-braces: the pathspec exclusion above already drops these, but
    # a future pathspec typo must not silently let them back in.
    return [
        path for path in paths if "graphify-out" not in path.parts and "handoffs" not in path.parts
    ]


def test_public_docs_have_no_internal_hosts() -> None:
    """No tracked, reviewer-facing doc may name the private Forgejo host,
    its SSH port, the external drive the CI runners live on, the runner's
    home-relative Forgejo data path, or a personal email address.

    A public GitHub snapshot of this repo is the whole point of this PR;
    any of these leaking into README/CHECKLIST/docs/specs/justfile/CI would
    expose the studio's private infrastructure to every reader.
    """
    offenders: list[str] = []
    for path in _tracked_public_doc_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _INTERNAL_HOST_PATTERN.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")

    assert not offenders, "internal infrastructure references found:\n" + "\n".join(offenders)


def test_no_tracked_doc_links_to_handoffs() -> None:
    """`docs/handoffs/` becomes untracked in this same PR, so no tracked doc
    may still point a reader at it — a reviewer following the link would
    get a 404 (GitHub) or nothing at all (a clone), and the content itself
    is local working notes, not part of the submission.
    """
    offenders: list[str] = []
    for path in _tracked_public_doc_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _HANDOFF_LINK_PATTERN.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")

    assert not offenders, "tracked docs still link to docs/handoffs/:\n" + "\n".join(offenders)


def test_submission_docs_name_the_live_demo_without_old_cloud_placeholders() -> None:
    """The final review found mutually contradictory pending/live Cloud claims."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (REPO_ROOT / "CHECKLIST.md").read_text(encoding="utf-8")
    live_url = "https://homelib.streamlit.app/"

    assert live_url in readme
    assert live_url in checklist
    for stale_claim in (
        "URL to be added after Cloud deploy",
        "Public demo URL: none yet",
        "Cloud deploy is pending",
    ):
        assert stale_claim not in readme
        assert stale_claim not in checklist
