# ADR-002 — Catalog source: Open Library, and three rejections

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** Pavlo (owner)
- **Supersedes / superseded by:** —
- **Related:** `specs/corpus.md` §"Banned sources (binding)", `specs/roadmap.md`

## Context

The roadmap builder recommends books the reader does not yet own. That needs a
book-metadata catalog — title, authors, subjects, and ideally a description —
much larger than the 18-book demo corpus. The corpus itself (full text) is a
separate, already-settled question: Project Gutenberg public-domain texts,
pinned by sha256 in `data/manifest.yaml`.

This repository is public. Whatever the catalog is, its bytes get pushed to a
public git remote and stay in the history. So the only workable test is not
"can I download this?" but **"may I redistribute this, publicly, forever?"** —
a much narrower question, and the one that eliminated three otherwise obvious
candidates.

The pressure to cut this corner is real: this is a deadline-bound capstone, the
rejected options are one `kagglehub.download()` away, and nobody grading it
would likely notice. That is exactly why the decision is written down.

## Decision

**Use Open Library `search.json`, queried as ~14 curated subject slices.**

Result: 3,061 deduplicated works in `data/catalog.jsonl`, with a `_provenance`
header line naming the source and fetch date. Subject coverage 99.97%.

Open Library is run by the Internet Archive, which asserts no rights over the
bibliographic metadata itself and publishes it for reuse. Querying the public
`search.json` endpoint for a bounded set of subjects — rather than pulling the
~4 GB works dump — keeps the request volume modest and the result auditable.

**Known cost, accepted:** `search.json` returns no `description` field at all;
descriptions live only on the per-work endpoint, which would mean thousands of
extra requests. The roadmap was already specified to generate its own rationale
from the retrieved text and to treat descriptions as optional, so this costs
nothing that was actually being used. Measured, not assumed: description
coverage is 0%, recorded in `docs/evidence.md`.

## Rejected options

### 1. Kaggle "15K+ Books Across 100+ Categories" — banned in any form

The single most tempting option: one file, clean columns, already tabular, and
carrying a **CC0** badge on Kaggle.

Rejected because **the dataset's own description states it was scraped from the
Google Books API.** That makes the CC0 badge unenforceable: the uploader cannot
release under CC0 what was never theirs to license. A permissive label applied
by someone who lacked the right to apply it grants nothing to a downstream user.

Google's API Terms of Service prohibit scraping the API, building a derivative
database from its results, retaining permanent copies, and redistributing them.
A public GitHub repository would do all four at once.

The ban is deliberately **total**, covering:

- committing the CSV,
- a build-time re-download (`kagglehub`, a URL in a script, a CI step),
- and **using only a "harmless" subset of fields such as title and author.**

The last one matters most, because it is the form the shortcut would actually
take. Selecting columns from a database that was assembled in breach of the
terms it was assembled under does not launder its provenance; it just makes the
breach smaller and harder to see.

### 2. Google Books API directly — unusable

Same clauses, applied one step earlier in the chain. Going to the source rather
than to someone else's scrape of the source removes the licensing-fiction
problem but not the ToS problem: no scraping, no derivative database, no
redistribution of results. A public repo needs all three.

### 3. UCSD Goodreads Book Graph — unusable

A different licence family with the same outcome. Its terms restrict use to
non-commercial academic research **and** forbid redistribution. This project is
neither academic research nor non-redistributing, so it fails on both counts
independently — either one alone would be disqualifying.

## Consequences

**Positive**
- The repository can be made public, and stay public, without a licensing
  liability sitting in its git history where it cannot be deleted.
- Provenance is stated in-band: `data/catalog.jsonl`'s first line records
  source and fetch date, so a reviewer can check the claim without trusting
  this document.
- 3,061 works across 14 subjects is ample for roadmap recommendations. The
  constraint cost the project nothing it needed.

**Negative**
- No descriptions, as above. Accepted, with the mitigation already in the spec.
- Open Library's subject tagging is uneven, so slice sizes vary by subject.
- Fewer records than the 15k the rejected set offered. This never mattered:
  the roadmap surfaces a handful of books per user, not thousands.

**Enforcement — the part that makes this ADR more than a good intention**

`apps/ingest/tests/test_fetch_catalog.py::test_kaggle_source_absent_from_pipeline`
greps the entire `apps/ingest` tree and fails on any `import kaggle`,
`from kaggle`, `kaggle.com`, `kagglehub`, or a filename containing "kaggle".
It matches functional footprints only, so prose explaining the ban — including
this paragraph's subject — does not trip it.

A decision recorded only in a document decays the moment someone is in a hurry.
A decision recorded as a **failing test** is one a future session cannot quietly
undo, including a future session of mine that has forgotten this file exists.

## Verification

```bash
# Provenance header and record count
head -1 data/catalog.jsonl
wc -l data/catalog.jsonl

# The ban is enforced, not merely documented
uv run pytest apps/ingest/tests/test_fetch_catalog.py -k kaggle -v
```

## Notes on sourcing

The restrictions above are summarised, not quoted verbatim: they paraphrase the
relevant clauses of the Google APIs Terms of Service and the UCSD Book Graph
dataset terms as they read when this decision was made (2026-08-30). Terms
change. Anyone revisiting this decision should re-read the current terms rather
than rely on this summary — and should treat a change in those terms, not
convenience, as the only reason to reopen it.
