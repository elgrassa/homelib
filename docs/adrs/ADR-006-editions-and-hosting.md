# ADR-006 — Editions and hosting

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** Pavlo (owner)
- **Related:** `specs/product.md` §4, `docs/plan-v2.md` §1, mockup `docs/mockups/00-home-topology.png`

## Context

HomeLib must satisfy a public capstone rubric (logged-out URL, Compose) and a real home topology (iPad/phone browser, projector, local model). Hosting choices that look convenient (Vercel, early Streamlit Cloud canary, Apple Foundation Models this week) fight memory, secrets, or the late-deploy owner decision.

## Decision

**Two editions from one codebase this week; a third later.**

| Edition | This week |
|---|---|
| Public showcase | Streamlit Community Cloud, `APP_MODE=demo`, app-owner cloud LLM, resettable seed, session-isolated mutable state. **Created on submission day (Sun Sep 7), not before.** Rehearse `APP_MODE=demo` locally. ONNX-vs-torch is decided against Community Cloud's *documented* memory limits, not a live canary. |
| Home / reviewer | Self-hosted Streamlit + FastAPI. **LM Studio preferred on Mac** (`host.docker.internal:1234/v1`). **Ollama for reviewer Compose.** Persistent SQLite in home; Compose still Postgres until WP02. |
| Persistent cloud trial | Post-capstone (product §15). |

**Rejected:** Vercel (wrong runtime: this is Streamlit/FastAPI + local/ONNX embeddings, not a JS serverless app).

**Apple Foundation Models:** Coming soon / reserved provider. The topology mockup is a metaphor, not a capstone-week ship requirement.

**GitHub public repo:** also created at the very end (same day as Cloud). Develop on Forgejo `v2`.

## Consequences

**Positive** — no early canary flapping; demo path stays dependency-light; Mac Metal stays on LM Studio.

**Negative** — first Cloud deploy is submission day (install, RSS, secrets, cold start). Mitigate by local demo rehearsal and measuring RSS against documented limits. Topology diagram must not be misread as "ship Apple FM by Sunday."
