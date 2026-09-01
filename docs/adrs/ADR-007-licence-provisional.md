# ADR-007 — Licence (provisional)

- **Status:** Accepted (provisional — legal review before commercial launch)
- **Date:** 2026-09-01
- **Deciders:** Pavlo (owner)
- **Related:** `specs/product.md` §4.6 and “Commercial split… (owner 2026-09-01)”, ADR-010, current tree `LICENSE` (Apache-2.0, v1)

## Context

The capstone must be a public GitHub repository. Public GitHub is **not** open source by default: GitHub requires an explicit licence to grant general rights to use, change, and distribute. GitHub terms still allow other users to **view and fork** a public repository. Public forks remain public if the origin is later made private. Technical secrecy therefore comes from never publishing premium source, not from trying to retract it.

This tree currently ships **Apache-2.0** from v1. That is too permissive if Home/Pro is a paid private product. Changing the licence is an owner sign-off before `just publish`, not a silent rewrite of git history.

## Decision

**Provisional public-capstone licence: PolyForm Noncommercial** on the public GitHub snapshot. A separate commercial licence for Home/Pro is sold later; paid-tier code lands in the **same Forgejo repo after** that snapshot is frozen and Forgejo is private (ADR-010). Not a second git remote this week.

- Never casually choose MIT or Apache-2.0 for the public capstone.
- AGPL requires source-sharing for networked modifications; it does **not** stop a compliant paid fork.
- BSL / BUSL-1.1 requires eventual OSS conversion. Use it only if that outcome is wanted. **It is not**, unless the owner says so.
- No technical mechanism makes self-hosted software uncopyable. The moat is the complete experience (UX, signed releases, updates, support, integrations, privacy), not obfuscation.
- Never commit premium code, signing keys, or proprietary visual assets **until after** the public GitHub push (see ADR-010). Public GitHub remains viewable/forkable.
- Protect the HomeLib name, logo, premium artwork, and product identity separately (trademark / asset control), not via the software licence alone.
- Entitlement for a fully offline paid product: locally verified signed licence file; app embeds only the public verification key; signing key never ships; no mandatory licence server or telemetry.

This PR does not replace `LICENSE`. Owner signs off PolyForm-NC before the public GitHub push (plan §1).

## Consequences

**Positive** — reviewers can study and run the capstone; commercial rights stay with Home/Pro; history stays free of premium blobs.

**Negative** — Apache-2.0 remains on `main` until the pre-publish licence swap; dependencies keep their own licences (SBOM / notices still required); PolyForm-NC must be legally reviewed before launch; public GitHub forks stay public even after Forgejo is made private.
