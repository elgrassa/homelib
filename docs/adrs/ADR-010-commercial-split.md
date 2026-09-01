# ADR-010 — Single repo until public; paid tier after

- **Status:** Accepted (supersedes the same-day “separate `homelib-commercial-private` tree this week” instruction)
- **Date:** 2026-09-01 (evening pivot)
- **Deciders:** Pavlo (owner)
- **Related:** `specs/product.md` §4.6 and “Commercial split…” appendix, ADR-007, ADR-006, ADR-009, `docs/plan-v2.md` §9
- **Note:** `docs/plan-v2.md` stays verbatim (it still names `homelib-commercial-private` in §9). This ADR + `docs/evidence.md` are the SOT for the pivot so a later session does not resurrect a second git remote this week.

## Context

A public GitHub snapshot cannot be unpublished (ADR-007: view/fork; public forks stay public). Paid/Home/Pro implementations in history at `just publish` time would ship with the capstone. A second commercial repository this week would split the scored work and is unnecessary: Forgejo `elgrassa/homelib` can become private *after* the public hash is frozen.

## Decision

**One repo until the capstone is public. Work continues in Forgejo `elgrassa/homelib` only.**

Sequence:

1. Finish **mandatory llm-zoomcamp scored criteria** in this repo. Never trade a scored criterion for polish / Home/Pro / rotunda / TTS.
2. **Owner** verifies locally, publishes to **public GitHub under `elgrassa`**, then creates the Streamlit Community Cloud app from that public repo. Agents do not create GitHub or Streamlit.
3. **After** that public snapshot is submitted (hash frozen): the Forgejo copy may be made **private and local-only**. Paid/Home/Pro features then land **in the same Forgejo repo**, not a second commercial remote.
4. Until the public GitHub push is done: **do not commit** premium/paid-tier implementations, signing keys, or proprietary assets — that history would be pushed with `just publish`. After Forgejo is private and is no longer the public mirror, paid features may be added in-tree.

### Post-public-publish / paid tier (same Forgejo repo later — not another git remote)

Do not implement these in the public snapshot this week. Public schema may have Coming-soon flags only (`specs/data-model.md`):

- arbitrary personal-book ingestion
- hardened EPUB/PDF/OCR pipelines
- persistent private conversations and artifacts (beyond capstone demo-session / single-principal paths)
- LM Studio discovery and model-management interface
- production local TTS/STT
- Silver Memory generation
- polished sphere and rotunda assets
- household profiles and LAN authentication
- backup, restore and migration
- Obsidian plugin
- native Apple companion
- installers, signed releases and automatic updates
- offline commercial licence verification

### Public app this week

Scored RAG + Streamlit/FastAPI + Compose + evals + Observatory. Showcase copy may stay on the demo:

> HomeLib Home — fully private self-hosted library
> Local AI · Personal books · Projector reading · No cloud transmission

May link to a landing page or waitlist. Streamlit Community Cloud = showcase, not guaranteed advertising. HTML prototype remains first in the cut order; paid sphere/rotunda assets are not this week.

### Product ladder

Free public showcase → paid Home/Pro **in the same Forgejo repo after it is private** → persistent cloud option → native Apple and Obsidian ecosystem.

### TTS / STT / Apple (post-public-publish; align with ADR-009)

- Foundation model: Mentor reasoning, summaries, structured artifacts (reserved provider)
- STT: voice-to-text
- TTS: narration
- Audio service: chapters, caching, playback, progress
- Future native Apple: Speech framework + AVSpeechSynthesizer — **distinct from** Apple Foundation Models
- Mac-hosted Streamlit: local Whisper-compatible STT + local TTS

### Obsidian (post-public-publish, contract-first — product §15)

- Safe Markdown export with stable HomeLib IDs + frontmatter
- Deep links
- Optional two-way plugin
- Commands: search, insert cited passages, Coffee Table, progress
- Scoped local API token via Obsidian SecretStorage
- Vault-folder opt-in, no telemetry
- Official Vault API + conflict-safe `Vault.process()`

## Consequences

**Positive** — one Forgejo remote for scored work; public GitHub history stays free of paid-tier blobs; paid features can still land without a second repo after Forgejo is private.

**Negative** — until `just publish`, every commit is potentially public; paid-tier code in this branch before that push is a leak. Public GitHub remains viewable/forkable under PolyForm-NC (ADR-007) even after Forgejo goes private.
