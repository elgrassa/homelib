# ADR-004 — SQLite replaces Postgres

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** Pavlo (owner)
- **Related:** `specs/product.md` §7.4–§7.5, `docs/plan-v2.md` §0.6 / §4, ADR-001
- **Supersedes:** v1 Postgres + pgvector as the *target* store (v1 compose stays until WP02)

## Context

v1 retrieval runs on Postgres FTS + pgvector. That stack is verified and tagged `v1-fallback`. v2's public showcase and home edition both need a single-file, resettable, Community-Cloud-friendly store. Reviewer Compose should not require a second database engine.

Seed `.sqlite` files are not byte-reproducible across machines (SQLite headers, rowids, WAL). Treating them as byte-stable artifacts would fail honest rebuilds.

## Decision

**Drop Postgres/pgvector as the v2 product store. Use SQLite + FTS5 + a cached NumPy embedding matrix keyed by index revision.**

- Lexical arm: FTS5 (BM25).
- Vector arm: float32 matrix in memory (product §7.5); do not decode per-query BLOBs.
- Verify seeds by canonical row counts + logical checksums, not file bytes. v1 JSONL snapshot byte-stability still holds for *inputs*.
- This PR does not change running compose. WP02 implements migrations.

## Consequences

**Positive** — one engine for demo and home; Community Cloud can ship a seed file; v1 fallback remains on Postgres.

**Negative** — two stores exist until WP02 cutover; FTS5/NumPy must re-earn ADR-001's measured arm choice; WAL/busy-timeout/FK discipline is new operational surface.

**Addendum 2026-09-05** — the dispatch predicate (`HOMELIB_SQLITE_PATH` non-empty)
now also covers `answer._book_metadata` and `agent.search_catalog`. Until then the
tip degraded every answer on a SQLite-only host ("failed to load book metadata")
because retrieval had moved to SQLite while synthesis still looked titles up in
Postgres. Reviewer path unaffected only because compose still runs Postgres.
