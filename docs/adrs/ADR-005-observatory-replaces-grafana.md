# ADR-005 — Observatory replaces Grafana

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** Pavlo (owner)
- **Related:** `specs/product.md` §5.1 / WP10, v1 Grafana dashboard, `docs/plan-v2.md` §4

## Context

v1 criterion 7 is a Grafana OSS container with six provisioned panels plus a live feedback loop. A public Streamlit showcase cannot assume reviewers will open a second origin on port 3001, and Community Cloud will not run Grafana.

## Decision

**Ship monitoring as an in-app Observatory** (Streamlit page over `query_log` / feedback aggregates). Grafana is not part of the v2 product. v1 Grafana remains on the fallback tag.

WP10 still requires user feedback plus at least five populated charts. Query logging starts in earlier service WPs.

## Consequences

**Positive** — one URL for reviewers; demo traffic can fill charts in-process; no Grafana password in the cloud demo.

**Negative** — lose Grafana's query explorer; must re-verify the feedback UI→service→DB loop that v1 already proved live; compose can drop the grafana service only after Observatory is green (not this PR).
