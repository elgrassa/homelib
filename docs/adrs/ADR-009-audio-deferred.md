# ADR-009 — Audio deferred

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** Pavlo (owner)
- **Related:** `specs/product.md` §4.1 / §5 (audio), mockup `07-mentor-session-voice.jpg`, ADR-010

## Context

The mentor mockup shows voice + live transcript. Product Home/Pro wants local TTS/STT and Silver Memory. Community Cloud, browser mic permissions, cost, and rights make production audio a scored-criterion risk this week.

## Decision

**One lawful public-domain preview this week. Everything else is Coming soon.**

- Schema may reserve `listen_progress` / audio capability flags.
- Do not ship TTS, STT, Silver Memory, or microphone capture in the capstone.
- Audio is **not** a scored this-week criterion. Cut order already puts full audio generation after the HTML prototype and several UX extras.
- Voice UI in mockups is directional, not acceptance for WP08/WP09.

## Consequences

**Positive** — no Cloud mic/privacy incident; rubric time stays on cited RAG, evals, ingest, Observatory, Compose.

**Negative** — mentor-session mockup will not match the shipped UI; listen progress stays unused until post-capstone.
