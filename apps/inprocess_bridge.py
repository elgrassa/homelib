"""Wire InProcessClient for APP_MODE=demo (outside apps/ui AST boundary).

Streamlit Community Cloud runs one process — no FastAPI sidecar. This module
mounts the FastAPI app over httpx ASGITransport so Ask/Mentor/etc. reuse the
same route handlers and ``LLM_*`` env wiring as Compose, without a network hop.

Embeddings stay on local sentence-transformers (Cloud RSS risk — documented in
the PR; ONNX swap is out of scope unless tests require it).
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from apps.ui.api_client import ApiClient, InProcessClient

_INPROCESS_BASE = "http://homelib.inprocess"


def require_sqlite_path() -> Path:
    raw = os.environ.get("HOMELIB_SQLITE_PATH", "").strip()
    if not raw:
        raise RuntimeError(
            "APP_MODE=demo requires HOMELIB_SQLITE_PATH "
            "(seed SQLite path, e.g. data/homelib.sqlite)"
        )
    path = Path(raw)
    if not path.is_file():
        raise RuntimeError(
            f"HOMELIB_SQLITE_PATH is not a file: {path} "
            "(seed with the SQLite pipeline before demo mode)"
        )
    return path


def build_inprocess_client() -> InProcessClient:
    """Build an InProcessClient backed by the FastAPI app over ASGI."""
    require_sqlite_path()
    # Import after the sqlite path check so misconfig fails before heavy deps.
    from apps.api.main import app

    # httpx stubs type ASGITransport narrower than Client's transport param.
    transport: httpx.BaseTransport = httpx.ASGITransport(app=app)  # type: ignore[assignment]
    http_client = httpx.Client(transport=transport, base_url=_INPROCESS_BASE)
    delegate = ApiClient(_INPROCESS_BASE, http_client=http_client)
    return InProcessClient(delegate=delegate)
