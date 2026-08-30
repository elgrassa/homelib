# homelib

Your bookshelf is unsearchable, and your reading order is unplanned.

**homelib** ingests books in any format you own (EPUB, PDF — native or scanned,
TXT, Markdown, DjVu) into one universal document model, then puts three things
on top of it:

1. **Ask your library** — retrieval-augmented answers with **block-level
   citations** (book · chapter · page), so every claim is traceable to a passage.
2. **Reading roadmap** — say what you want to learn ("AI engineering, LLM
   harnesses, building a software business") and an agent composes an ordered,
   justified reading plan from a book catalog.
3. **Library view** — what's ingested, how it was extracted, and how well.

Everything runs **fully self-hosted**: `docker compose up` brings up Postgres
(FTS + pgvector), a local LLM, the API, the UI, and Grafana. A cloud API key is
an optional override, never a requirement.

> Status: in active development (LLM Zoomcamp 2026 capstone). See
> [`docs/evidence.md`](docs/evidence.md) for the build log and
> [`docs/course-map.md`](docs/course-map.md) for the course-module map.

## Quickstart

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml --profile seed run --rm ingest
open http://localhost:8501
```

## Development

```bash
uv sync --all-extras
just ci        # ruff + mypy --strict + pytest (90% coverage floor)
```

## License

Apache-2.0. Demo corpus is public-domain text only; catalog metadata comes from
Open Library. See [`data/manifest.yaml`](data/manifest.yaml) for per-source
provenance.
