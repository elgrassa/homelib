"""Streamlit Community Cloud entrypoint.

Cloud runs one file from the repository root; the product lives in
`apps/ui/app.py`, which Compose runs as `streamlit run apps/ui/app.py`. This
shim keeps one UI: it puts the repo root on `sys.path` (Cloud's working
directory is the checkout, but the `apps` package is not installed) and calls
the same `main()`.

Edition wiring happens inside `main()`: `APP_MODE=demo` from `st.secrets`
selects the in-process FastAPI client (`apps/inprocess_bridge.py`) over the
committed seed SQLite (`data/seed/homelib.sqlite.gz`, inflated once on cold
start). Nothing here reads secrets or opens a database.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.ui.app import main  # noqa: E402  (path must be set first)

if __name__ == "__main__":
    main()
