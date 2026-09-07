"""OpenTelemetry tracing for `/v1/ask` — specs/monitoring.md's "Tracing" section.

One root span per request (`homelib.ask`, opened in `apps/api/main.py`), with
child spans for each pipeline stage (`rewrite`, `retrieve`, `rerank`, `llm`,
`cite`) so Observatory's `time_per_stage` chart and `GET /v1/traces/{trace_id}`
can show where latency actually goes. Spans never carry the raw question
text unless `HOMELIB_TRACE_QUESTIONS=1` (default off) — every attribute
`apps/api/main.py` sets uses the same sha256 prefix `query_log` already
stores.

Export target is `SqliteSpanExporter`, writing to the `spans` table
(migration 7 / Postgres equivalent in `docker/initdb/01-schema.sql`). It is
fed a `connect: Callable[[], sqlite3.Connection]` — the same Deps-style seam
the rest of `apps/api` uses — so a test can point it at an in-memory-backed
connection instead of a real file (`test_sqlite_span_exporter_roundtrip`).
`BatchSpanProcessor` is used for `APP_MODE=selfhosted` (compose, a separate
long-lived process — batching is free); `SimpleSpanProcessor` for
`APP_MODE=demo` (in-process Streamlit, which can exit mid-batch).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from pydantic import BaseModel, ConfigDict, Field

from apps.runtime_settings import AppMode, read_app_mode

__all__ = [
    "SERVICE_NAME",
    "SpanRecord",
    "SqliteSpanExporter",
    "TraceResponse",
    "TraceSpanNode",
    "build_span_tree",
    "force_flush_traces",
    "get_tracer",
    "read_trace_spans",
    "reset_tracer_for_tests",
]

logger = logging.getLogger(__name__)

SERVICE_NAME = "homelib-api"


class SqliteSpanExporter(SpanExporter):
    """Writes finished spans to the `spans` table (apps/store/sqlite.py's
    migration 7). `connect` is called once per export batch and the
    connection is used via `with`, matching every other `apps/api` sqlite
    helper's commit-then-close pattern.

    Never raises: a failed export is logged and reported as `FAILURE` to the
    SDK (which retries/drops per its own policy) — the same "monitoring must
    not become a new failure mode" rule `apps/api/main.py`'s `log_query`
    already follows.
    """

    def __init__(self, connect: Callable[[], sqlite3.Connection]) -> None:
        self._connect = connect

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            with self._connect() as conn:
                for span in spans:
                    # opentelemetry-sdk's ReadableSpan.get_span_context is
                    # untyped even under its own py.typed marker.
                    ctx = span.get_span_context()  # type: ignore[no-untyped-call]
                    if ctx is None:
                        continue
                    parent_id = format(span.parent.span_id, "016x") if span.parent else None
                    conn.execute(
                        "INSERT OR REPLACE INTO spans "
                        "(trace_id, span_id, parent_span_id, name, start_ns, end_ns, attributes) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            format(ctx.trace_id, "032x"),
                            format(ctx.span_id, "016x"),
                            parent_id,
                            span.name,
                            span.start_time or 0,
                            span.end_time or 0,
                            json.dumps(dict(span.attributes or {})),
                        ),
                    )
                conn.commit()
        except Exception:
            logger.warning("SqliteSpanExporter: failed to export spans", exc_info=True)
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


_provider_lock = threading.Lock()
_provider: TracerProvider | None = None


def _build_provider() -> TracerProvider:
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    from apps.api import sqlite_deps

    if sqlite_deps.sqlite_path() is not None:
        exporter = SqliteSpanExporter(sqlite_deps.open_store)
        if read_app_mode() is AppMode.DEMO:
            provider.add_span_processor(SimpleSpanProcessor(exporter))
        else:
            provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def get_tracer() -> trace.Tracer:
    """Process-wide lazy `Tracer`, matching `apps.api.main.get_deps`'s
    build-once-then-reuse pattern. With no `HOMELIB_SQLITE_PATH` configured,
    spans are still created (so `post_ask` never has to branch on it) but
    nothing is exported anywhere.
    """
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = _build_provider()
    return _provider.get_tracer(SERVICE_NAME)


def force_flush_traces(timeout_millis: int = 5_000) -> bool:
    """Flush pending BatchSpanProcessor exports so `/v1/traces/{id}` and
    Observatory's `time_per_stage` see the just-finished ask immediately.

    Selfhosted mode uses `BatchSpanProcessor` (specs/monitoring.md); without
    an explicit flush, a follow-up `GET /v1/traces/{trace_id}` right after
    `/v1/ask` can miss `llm`/`cite` (and their token attributes). Demo mode
    already uses `SimpleSpanProcessor` and is a no-op here. Returns True when
    flush succeeds or there is no provider yet.
    """
    provider = _provider
    if provider is None:
        return True
    return bool(provider.force_flush(timeout_millis))


def reset_tracer_for_tests(provider: TracerProvider | None = None) -> None:
    """Test seam: force the next `get_tracer()` call to rebuild (`None`), or
    adopt a caller-supplied provider — e.g. one wired to an in-memory
    exporter so a test can inspect spans without touching disk.

    Shuts down the OUTGOING provider first (flushing any `BatchSpanProcessor`
    while its exporter's `connect` callable is still valid) rather than just
    dropping the reference — otherwise a queued span exports later, on a
    background thread, after a test's `monkeypatch` has already reverted the
    env var `connect` depends on (e.g. `HOMELIB_SQLITE_PATH`), which
    `SqliteSpanExporter` then logs as a spurious export failure.
    """
    global _provider
    if _provider is not None:
        _provider.shutdown()
    _provider = provider


@dataclass(frozen=True, slots=True)
class SpanRecord:
    """One flat `spans` row, as read back from the store."""

    span_id: str
    parent_span_id: str | None
    name: str
    start_ns: int
    end_ns: int
    attributes: dict[str, Any]


def read_trace_spans(conn: sqlite3.Connection, trace_id: str) -> list[SpanRecord]:
    rows = conn.execute(
        "SELECT span_id, parent_span_id, name, start_ns, end_ns, attributes "
        "FROM spans WHERE trace_id = ? ORDER BY start_ns",
        (trace_id,),
    ).fetchall()
    return [
        SpanRecord(
            span_id=str(r[0]),
            parent_span_id=str(r[1]) if r[1] is not None else None,
            name=str(r[2]),
            start_ns=int(r[3]),
            end_ns=int(r[4]),
            attributes=json.loads(r[5]) if r[5] else {},
        )
        for r in rows
    ]


class TraceSpanNode(BaseModel):
    """One span in `GET /v1/traces/{trace_id}`'s response tree."""

    model_config = ConfigDict(extra="forbid")

    span_id: str
    name: str
    duration_ms: float
    attributes: dict[str, Any] = Field(default_factory=dict)
    children: list[TraceSpanNode] = Field(default_factory=list)


class TraceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    spans: list[TraceSpanNode] = Field(default_factory=list)


def build_span_tree(records: Sequence[SpanRecord]) -> list[TraceSpanNode]:
    """Nest flat `spans` rows into a tree by `parent_span_id`, children
    ordered by `start_ns` at every level.

    A row whose `parent_span_id` names a span absent from `records` is
    treated as an additional root rather than dropped — a trace exported by
    `BatchSpanProcessor` mid-flush can be incomplete, and a partial tree is
    more useful than a silently missing branch.
    """
    by_id = {r.span_id: r for r in records}
    children_of: dict[str | None, list[SpanRecord]] = {}
    for record in records:
        parent = record.parent_span_id if record.parent_span_id in by_id else None
        children_of.setdefault(parent, []).append(record)
    for group in children_of.values():
        group.sort(key=lambda r: r.start_ns)

    def _node(record: SpanRecord) -> TraceSpanNode:
        return TraceSpanNode(
            span_id=record.span_id,
            name=record.name,
            duration_ms=(record.end_ns - record.start_ns) / 1_000_000,
            attributes=record.attributes,
            children=[_node(child) for child in children_of.get(record.span_id, [])],
        )

    return [_node(record) for record in children_of.get(None, [])]
