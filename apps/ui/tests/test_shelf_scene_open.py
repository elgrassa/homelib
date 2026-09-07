"""Shelf scene hits must offer an in-UI open-passage control in demo mode.

Cloud demo has no :8502 companion, so hiding the clean-read link must not
leave only a caption that open_anchor resolves via GET /v1/blocks/.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
API = "http://homelib.test"


@pytest.fixture(autouse=True)
def _demo_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    # APP_MODE=demo without API_URL selects InProcess; keep HTTP so respx works.
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("API_URL", API)
    monkeypatch.delenv("HOMELIB_SQLITE_PATH", raising=False)
    monkeypatch.delenv("HOMELIB_OFFICIAL_VIEWER", raising=False)


@respx.mock
def test_demo_shelf_scene_hit_offers_open_this_passage() -> None:
    respx.post(f"{API}/v1/demo/session").mock(
        return_value=httpx.Response(
            200, json={"demo_session_id": "sess", "principal_id": "p"}
        )
    )
    respx.get(f"{API}/v1/books").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "book_id": "thoreau-walden",
                    "title": "Walden",
                    "authors": ["Henry David Thoreau"],
                    "blocks": 729,
                    "chunks": 9168,
                    "format": "txt",
                }
            ],
        )
    )
    block = {
        "block_id": "25a30321b30d03cc",
        "book_id": "thoreau-walden",
        "ordinal": 1,
        "section_path": ["Economy"],
        "text": "I went to the woods because I wished to live deliberately.",
        "char_start": 0,
        "char_end": 58,
        "provenance": {
            "format": "txt",
            "page": None,
            "spine_index": None,
            "anchor": None,
            "source_sha256": "abc",
        },
    }
    respx.get(f"{API}/v1/blocks/25a30321b30d03cc").mock(
        return_value=httpx.Response(200, json=block)
    )
    respx.get(url__regex=rf"{API}/v1/books/thoreau-walden/blocks.*").mock(
        return_value=httpx.Response(200, json=block)
    )

    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state["door"] = "Shelf"
    at.session_state["last_scene"] = {
        "book_id": "thoreau-walden",
        "mode_used": "smart",
        "hits": [
            {
                "open_anchor": "25a30321b30d03cc",
                "block_id": "25a30321b30d03cc",
                "quote": "I went to the woods",
            }
        ],
    }
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [b.label for b in at.button]
    assert "Open this passage" in labels
    assert not any("open_anchor resolves" in str(c.value) for c in at.caption)

    at.button(key="open_scene_passage_25a30321b30d03cc").click().run()
    assert not at.exception, [e.value for e in at.exception]
    visible = " ".join(str(getattr(t, "value", t)) for t in at.text)
    assert "live deliberately" in visible.lower()
    labels_after = [b.label for b in at.button]
    assert "Previous passage" in labels_after
    assert "Next passage" in labels_after
    assert "Continue in Projection" in labels_after
