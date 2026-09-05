"""Wire InProcessClient for APP_MODE=demo (outside apps/ui AST boundary).

Streamlit Community Cloud runs one process — no FastAPI sidecar. This module
drives the FastAPI app over httpx's ASGITransport on a loop thread so Ask/Mentor/etc. reuse the
same route handlers and ``LLM_*`` env wiring as Compose, without a network hop.

Embeddings stay on local sentence-transformers (Cloud RSS risk — documented in
the PR; ONNX swap is out of scope unless tests require it).
"""

from __future__ import annotations

import asyncio
import functools
import gzip
import os
import shutil
import threading
from pathlib import Path
from typing import Any

import httpx

from apps.ui.api_client import ApiClient, InProcessClient

_INPROCESS_BASE = "http://homelib.inprocess"
# Committed, compressed copy of the seed store (built by `just seed-gz` from a
# `just seed-sqlite` run; ~29 MB). Community Cloud has no seed step and no
# Postgres, so the demo inflates this once on cold start when the configured
# HOMELIB_SQLITE_PATH does not exist yet. The .gz is the artefact; the inflated
# .sqlite stays gitignored.
SEED_GZ = Path(__file__).resolve().parent.parent / "data" / "seed" / "homelib.sqlite.gz"
_REPO_ROOT = Path(__file__).resolve().parent.parent


_DATA_DIR = _REPO_ROOT / "data"


def _inside_data_dir(target: Path) -> bool:
    """True only for paths under the repo's `data/` directory, with no `..`.

    The seed is the one file the bridge ever writes, and `data/` is the one
    place it belongs; "inside the repo" was too loose — pytest's basetemp and
    any other repo-local scratch would qualify.
    """
    if ".." in target.parts:
        return False
    resolved = target.resolve()
    return resolved.parent == _DATA_DIR or _DATA_DIR in resolved.parents


def inflate_seed_if_missing(target: Path, seed_gz: Path = SEED_GZ) -> bool:
    """Inflate the committed seed to `target` when `target` is absent.

    Returns True when a file was written. Refuses targets outside the repo's
    `data/` directory and any `..` segment: the path comes from configuration, and "write a 58 MB
    file wherever the environment says" is not a behaviour to have on a public
    host. Writes to a sibling temp file and renames, so a killed cold start
    never leaves a half-inflated store that SQLite would happily open.
    """
    if not _inside_data_dir(target):
        raise RuntimeError(f"refusing to inflate the seed outside data/: {target}")
    resolved = target.resolve()
    if resolved.is_file():
        return False
    if not seed_gz.is_file():
        return False
    resolved.parent.mkdir(parents=True, exist_ok=True)
    tmp = resolved.with_name(resolved.name + ".inflating")
    with gzip.open(seed_gz, "rb") as src, tmp.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    tmp.replace(resolved)
    return True


def require_sqlite_path() -> Path:
    raw = os.environ.get("HOMELIB_SQLITE_PATH", "").strip()
    if not raw:
        raise RuntimeError(
            "APP_MODE=demo requires HOMELIB_SQLITE_PATH "
            "(seed SQLite path, e.g. data/homelib.sqlite)"
        )
    path = Path(raw)
    if not path.is_file():
        # Cold start on a host with no seed step (Community Cloud): inflate
        # the committed seed once. A relative path is relative to the repo
        # root, which is Cloud's working directory. Paths outside data/ are
        # never written to; they fall through to the error below.
        candidate = path if path.is_absolute() else _REPO_ROOT / path
        if _inside_data_dir(candidate):
            inflate_seed_if_missing(candidate)
            if candidate.is_file():
                return candidate
    if not path.is_file():
        raise RuntimeError(
            f"HOMELIB_SQLITE_PATH is not a file: {path} "
            "(seed with the SQLite pipeline before demo mode, "
            "or commit data/seed/homelib.sqlite.gz)"
        )
    return path


class SyncASGITransport(httpx.BaseTransport):
    """Sync façade over ``httpx.ASGITransport`` for a blocking ``httpx.Client``.

    ``ASGITransport`` is async-only (``handle_async_request``); wrapped in a
    sync ``httpx.Client`` it raised ``AttributeError`` on the very first call,
    so the demo edition never answered anything until the Cloud rehearsal
    caught it (the ``type: ignore`` that made it type-check was the tell).
    This runs the ASGI app on one long-lived event-loop thread and returns
    fully buffered responses, so Streamlit's script thread can call the
    FastAPI routes exactly like the HTTP edition does. The request's read
    timeout is honoured and surfaces as ``httpx.ReadTimeout`` — the same
    exception the HTTP path raises — so ``ApiClient`` degrades identically.
    """

    def __init__(self, app: Any) -> None:
        self._asgi = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="homelib-inprocess-asgi", daemon=True
        )
        self._thread.start()

    async def _call(self, request: httpx.Request) -> httpx.Response:
        response = await self._asgi.handle_async_request(request)
        try:
            body = b"".join([chunk async for chunk in response.stream])  # type: ignore[union-attr]
        finally:
            await response.aclose()
        return httpx.Response(
            response.status_code, headers=response.headers, content=body, request=request
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()  # a buffered body satisfies ASGITransport's async-stream contract
        timeout = (request.extensions.get("timeout") or {}).get("read")
        future = asyncio.run_coroutine_threadsafe(self._call(request), self._loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError as exc:
            future.cancel()
            raise httpx.ReadTimeout("in-process request timed out", request=request) from exc

    def close(self) -> None:
        # Deliberately a no-op: the transport is shared across every
        # ``httpx.Client`` Streamlit builds per rerun, so a client closing
        # (``with``/GC) must not stop the loop under the next rerun's client.
        # The thread is a daemon and dies with the process.
        return None


@functools.cache
def _shared_transport(app: Any) -> SyncASGITransport:
    """One loop thread per app object per process: Streamlit builds a client
    on every rerun, and a thread per rerun would never be joined."""
    return SyncASGITransport(app)


def build_inprocess_client() -> InProcessClient:
    """Build an InProcessClient backed by the FastAPI app over ASGI."""
    require_sqlite_path()
    # Import after the sqlite path check so misconfig fails before heavy deps.
    from apps.api.main import app

    http_client = httpx.Client(transport=_shared_transport(app), base_url=_INPROCESS_BASE)
    delegate = ApiClient(_INPROCESS_BASE, http_client=http_client)
    return InProcessClient(delegate=delegate)
