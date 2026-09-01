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
docker compose -p homelib --env-file .env -f docker/docker-compose.yml up -d --build
docker compose -p homelib --env-file .env -f docker/docker-compose.yml --profile seed run --rm ingest
open http://localhost:8501
```

Neither flag is optional, and both exist because the compose file lives in
`docker/`:

- `--env-file .env` — Compose treats `docker/` as the project directory and
  looks for `docker/.env`, so without this it starts Postgres with a blank
  password. It warns rather than failing, so the stack boots misconfigured.
- `-p homelib` — Compose otherwise names the project after that same
  directory, i.e. `docker`. That collides with any other project on your
  machine laid out the same way, and it means a Docker restart can bring the
  stack back attached to a different, empty volume while the seeded one sits
  untouched. Both observed here.

`just up && just seed` does all of this for you and refuses to run without a
`.env`, which is the recommended path.

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

## Evaluation results

**Retrieval.** 4 arms × 235 ground-truth questions, k=5, **0 degraded across all
940 arm-runs** — every row measures the arm it names, not a silent fallback.

| arm | hit-rate@5 | MRR@5 |
|---|---:|---:|
| `lexical` | 0.072 | 0.066 |
| `vector` | 0.106 | 0.092 |
| `hybrid` | 0.174 | 0.152 |
| **`hybrid_rerank`** | **0.174** | **0.167** |

Fusion is where the gain is: hybrid beats the better single arm by **+64%**
(0.174 vs 0.106) because lexical and vector fail on different questions.
Rerank lifts MRR (0.152 → 0.167) and leaves hit-rate flat — that's exactly
what a reranker does; it reorders a fixed candidate set, it can't retrieve
what fusion didn't surface. Query rewriting was measured on a matched 80-row
sample and **rejected**: 0.150/0.144 hit-rate/MRR with rewrite off vs.
0.150/0.138 with it on — a recorded negative result, not an oversight.
Production runs `hybrid_rerank` ([ADR-001](docs/adrs/ADR-001-retrieval-arm.md)).

0.174 reads low, so it was checked rather than reported bare. A 60-question
proximity probe over the same index asked not "was the labelled chunk
retrieved" but "was anything near it retrieved": exact-chunk hit-rate is
0.133, but the **correct book** is in the top-5 65.0% of the time and the
**correct section** 40.0% of the time, across 18 books (chance is 5.6%).
Both things are true at once — the metric is single-positive and
chunk-exact, so a neighbouring chunk with equally relevant prose scores as a
total miss, which understates usefulness; and 0.650 book-level accuracy is
not a good score in absolute terms either, so there is real headroom too.
Full reasoning in [ADR-001](docs/adrs/ADR-001-retrieval-arm.md).

**LLM answer quality.** 4 prompt arms — 3 challengers plus the production
prompt as a control — × 30 questions, scored by an LLM judge with bias
control. **Null result:** run-to-run variance (spread up to 0.47 across four
repeated runs) exceeded the entire between-arm spread within a single run
(0.34), and the ranked winner flipped between runs, so the incumbent prompt
stays. A hedging guard also flagged the top-scoring arm (`stepwise`) as
**unproven**: it declined to cite anything more often than any other arm
(7/30 questions), and a zero-citation decline still counts as a success, so
an arm that hedges has less for a judge with almost no dynamic range to mark
down. This is stated as the honest outcome it is, not a failure to hide —
the eval infrastructure (judge, bias control, hedging guard) worked exactly
as designed; the measured difference between prompts is below its noise
floor. Full reasoning in [ADR-003](docs/adrs/ADR-003-answer-prompt.md).

**Regression gate.** Both evals have measured baselines with margins in
[`evals/eval-baseline.json`](evals/eval-baseline.json), an append-only run
history, and a rule that a metric missing from a run counts as a regression
rather than being silently skipped.

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

## Rubric self-audit

Mirrors [`CHECKLIST.md`](CHECKLIST.md) section A, the current graded status
against the LLM Zoomcamp 2026 rubric. Status vocabulary is deliberately
strict there: `done` means verified by a command whose output is recorded in
[`docs/evidence.md`](docs/evidence.md), not "the code exists."

| Criterion | Points | Status | Evidence |
|---|---:|---|---|
| Problem description | 2 | done | Stated in user terms above — unsearchable shelf, unplanned reading order |
| Retrieval flow (KB + LLM) | 2 | done | Postgres FTS + pgvector + grounded, citation-validated answers — [`packages/homelib-rag`](packages/homelib-rag), [`apps/api/main.py`](apps/api/main.py) |
| Retrieval evaluation | 2 | done | 4 arms × 235 questions, 0 degraded — [`evals/results/retrieval.md`](evals/results/retrieval.md), [ADR-001](docs/adrs/ADR-001-retrieval-arm.md) |
| LLM evaluation | 2 | done | 4 prompt arms × 30 questions, judge with bias control; null result recorded — [`evals/results/llm_eval.md`](evals/results/llm_eval.md), [ADR-003](docs/adrs/ADR-003-answer-prompt.md) |
| Interface (UI or API) | 2 | done | Both — FastAPI (OpenAPI-pinned) and a 3-tab Streamlit UI — [`apps/api/main.py`](apps/api/main.py), [`apps/ui`](apps/ui) |
| Ingestion pipeline (e.g. dlt) | 2 | done | Real dlt source/resources, ELT into the canonical schema, 37 tests against a live Postgres — [`apps/ingest/pipeline.py`](apps/ingest/pipeline.py) |
| Monitoring (feedback + ≥5-chart dashboard) | 2 | done | 6 Grafana panels + feedback loop verified live end to end — [`docs/evidence.md`](docs/evidence.md) |
| Containerization | 2 | done | 7 services in one compose file, digest-pinned, healthchecked — [`docker/docker-compose.yml`](docker/docker-compose.yml) |
| Reproducibility | 2 | partial | Pins, snapshot and digests are done; the cold-clone drill (`just drill`) is mid re-run right now on a quiet machine — [`scripts/cold_clone_drill.sh`](scripts/cold_clone_drill.sh), [`docs/evidence.md`](docs/evidence.md) |
| Best practices — hybrid (1) + rerank (1) + rewrite (1) | 3 | done | All three implemented **and** measured. Rewrite's evaluation rejected it on evidence — under the course's own "if implemented and evaluated" rule, the measurement is the point earned, not a passing score — [ADR-001](docs/adrs/ADR-001-retrieval-arm.md) |

Floor without any bonus, on the statuses above: 19/21 confirmed done plus
reproducibility's partial credit. See `CHECKLIST.md` for the bonus rows
(cloud deployment, extras) and the engineering-quality checklist behind this
table.

## License

Apache-2.0. Demo corpus is public-domain text only; catalog metadata from Open
Library. Per-source provenance in [`data/manifest.yaml`](data/manifest.yaml).
