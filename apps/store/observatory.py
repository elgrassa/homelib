"""Observatory aggregates from query_log — specs/observatory.md (WP10)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from apps.runtime_settings import read_app_mode

__all__ = [
    "ObservatoryChart",
    "ObservatoryPoint",
    "ObservatoryResponse",
    "build_observatory",
]


class ObservatoryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str
    value: float
    series: str | None = None


class ObservatoryChart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    points: list[ObservatoryPoint] = Field(default_factory=list)


class ObservatoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    charts: list[ObservatoryChart]
    app_mode: str


def build_observatory(conn: sqlite3.Connection) -> ObservatoryResponse:
    charts: list[ObservatoryChart] = []

    # 1. queries_over_time
    rows = conn.execute(
        "SELECT substr(ts, 1, 13) AS hour, COUNT(*) FROM query_log GROUP BY 1 ORDER BY 1"
    ).fetchall()
    charts.append(
        ObservatoryChart(
            id="queries_over_time",
            title="Queries over time",
            points=[ObservatoryPoint(bucket=str(r[0]), value=float(r[1])) for r in rows],
        )
    )

    # 2. latency_p50_p95 (approximate via ordered list)
    latencies = [
        int(r[0])
        for r in conn.execute("SELECT latency_ms FROM query_log ORDER BY latency_ms").fetchall()
    ]
    points: list[ObservatoryPoint] = []
    if latencies:
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
        points = [
            ObservatoryPoint(bucket="all", value=float(p50), series="p50"),
            ObservatoryPoint(bucket="all", value=float(p95), series="p95"),
        ]
    charts.append(ObservatoryChart(id="latency_p50_p95", title="Latency p50 / p95", points=points))

    # 3. retrieval_mode_usage
    arms = conn.execute(
        "SELECT arm, COUNT(*) FROM query_log GROUP BY arm ORDER BY 2 DESC"
    ).fetchall()
    charts.append(
        ObservatoryChart(
            id="retrieval_mode_usage",
            title="Retrieval mode usage",
            points=[ObservatoryPoint(bucket=str(r[0]), value=float(r[1])) for r in arms],
        )
    )

    # 4. feedback_ratio
    fb = conn.execute(
        "SELECT feedback, COUNT(*) FROM query_log WHERE feedback IS NOT NULL GROUP BY feedback"
    ).fetchall()
    charts.append(
        ObservatoryChart(
            id="feedback_ratio",
            title="Feedback ratio",
            points=[ObservatoryPoint(bucket=str(r[0]), value=float(r[1])) for r in fb],
        )
    )

    # 5. degraded_or_no_result
    deg = conn.execute("SELECT degraded, COUNT(*) FROM query_log GROUP BY degraded").fetchall()
    charts.append(
        ObservatoryChart(
            id="degraded_or_no_result",
            title="Degraded rate",
            points=[
                ObservatoryPoint(
                    bucket="degraded" if int(r[0]) else "ok",
                    value=float(r[1]),
                )
                for r in deg
            ],
        )
    )

    # 6. token_or_cost_estimate — cost when any row has been priced
    # (query_log.cost_usd > 0, C1/specs/monitoring.md), else the token sum
    # that shipped before pricing existed. A local/Ollama run never sets
    # LLM_PRICE_PER_1K_*, so cost_usd is 0 on every row and this falls back
    # to the original token chart rather than showing a fake $0 total.
    total_cost = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM query_log").fetchone()
    priced = float(total_cost[0] if total_cost else 0) > 0
    if priced:
        charts.append(
            ObservatoryChart(
                id="token_or_cost_estimate",
                title="Cost estimate (USD)",
                points=[
                    ObservatoryPoint(bucket="total_cost_usd", value=float(total_cost[0])),
                ],
            )
        )
    else:
        tokens = conn.execute(
            "SELECT COALESCE(SUM(tokens_prompt + tokens_completion), 0) FROM query_log"
        ).fetchone()
        charts.append(
            ObservatoryChart(
                id="token_or_cost_estimate",
                title="Token estimate",
                points=[
                    ObservatoryPoint(
                        bucket="total_tokens",
                        value=float(tokens[0] if tokens else 0),
                    )
                ],
            )
        )

    # 7. judged_relevance — C6's online judge (specs/monitoring.md). Counts
    # per `query_log.relevance` label (the judge's 1-5 sub-score, as a
    # string); empty until `scripts/judge_recent.py` has run, never an error.
    judged = conn.execute(
        "SELECT relevance, COUNT(*) FROM query_log "
        "WHERE relevance IS NOT NULL GROUP BY relevance ORDER BY relevance"
    ).fetchall()
    charts.append(
        ObservatoryChart(
            id="judged_relevance",
            title="Judged relevance",
            points=[ObservatoryPoint(bucket=str(r[0]), value=float(r[1])) for r in judged],
        )
    )

    return ObservatoryResponse(
        generated_at=datetime.now(UTC),
        charts=charts,
        app_mode=read_app_mode().value,
    )
