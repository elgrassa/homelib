# spec: observatory — in-app monitoring (replaces Grafana)

**Implemented by:** WP10 (charts); query logging starts in earlier service WPs.
**Consumed by:** `GET /v1/observatory`, Streamlit Observatory page.
**ADR-005:** Grafana is not part of the v2 product. v1 Grafana remains on
`v1-fallback`. `specs/monitoring.md` is the v1 implementation spec.

## Purpose

Rubric monitoring = user feedback **and** ≥5 populated charts on one URL.
Community Cloud will not run Grafana. Default logs store a query hash, not
raw personal text.

## Public interface

```python
class ObservatoryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bucket: str                 # ISO time or category label
    value: float
    series: str | None = None   # e.g. "p50" / "p95" / "up"

class ObservatoryChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    points: list[ObservatoryPoint]

class ObservatoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generated_at: datetime
    charts: list[ObservatoryChart]    # len >= 5 when demo_traffic has run
    app_mode: str
```

`query_log` columns: port v1 (`specs/monitoring.md` / `specs/indexing.md`)
plus `principal_id` / `demo_session_id`. `degraded boolean NOT NULL DEFAULT
false` stays — v1 contradiction that was real.

## Data contracts (field-level)

Product §9.3 required charts (map to v1 Grafana panels where they match):

```
1. queries_over_time          -- count(*) by time bucket
2. latency_p50_p95            -- percentile_cont 0.5 and 0.95
3. retrieval_mode_usage       -- count by arm
4. feedback_ratio             -- up / (up+down) where feedback IS NOT NULL
5. degraded_or_no_result      -- degraded OR empty-hit rate
6. connector_failures         -- optional 6th; 0 until WP05
7. token_or_cost_estimate     -- optional; sum tokens (v1 panel 5)
```

Ship **at least five** populated after `demo_traffic.py --n 40`. Public demo
logs normalized operational metadata + explicit feedback only.

Privacy: `query_sha256_prefix` always; `query_plaintext` opt-in, default NULL.
Demo: no raw query text.

## Error/degradation behavior

- Log write failure never fails `/v1/ask` (v1 rule, keep).
- Unknown `request_id` feedback → 404 (v1).
- Empty `query_log` → charts exist with empty `points`, not 500.
- `/v1/observatory` never includes query plaintext or API keys.

## Named red tests

- `test_observatory_returns_at_least_five_chart_ids`.
- `test_observatory_never_includes_plaintext_or_keys`.
- `test_query_never_stored_plaintext_by_default` — port from monitoring.md.
- `test_record_feedback_unknown_request_id_returns_false`.

## Verify

```
uv run pytest -k 'observatory or query_never_stored' -v
uv run python scripts/demo_traffic.py --n 40   # after WP10 wiring
```
