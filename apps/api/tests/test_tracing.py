"""Behavioural tests for `apps.api.tracing` — C5 (specs/monitoring.md "Tracing").

`/v1/ask`'s own span wiring is exercised end-to-end in
`apps/api/tests/test_api.py` (dependency-override pattern, same as every
other endpoint test); this module covers the exporter and tree-building
logic in isolation.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from apps.api.tracing import SpanRecord, SqliteSpanExporter, build_span_tree, read_trace_spans
from apps.store.sqlite import connect, migrate


def _db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "spans.sqlite")
    migrate(conn)
    return conn


def test_sqlite_span_exporter_roundtrip(tmp_path: Path) -> None:
    """A span tree exported through `SqliteSpanExporter` reads back via
    `read_trace_spans` with the same names, attributes, and parent linkage —
    the same connection is reused for every export batch (the "Deps-style
    seam so tests can capture spans in memory" this module's docstring
    promises), never a fresh one per call."""
    conn = _db(tmp_path)
    exporter = SqliteSpanExporter(lambda: conn)
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("t")

    with tracer.start_as_current_span("homelib.ask") as root:
        ctx = root.get_span_context()
        assert ctx is not None
        trace_id = format(ctx.trace_id, "032x")
        root.set_attribute("query_sha256_prefix", "abc123")
        with tracer.start_as_current_span("retrieve") as child:
            child.set_attribute("hits", 5)

    records = read_trace_spans(conn, trace_id)
    names = {r.name for r in records}
    assert names == {"homelib.ask", "retrieve"}

    root_record = next(r for r in records if r.name == "homelib.ask")
    retrieve_record = next(r for r in records if r.name == "retrieve")
    assert root_record.parent_span_id is None
    assert retrieve_record.parent_span_id == root_record.span_id
    assert retrieve_record.attributes["hits"] == 5
    assert root_record.attributes["query_sha256_prefix"] == "abc123"


def test_sqlite_span_exporter_unknown_trace_id_returns_empty(tmp_path: Path) -> None:
    conn = _db(tmp_path)
    assert read_trace_spans(conn, "does-not-exist") == []


def test_build_span_tree_nests_by_parent_and_computes_duration() -> None:
    root = SpanRecord(
        span_id="a", parent_span_id=None, name="root", start_ns=0, end_ns=10_000_000, attributes={}
    )
    child = SpanRecord(
        span_id="b",
        parent_span_id="a",
        name="child",
        start_ns=1_000_000,
        end_ns=3_000_000,
        attributes={"k": 1},
    )

    tree = build_span_tree([child, root])  # deliberately out of start_ns order

    assert len(tree) == 1
    assert tree[0].name == "root"
    assert tree[0].duration_ms == 10.0
    assert len(tree[0].children) == 1
    assert tree[0].children[0].name == "child"
    assert tree[0].children[0].duration_ms == 2.0
    assert tree[0].children[0].attributes == {"k": 1}


def test_build_span_tree_treats_missing_parent_as_root() -> None:
    """A span whose parent_span_id names nothing in this batch (e.g. a
    partially flushed BatchSpanProcessor export) still renders — as an
    additional root — instead of being silently dropped."""
    orphan = SpanRecord(
        span_id="z",
        parent_span_id="does-not-exist-in-this-batch",
        name="orphan",
        start_ns=0,
        end_ns=1_000_000,
        attributes={},
    )

    tree = build_span_tree([orphan])

    assert [node.name for node in tree] == ["orphan"]


def test_build_span_tree_orders_children_by_start_ns() -> None:
    root = SpanRecord(
        span_id="a", parent_span_id=None, name="root", start_ns=0, end_ns=100, attributes={}
    )
    second = SpanRecord(
        span_id="b", parent_span_id="a", name="second", start_ns=50, end_ns=60, attributes={}
    )
    first = SpanRecord(
        span_id="c", parent_span_id="a", name="first", start_ns=10, end_ns=20, attributes={}
    )

    tree = build_span_tree([root, second, first])

    assert [child.name for child in tree[0].children] == ["first", "second"]
