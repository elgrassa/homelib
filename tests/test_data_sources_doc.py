"""docs/data-sources.md must agree with the pinned artefacts it describes."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "data-sources.md"

_PATH_RE = re.compile(
    r"`((?:apps|data|docs|evals|packages|specs|docker|scripts)/[\w./+-]+\.(?:py|md|yaml|yml|jsonl|gz|json|sql|toml|sh))(?::\d+(?:-\d+)?)?`"
)


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_data_sources_doc_names_the_dataset_and_the_api() -> None:
    text = _doc()
    assert "Project Gutenberg" in text
    assert "Open Library" in text and "search.json" in text
    # The public demo runs on the committed SQLite seed, not on a live store.
    assert "data/seed/homelib.sqlite.gz" in text
    assert "sub-second" in text


def test_data_sources_doc_matches_manifest_and_catalog() -> None:
    text = _doc()
    manifest = (REPO_ROOT / "data" / "manifest.yaml").read_text(encoding="utf-8")
    book_ids = re.findall(r"^- book_id:\s*(\S+)", manifest, flags=re.MULTILINE)
    assert len(book_ids) == 18
    assert f"{len(book_ids)} public-domain books" in text or f"{len(book_ids)} books" in text
    for book_id in book_ids:
        assert f"`{book_id}`" in text, book_id

    catalog_lines = (REPO_ROOT / "data" / "catalog.jsonl").read_text(encoding="utf-8").splitlines()
    assert catalog_lines[0].startswith('{"_provenance"')
    works = len(catalog_lines) - 1
    assert f"{works:,}" in text, works

    ground_truth = (REPO_ROOT / "evals" / "ground_truth.jsonl").read_text(encoding="utf-8")
    questions = len([line for line in ground_truth.splitlines() if line.strip()])
    assert f"{questions} " in text, questions


def test_data_sources_doc_cites_only_existing_paths() -> None:
    missing = sorted({path for path in _PATH_RE.findall(_doc()) if not (REPO_ROOT / path).exists()})
    assert missing == [], missing


def test_readme_links_to_data_sources_doc() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/data-sources.md" in readme
