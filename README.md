# homelib

**Your bookshelf is unsearchable, and your reading order is unplanned.**

You own books — bought, downloaded, scanned — in a pile of incompatible formats.
Nothing searches across them. When a half-remembered argument matters, you can't
find the passage, and you certainly can't quote it with a page number. And when
you want to learn something new, choosing what to read next is guesswork
performed alone.

**homelib** ingests books in any format you own (EPUB, PDF — native *or*
scanned, TXT, Markdown, DjVu) into one universal document model, then puts three
things on top of it:

1. **Ask your library** — retrieval-augmented answers where every claim carries a
   **block-level citation**: book, chapter, page. You can check the machine.
2. **Reading roadmap** — say what you want to learn ("AI engineering, LLM
   harnesses, building a software business") and an agent composes an ordered,
   justified reading plan from a book catalog.
3. **Library view** — what's ingested, how it was extracted, and how well.

Everything runs **fully self-hosted**. `docker compose up` brings up Postgres
(full-text + pgvector), a local LLM, the API, the UI, and Grafana. A cloud API
key is an optional override, never a requirement — there is nothing to sign up
for.

---

## Quickstart

```bash
cp .env.example .env
docker compose --env-file .env -f docker/docker-compose.yml up -d --build
docker compose --env-file .env -f docker/docker-compose.yml --profile seed run --rm ingest
open http://localhost:8501
```

`--env-file` is not optional: the compose file lives in `docker/`, so Compose
treats that as the project directory and would otherwise start Postgres with a
blank password. `just up && just seed` does the same thing and checks for you.

Ports (`API_PORT`, `UI_PORT`, `GRAFANA_PORT`, `POSTGRES_PORT`, `OLLAMA_PORT`)
are overridable in `.env` if something already listens on a default.

| Service | Default | What it is |
|---|---|---|
| UI | http://localhost:8501 | Streamlit: ask, roadmap, library |
| API | http://localhost:8000/docs | FastAPI + Swagger — the full contract |
| Grafana | http://localhost:3001 | Provisioned dashboard, 6 panels |

---

## Architecture

```
     EPUB / PDF / scanned PDF / TXT / MD / DjVu
                      │
              parse_file()  ── per-format handlers, each returning an
                      │        ExtractionResult (native_text | ocr_fallback
                      │        | mixed) with a sha256 of what it extracted
                      ▼
                  BookDoc  ── ordered Blocks; every Block carries
                      │        section_path + char offsets + provenance
                      │        (PDF page / EPUB spine index + anchor)
                      ▼
              chunk_book()  ── block-aware, sentence-boundary chunks;
                      │        canonical_text[start:end] == text, exactly
                      ▼
        dlt pipeline ──────► Postgres
                               ├── chunks + tsvector (GIN)      lexical
                               ├── chunk_embeddings vector(384) semantic
                               ├── catalog (Open Library)       roadmap
                               └── query_log                    monitoring
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
      lexical / vector           RRF hybrid (k=60)          cross-encoder
       search arms                                             rerank
              └─────────────────────────┬─────────────────────────┘
                                        ▼
                         agent loop (function calling)
                    search_shelf · search_catalog · build_roadmap · get_block
                                        │
                                        ▼
                       answer with block-level citations
```

The **UI never touches the database.** It talks only through the public API, so
the API stays the single contract — and the Swagger page is the documentation.

## Data

**Shelf (full text).** 18 public-domain books from Project Gutenberg, chosen for
an engineering / business / self-education narrative — Franklin, Adam Smith,
Taylor, Ford, Thoreau, Mill, Strunk, and others. `data/manifest.yaml` pins each
by exact source URL, sha256 and licence note; every hash was computed from a
real download. Gutenberg's header/footer boilerplate is stripped so licence text
doesn't pollute retrieval. **729 blocks → 9,168 chunks.**

The parsed corpus is committed as `data/corpus_snapshot.jsonl.gz` (6 MB), so
reviewers seed the database offline and never re-download 18 books.

**Catalog (metadata).** 3,061 deduplicated works from **Open Library**, gathered
as curated `search.json` slices across 14 roadmap-relevant subjects. Internet
Archive asserts no rights over this metadata.

Two deliberate exclusions, recorded so they aren't quietly reintroduced: the
Kaggle "15K+ Books" dataset is **banned** — it was scraped from the Google Books
API, whose terms bar scraping and redistribution, and an uploader's CC0 badge
cannot re-license someone else's data. The Google Books API and the UCSD
Goodreads Book Graph are unusable for the same reason. A test greps the ingest
tree to enforce it.

Personal purchased ebooks stay local and git-ignored. Only public-domain text
is committed.

## Development

```bash
uv sync --all-extras
just ci      # ruff + mypy --strict + pytest, 90% coverage floor
just drill   # cold-clone reproducibility gate
```

Work is spec-first: every component has a one-page spec in [`specs/`](specs/)
written before its code, naming the data contract, the degradation behaviour,
and the tests it mandates. [`docs/evidence.md`](docs/evidence.md) is the build
log — including the defects found along the way and one diagnosis I got wrong
and had to retract.

## Course map

[`docs/course-map.md`](docs/course-map.md) maps every LLM Zoomcamp 2026 module to
where this project demonstrates it, with honest per-row status.

## License

Apache-2.0. Demo corpus is public-domain text only; catalog metadata from Open
Library. Per-source provenance in [`data/manifest.yaml`](data/manifest.yaml).
