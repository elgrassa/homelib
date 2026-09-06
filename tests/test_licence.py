"""Guards on the licence swap itself (ADR-007).

The repo used to ship an unfilled Apache-2.0 template while ADR-007 already
decided on PolyForm Noncommercial 1.0.0 for code and CC BY-NC-SA 4.0 for
docs/images. A licence file and a `license` field in `pyproject.toml` are
easy to let drift back to a stale default (a fresh `uv init`, a copy-pasted
template) without anything failing. These tests assert the licence actually
declared on disk matches the owner's decision, not that a scan ran.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSE = REPO_ROOT / "LICENSE"
LICENSE_DOCS = REPO_ROOT / "LICENSE-docs.md"
PYPROJECT_FILES = (
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "packages/homelib-core/pyproject.toml",
    REPO_ROOT / "packages/homelib-rag/pyproject.toml",
)


def test_license_is_polyform_noncommercial() -> None:
    """LICENSE must be the PolyForm Noncommercial 1.0.0 text, not Apache."""
    text = LICENSE.read_text()

    first_nonempty_line = next(line for line in text.splitlines() if line.strip())
    assert first_nonempty_line.startswith("HomeLib"), (
        "LICENSE must open with the HomeLib/MagicLib notice, not the raw licence text"
    )
    assert "PolyForm Noncommercial License 1.0.0" in text
    assert "Apache" not in text


def test_docs_licence_is_cc_by_nc_sa() -> None:
    """LICENSE-docs.md must exist and declare CC BY-NC-SA 4.0."""
    assert LICENSE_DOCS.is_file(), "LICENSE-docs.md is missing"
    assert "CC BY-NC-SA 4.0" in LICENSE_DOCS.read_text()


def test_no_pyproject_declares_apache() -> None:
    """Every pyproject.toml must declare PolyForm-Noncommercial-1.0.0.

    None of them may mention Apache-2.0 as the package licence — that was
    the stale default this ADR replaced.
    """
    for path in PYPROJECT_FILES:
        data = tomllib.loads(path.read_text())
        license_field = data["project"]["license"]
        assert license_field == {"text": "PolyForm-Noncommercial-1.0.0"}, (
            f"{path} does not declare PolyForm-Noncommercial-1.0.0"
        )
        assert "Apache-2.0" not in path.read_text()
