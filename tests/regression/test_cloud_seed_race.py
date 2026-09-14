"""Regression for the 2026-09-14 Cloud *.inflating rename traceback."""

from __future__ import annotations

import gzip
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from apps import inprocess_bridge as bridge


def test_simultaneous_cold_starts_publish_seed_only_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge, "_DATA_DIR", tmp_path)
    target = tmp_path / "homelib.sqlite"
    seed = tmp_path / "seed.gz"
    payload = b"complete seed contents" * 1024
    seed.write_bytes(gzip.compress(payload))
    arrivals = threading.Barrier(2)
    checked = threading.local()
    original_is_file = Path.is_file

    def simultaneous_missing(path: Path) -> bool:
        result = original_is_file(path)
        if path == target and not getattr(checked, "done", False):
            checked.done = True
            # Both sessions must observe an absent DB before either writes it.
            arrivals.wait(timeout=10)
        return result

    monkeypatch.setattr(Path, "is_file", simultaneous_missing)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(bridge.inflate_seed_if_missing, target, seed) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(results) == [False, True]
    assert target.read_bytes() == payload
    assert not list(tmp_path.glob("*.inflating*"))
