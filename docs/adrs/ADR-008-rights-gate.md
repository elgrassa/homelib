# ADR-008 — Rights gate (unknown fails closed)

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** Pavlo (owner)
- **Related:** ADR-002, `specs/corpus.md`, `specs/product.md` §6.2, `apps/ingest/tests/test_fetch_catalog.py`

## Context

v1 already banned Kaggle / Google Books / Goodreads (grep-enforced) and the course FAQ corpus. v2 adds user-extensible libraries and connectors. Unknown or ambiguous rights are the failure mode that would ship copyrighted full text into RAG.

## Decision

**Unknown rights fail closed.**

- Metadata may be searchable as metadata.
- Unknown-rights full text never enters RAG / FTS5 / the embedding matrix.
- Audio is not generated from unknown-rights text.
- UI explains the restriction; it does not silently omit the row.
- Ambiguous catalog editions never merge (product §6.3).

**Banned sources (carry forward, grep-enforced):** Kaggle, Google Books, Goodreads, Anna’s Archive, Sci-Hub, LibGen, and the DataTalks.Club course FAQ corpus. The existing Kaggle grep test stays; WP03 extends coverage to the other names in ingest/connectors without matching ban-prose.

## Consequences

**Positive** — public history cannot grow an undistributable corpus; ground truth stays on the lawful 18-book snapshot.

**Negative** — some Discover hits will be metadata-only; connectors must carry `rights_status` before index.
