"""The ingest User-Agent identifies the project, never a person (public-snapshot hygiene)."""

from __future__ import annotations

import re

from apps.ingest import fetch_catalog, fetch_corpus


def test_user_agent_has_no_email() -> None:
    for ua in (fetch_corpus.USER_AGENT, fetch_catalog.USER_AGENT):
        assert ua.startswith("homelib-ingest/")
        assert "+https://github.com/elgrassa/homelib" in ua
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", ua), ua
