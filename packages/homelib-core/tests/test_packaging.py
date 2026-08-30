"""Packaging invariants.

These are cheap to assert and expensive to discover later: a consumer that
installs homelib-core and gets no type information has no way to know the
marker was simply forgotten.
"""

from pathlib import Path

import homelib_core


def test_package_ships_py_typed_marker() -> None:
    """PEP 561: without this file, installed type hints are invisible to mypy.

    homelib-core is meant to be reusable (the LocalExpert read_document seam is
    the intended second consumer), so its types must survive installation, not
    only work in-tree where mypy reads the sources directly.
    """
    marker = Path(homelib_core.__file__).parent / "py.typed"
    assert marker.exists(), "homelib_core is missing its PEP 561 py.typed marker"


def test_public_names_are_exported() -> None:
    """The documented surface must be importable from the package root."""
    for name in (
        "BookDoc",
        "Block",
        "Chunk",
        "Provenance",
        "ExtractionResult",
        "CatalogEntry",
        "make_block_id",
    ):
        assert hasattr(homelib_core, name), f"homelib_core.{name} is not exported"
