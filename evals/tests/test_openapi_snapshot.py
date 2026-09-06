"""Contract-drift guard — see specs/api.md.

Asserts the generated OpenAPI schema (paths + methods, schema names, and each
schema's required fields) matches the committed `specs/openapi.snapshot.json`.
Changing the API surface means regenerating the snapshot in the same PR — the
diff on that file is deliberately visible in review, per specs/api.md's
"Contract-drift guard" section.

No live DB/LLM needed: `app.openapi()` only introspects route definitions and
Pydantic models, never calls a dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.api.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "specs" / "openapi.snapshot.json"


def _normalize_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Reduce a full OpenAPI document to the slice specs/api.md's
    contract-drift guard cares about: paths + HTTP methods, and every
    component schema's name + required-field set. Deliberately ignores
    descriptions/examples/titles so prose-only doc edits don't churn the
    snapshot — only a real shape change should.
    """
    paths = {path: sorted(methods.keys()) for path, methods in schema["paths"].items()}
    schemas = {
        name: sorted(component.get("required", []))
        for name, component in schema.get("components", {}).get("schemas", {}).items()
    }
    return {"paths": paths, "schemas": schemas}


def test_openapi_snapshot_matches() -> None:
    current = _normalize_openapi(app.openapi())
    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert current == committed, (
        "OpenAPI contract drifted from specs/openapi.snapshot.json. "
        "If this is a deliberate API change, regenerate the snapshot in the "
        "same PR (see specs/api.md's Contract-drift guard) rather than "
        "weakening this test."
    )


def test_snapshot_covers_every_endpoint_in_api_md() -> None:
    """A cheap independent check that the snapshot itself is not stale: every
    endpoint named in specs/api.md's table is present."""
    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    # v1 live surface (always required) plus v2 section 8 routes shipped in WP07-10.
    expected_paths = {
        "/health",
        "/v1/ask",
        "/v1/roadmap",
        "/v1/ingest",
        "/v1/feedback",
        "/v1/books",
        "/v1/books/{book_id}/blocks",
        "/v1/blocks/{block_id}",
        "/v1/traces/{trace_id}",
        "/v1/mentor/intake",
        "/v1/paths",
        "/v1/resources",
        "/v1/resources/{resource_id}/search",
        "/v1/playlists/current",
        "/v1/playlists/current/items",
        "/v1/playlists/current/items/{item_id}",
        "/v1/progress",
        "/v1/observatory",
        "/v1/audio/capabilities",
        "/v1/demo/session",
    }
    assert expected_paths == set(committed["paths"])


def test_ask_response_required_fields_match_spec() -> None:
    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert set(committed["schemas"]["AskResponse"]) == {
        "request_id",
        "answer",
        "citations",
        "arm_used",
        "degraded",
        "latency_ms",
        "tokens",
    }


def test_citation_required_fields_match_spec() -> None:
    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert set(committed["schemas"]["Citation"]) == {
        "chunk_id",
        # Not redundant with chunk_id. A chunk is the retrieval unit; a block
        # is the document unit a reader opens, and GET /v1/blocks/{block_id}
        # is keyed on the latter. Citations carried only chunk_id until the
        # cold-clone drill tried to resolve one and got a 404 — the UI's "show
        # full source" action had never worked. A citation nobody can open is
        # not a citation, so the id needed to open it is required here.
        "block_id",
        "book_id",
        "book_title",
        "section_path",
        "page",
        "quote",
    }
