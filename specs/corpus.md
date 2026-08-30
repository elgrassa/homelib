# spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`

**Implemented by:** WP-08.
**Consumed by:** `apps/ingest/pipeline.py` (specs/ingestion.md), `search_catalog` /
`build_roadmap` agent tools.

## Purpose

Two independent, license-clean corpora committed (or sha-pinned) into the
repo so reviewers can build the entire demo **without network access**:
a full-text **Shelf** for RAG, and a metadata-only **Catalog** for the
book-roadmap feature. Neither corpus may touch data whose provenance is
legally tainted — see the banned-sources list below, which is binding, not
advisory.

## Public interface

```python
# apps/ingest/fetch_corpus.py
def main(argv: list[str] | None = None) -> int: ...
    # --fetch: download every book.manifest entry, verify sha256, strip
    #          Gutenberg boilerplate, parse via homelib_core.normalize.parse_file,
    #          append to data/corpus_snapshot.jsonl.gz
    # --verify-only: re-hash already-downloaded files against the manifest,
    #          exit non-zero on any mismatch, does not re-download

def strip_gutenberg_boilerplate(raw_text: str) -> str: ...
    # cuts everything before "*** START OF THE PROJECT GUTENBERG EBOOK" and
    # after "*** END OF THE PROJECT GUTENBERG EBOOK" (case-insensitive markers)

# apps/ingest/fetch_catalog.py
def main(argv: list[str] | None = None) -> int: ...
    # fetches Open Library search.json?q=subject:"<subject>" for each subject
    # in CATALOG_SUBJECTS, dedupes by ol_key, writes data/catalog.jsonl
```

## Data contracts (field-level)

`data/manifest.yaml` — one entry per Shelf book:

```yaml
- book_id: thoreau-walden
  title: Walden
  authors: [Henry David Thoreau]
  source_url: https://www.gutenberg.org/cache/epub/205/pg205.txt
  sha256: "<exact hex digest of the downloaded file, pinned>"
  license_note: "Public domain (US) — Project Gutenberg, no cost/restriction"
  format: txt
```

`data/corpus_snapshot.jsonl.gz` — gzipped JSONL, one line per `BookDoc`
(via `BookDoc.to_jsonl()`, specs/core-models.md), committed to git so
`--verify-only` and the ingestion pipeline never require network.

`data/catalog.jsonl` — one JSON object per line, each a `CatalogEntry`
(specs/core-models.md field-for-field), plus a first line that is a
provenance header (`{"_provenance": "Open Library search.json, curated
subject slices, fetched <date>"}`) rather than a `CatalogEntry` — the loader
in specs/ingestion.md skips any line starting with `_provenance`.

`CATALOG_SUBJECTS` (module constant, ~10–15 entries): roadmap-relevant
subjects such as `machine learning`, `software engineering`,
`entrepreneurship`, `management`, `distributed systems`, `deep learning`,
`data engineering`, `product management`, `technical writing`,
`system design` — each queried as `search.json?q=subject:"<subject>"`, never
the 4 GB Open Library works dump.

## Banned sources (binding)

- **Kaggle "15K+ Books Across 100+ Categories" — banned in any form,
  including a build-time re-download.** Its own dataset description states
  it was scraped from the Google Books API. Google's API Terms of Service
  bar scraping, building a derivative database, making permanent copies, and
  redistribution. The uploader's "CC0" badge on Kaggle cannot re-license data
  that was never Google's — or the uploader's — to relicense. This applies
  even if only a subset of fields (title/author) is used.
- **Google Books API — unusable directly**, for the same ToS reason: no
  scraping, no database-building, no redistribution of results.
- **UCSD Goodreads Book Graph — unusable directly**, same class of
  redistribution restriction; the dataset's own terms restrict use to
  non-commercial academic research and forbid redistribution, which a public
  GitHub repo violates on both counts.
- These three are recorded with source quotes in `docs/adrs/ADR-002-catalog-source.md`
  specifically so no later session re-proposes them having forgotten why.

## Error / degradation behavior

- `--fetch` on a sha256 mismatch after download: does **not** write the file
  into the snapshot, prints the expected vs. actual hash, and continues to
  the next manifest entry rather than aborting the whole run — one bad
  mirror should not block the other 20 books.
- `--verify-only` with zero downloaded files (fresh clone, snapshot-only
  path): reads `data/corpus_snapshot.jsonl.gz` directly and reports success —
  it never requires the raw downloads to be present, since the committed
  snapshot is the reviewer path.
- `fetch_catalog.py` on an Open Library request failure (timeout, 5xx):
  retries the single subject with backoff (3 attempts); after exhausting
  retries, logs a warning and continues with the remaining subjects — a
  missing subject slice degrades catalog coverage, it does not fail the run.
- Any book whose `parse_file` returns `ExtractionResult.method ==
  "extraction_failed"` is excluded from the snapshot and reported in the
  run's summary, not silently included as an empty `BookDoc`.

## Named red tests (write before the code)

- `test_manifest_shas_match_downloaded_files` — `--verify-only` against a
  fixture manifest + fixture files, tampered byte flips the sha and the
  command exits non-zero.
- `test_gutenberg_boilerplate_stripped` — a fixture raw text with real
  Gutenberg header/footer markers strips to just the book body.
- `test_catalog_dedupes_by_ol_key` — two subject slices returning the same
  `ol_key` produce one `CatalogEntry` in `data/catalog.jsonl`.
- `test_kaggle_source_absent_from_pipeline` — `apps/ingest` has no import,
  URL, or filename referencing "kaggle" anywhere (grep-based test, guards
  against reintroduction).
- `test_snapshot_verify_only_needs_no_network` — `--verify-only` runs
  against only the committed snapshot with `httpx` monkeypatched to raise on
  any call, and still succeeds.

## Verify

```
uv run python apps/ingest/fetch_corpus.py --verify-only
gunzip -c data/corpus_snapshot.jsonl.gz | wc -l
wc -l data/catalog.jsonl
uv run python -c "import json; rows=[json.loads(l) for l in open('data/catalog.jsonl') if not json.loads(l).get('_provenance')]; print(sum(1 for r in rows if r.get('subjects'))/len(rows))"
uv run pytest apps/ingest/tests -v
grep -ril kaggle apps/ingest/ || echo "no kaggle references"
```
