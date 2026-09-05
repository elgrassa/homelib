"""Streamlit Community Cloud edition: the files Cloud reads and the seed it needs.

Cloud installs from the first dependency file it finds — `uv.lock` wins over
`requirements.txt` — and picks Python in Advanced settings (default 3.12).
These tests pin what must be true of the committed tree for the owner's Monday
deploy to have a chance; the deploy itself is the owner's, not an agent's.
"""

from __future__ import annotations

import gzip
import importlib.util
import re
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cloud_entrypoint_runs_the_same_ui_main() -> None:
    """`streamlit_app.py` is a shim over `apps/ui/app.py`, not a second UI."""
    shim = REPO_ROOT / "streamlit_app.py"
    assert shim.is_file()
    spec = importlib.util.spec_from_file_location("streamlit_app_under_test", shim)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from apps.ui.app import main

    assert module.main is main
    assert str(REPO_ROOT) in sys.path


def test_uv_lock_pins_cpu_torch_index() -> None:
    """Cloud resolves from uv.lock; GPU torch wheels would blow its disk/RSS."""
    lock = (REPO_ROOT / "uv.lock").read_text()
    assert "https://download.pytorch.org/whl/cpu" in lock
    for hint in ("cu118", "cu121", "cu124", "cu126", "cu128", "rocm"):
        assert f"/whl/{hint}" not in lock, hint


def test_python_version_file_matches_requires_python() -> None:
    """`.python-version` (uv, pyenv, Cloud reviewers) agrees with pyproject."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', pyproject)
    assert match is not None
    requires = match.group(1)
    version = (REPO_ROOT / ".python-version").read_text().strip()
    assert re.fullmatch(r"3\.\d+", version), version
    assert version in requires, (version, requires)


@pytest.mark.slow
def test_committed_seed_gz_inflates_to_canonical_counts(tmp_path: Path) -> None:
    from apps.ingest.sqlite_pipeline import CANONICAL_COUNTS

    seed_gz = REPO_ROOT / "data" / "seed" / "homelib.sqlite.gz"
    assert seed_gz.is_file(), "commit data/seed/homelib.sqlite.gz (just seed-gz)"
    assert seed_gz.stat().st_size < 50 * 1024 * 1024, "keep under GitHub's 50 MB file limit"
    target = tmp_path / "homelib.sqlite"
    with gzip.open(seed_gz, "rb") as src, target.open("wb") as dst:
        dst.write(src.read())
    conn = sqlite3.connect(target)
    try:
        counts = {
            table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in CANONICAL_COUNTS
        }
    finally:
        conn.close()
    assert counts == CANONICAL_COUNTS


def test_require_sqlite_path_inflates_once_and_refuses_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps import inprocess_bridge as bridge

    # A tiny stand-in seed: real gzip, real SQLite, not the 29 MB artefact.
    small = tmp_path / "small.sqlite"
    conn = sqlite3.connect(small)
    conn.execute("CREATE TABLE books (book_id TEXT)")
    conn.execute("INSERT INTO books VALUES ('b1')")
    conn.commit()
    conn.close()
    seed_gz = tmp_path / "seed.sqlite.gz"
    with small.open("rb") as src, gzip.open(seed_gz, "wb") as dst:
        dst.write(src.read())

    # Inside the repo: inflate once, then a no-op.
    target = REPO_ROOT / "data" / f"_test_inflate_{tmp_path.name}.sqlite"
    try:
        assert bridge.inflate_seed_if_missing(target, seed_gz) is True
        assert target.is_file()
        assert bridge.inflate_seed_if_missing(target, seed_gz) is False
        assert not target.with_name(target.name + ".inflating").exists()
    finally:
        target.unlink(missing_ok=True)

    # Outside the repo, or via `..`: refused before anything is written.
    with pytest.raises(RuntimeError):
        bridge.inflate_seed_if_missing(tmp_path / "elsewhere.sqlite", seed_gz)
    with pytest.raises(RuntimeError):
        bridge.inflate_seed_if_missing(REPO_ROOT / "data" / ".." / ".." / "x.sqlite", seed_gz)
    # Inside the repo but outside data/ (pytest's basetemp lives here under `just ci`).
    with pytest.raises(RuntimeError):
        bridge.inflate_seed_if_missing(REPO_ROOT / ".pytest-tmp" / "x.sqlite", seed_gz)
    assert not (REPO_ROOT / ".pytest-tmp" / "x.sqlite").exists()
    assert not (tmp_path / "elsewhere.sqlite").exists()
