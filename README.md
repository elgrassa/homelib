# homelib

**Live demo:** https://homelib.streamlit.app/

**Your bookshelf is unsearchable, and your reading order is unplanned.**

You own books in incompatible formats. Nothing searches across them, so a
half-remembered argument is hard to find and harder to quote with a page.
Choosing what to read next is guesswork.

**homelib** ingests the books you own (EPUB, PDF — native or scanned, TXT,
Markdown, DjVu) into one document model, then puts three things on top:

1. **Ask** — retrieval-augmented answers with **block-level citations** you can open.
2. **Roadmap / Mentor** — an ordered reading plan from catalog + shelf evidence.
3. **Shelf / Observatory** — what is ingested, and how the system behaves under load.

The tip store is **SQLite FTS5 + a float32 embedding matrix**. Generation uses
**Groq** (`openai/gpt-oss-20b`) when `GROQ_API_KEY` is set. Ollama is an optional
local fallback. Never commit an API key.

**Submission commit:** record on `main` at submit time (see [`docs/evidence.md`](docs/evidence.md)).

Evaluation methodology: [`EVAL.md`](EVAL.md). Design choices and operating
cost/latency: [`TRADEOFFS.md`](TRADEOFFS.md), [`COST-LATENCY.md`](COST-LATENCY.md).

## Try (≈15 minutes)

**Hosted (no install):** open [homelib.streamlit.app](https://homelib.streamlit.app/)

1. **Ask** → `Who wrote Walden?` → expand a citation → **Show full source block**.
2. **Shelf** → confirm ~18 books / scene search → **Open this passage**.
3. **Observatory** → charts after traffic (empty on a cold seed is expected).

**Local SQLite (same runtime as the Cloud demo):**

```bash
git clone https://github.com/elgrassa/homelib.git
cd homelib
uv python install 3.13
uv sync --frozen --all-extras
cp .env.example .env
# set GROQ_API_KEY=… and leave LLM_API_KEY blank; HOMELIB_SQLITE_PATH=data/local-demo.sqlite
uv run --frozen --env-file .env streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501 — first launch inflates `data/seed/homelib.sqlite.gz`
when the target DB is missing. Docker Compose rebuilds ingestion + the full
stack: `just up && just seed && just seed-sqlite` (see below).

## What it looks like

Seven doors on one page: Ask, Mentor, Roadmap, Coffee Table, Shelf, Observatory,
Projection. These are real localhost captures from the SQLite demo, taken on
2026-09-11 at build `7c07138`. Click an image to inspect it at full size.
Generated answers and plans vary between runs; catalog records are metadata,
not full-text books.

**Ask:** a Walden question, its answer, and the supporting passage. Repeated
questions can use the answer cache; the example reports zero new tokens.

[![Ask — Walden answer with expanded source quotation](docs/screenshots/reviewer-02-ask-cited.jpg)](docs/screenshots/reviewer-02-ask-cited.jpg)

**Mentor:** a beginner path for “Learn how Adam Smith explains division of labour in The Wealth of Nations”, with interests “economics, division of labour”.
The complete two-step proposal and an expanded Smith citation are shown below.
Path acceptance depends on whether its steps resolve to full-text shelf books.

[![Mentor — complete Smith study path and supporting citation](docs/screenshots/reviewer-07-mentor.jpg)](docs/screenshots/reviewer-07-mentor.jpg)

**Roadmap:** an ordered book list with authors, rationale, prerequisites and
source provenance. For “Understand Adam Smith and the division of labour”, this run combines a catalog book with the full-text *Wealth of Nations*; accepting it adds the shelf book to Coffee Table.

[![Roadmap — two books with catalog and shelf provenance](docs/screenshots/reviewer-09-roadmap.jpg)](docs/screenshots/reviewer-09-roadmap.jpg)

**Coffee Table:** add a full-text book from the shelf, then open it in Projection
or remove it from the queue.

[![Coffee Table — Smith and Walden queued with Open and Remove controls](docs/screenshots/reviewer-08-coffee-table.jpg)](docs/screenshots/reviewer-08-coffee-table.jpg)

**Shelf:** the seeded full-text corpus, with per-book ingestion counts. This
capture shows the first inventory rows; the demo contains 18 books.

[![Shelf — current corpus counts and first inventory rows](docs/screenshots/reviewer-03-shelf.jpg)](docs/screenshots/reviewer-03-shelf.jpg)

**Discover:** search the committed Open Library catalog snapshot. Results link
to Open Library and explicitly identify records that are metadata only.

[![Discover — economics results with Open Library links and metadata labels](docs/screenshots/reviewer-06-discover.jpg)](docs/screenshots/reviewer-06-discover.jpg)

**Scene search:** choose a shelf book and describe a passage. Smart retrieval
can return related excerpts rather than an exact phrase match; use **Open this passage** to inspect the full source, then continue in Projection.

[![Scene search — Walden query, related excerpt and source-opening control](docs/screenshots/reviewer-10-scene-search.jpg)](docs/screenshots/reviewer-10-scene-search.jpg)

**Projection:** continue from a cited source or scene into the shelf reader.
The example shows a readable Walden chapter with Previous, Next and Save progress.

[![Projection — Walden chapter and reading controls](docs/screenshots/reviewer-05-projection.jpg)](docs/screenshots/reviewer-05-projection.jpg)

**Observatory:** query volume, latency, retrieval mode, feedback and degraded
responses are shown in five separate captures so labels remain readable.
These charts include historical seed traffic and local test requests; they are
not a quality score for the current Cloud deployment. The optional judged
relevance chart needs a separate evaluation run.

<details>
<summary>Open the five monitoring charts</summary>

[![Observatory — queries over time](docs/screenshots/reviewer-04-observatory-queries.jpg)](docs/screenshots/reviewer-04-observatory-queries.jpg)

[![Observatory — latency p50 and p95 with distinct series](docs/screenshots/reviewer-04-observatory-latency.jpg)](docs/screenshots/reviewer-04-observatory-latency.jpg)

[![Observatory — retrieval mode usage](docs/screenshots/reviewer-04-observatory-modes.jpg)](docs/screenshots/reviewer-04-observatory-modes.jpg)

[![Observatory — feedback counts](docs/screenshots/reviewer-04-observatory-feedback.jpg)](docs/screenshots/reviewer-04-observatory-feedback.jpg)

[![Observatory — degraded and successful responses](docs/screenshots/reviewer-04-observatory-degraded.jpg)](docs/screenshots/reviewer-04-observatory-degraded.jpg)

</details>

## System architecture

```mermaid
flowchart TD
    Reader([Reader]) --> Streamlit[Streamlit Crossroads]
    Streamlit --> FastAPI[FastAPI]
    FastAPI --> Shelf[Shelf search]
    Shelf --> Index[SQLite FTS5 plus float32]
    Index --> Passage[Cited passage open_anchor]
    Passage --> Reading[In-UI passage plus Projection]
    FastAPI --> Ask[Ask fixed RAG]
    Ask --> RetrAsk[Hybrid retrieve RRF k60 rerank]
    RetrAsk --> GroqAsk[Groq openai gpt-oss-20b]
    GroqAsk --> Cite[Citation validation]
    FastAPI --> Discover[Discover federation]
    Discover --> LiveAPIs[Open Library Gutendex]
    Discover -.-> CatSnap[OL catalog snapshot]
    FastAPI --> Mentor[Mentor run_agent max 2]
    Mentor --> Tools[search_shelf catalog get_block]
    Tools --> GroqMen[Groq]
    FastAPI --> Roadmap[Roadmap LLM catalog path]
    Roadmap --> CatSnap
    CatSnap --> GroqRoad[Groq]
    FastAPI --> Feedback["POST /v1/feedback"]
    Feedback --> QLog[(SQLite query_log)]
    Ask --> QLog
    Ask --> Spans[(OTel spans)]
    QLog --> Obs[Observatory 9 chart defs]
    Spans --> Obs
    Corpus[Ingested corpus text] --> DLT[dlt]
    DLT --> Blocks[BookDoc blocks]
    Blocks --> Chunks[Chunks 1200/200]
    Chunks --> SQLite[(SQLite tip)]
    Meta[OL catalog snapshot] --> CatTable[(catalog table)]
    CatTable --> SQLite
    DLT -.-> PG[(Postgres pgvector fallback)]
```

**Ask** is single-shot hybrid retrieve → rerank → Groq → citation validation.
**Mentor** alone runs `run_agent` (max 2 rounds). **Roadmap** is an LLM-assisted
catalog path. Shelf / Coffee Table / Projection do not call Groq.

Demo seed: **18 public-domain TXT books** (other parsers are tested, not in the
seed). Catalog metadata is a separate Open Library snapshot. Postgres + pgvector
remains the self-hosted fallback.

### Which LLM answers

| Edition | Model | Where it is set |
|---|---|---|
| Compose / local demo | Groq `openai/gpt-oss-20b` | `GROQ_API_KEY` in `.env` (`LLM_API_KEY` blank) |
| Optional `--profile local-llm` | Ollama `qwen2.5:7b-instruct` | `LLM_API_KEY=ollama` |
| Public Cloud demo | Groq free tier, same model | owner Streamlit Secrets; **100 LLM calls / visitor / UTC day** |

A missing model returns `degraded=true` with retrieval still shown — it does not invent citations.

```text
POST /v1/ask {"query": "Who wrote Walden?", "k": 5}
→ degraded: false · arm_used: hybrid_rerank
→ answer: Henry David Thoreau
→ citation opens GET /v1/blocks/… → 200
```

## Evaluation results

**Retrieval (SQLite tip, 2026-09-11 remapped).** 4 arms × **234** questions, k=5,
0 degraded. Labels were remapped after the September seed rebuild (161 of 235
moved; one dropped) — see
[`evals/results/retrieval-2026-09-11-remapped.md`](evals/results/retrieval-2026-09-11-remapped.md).
**Passage** hit-rate@5 and **book** hit-rate@5 are different metrics — book hit
is not answer accuracy.

| arm | passage hit-rate@5 | book hit@5 | MRR@5 |
|---|---:|---:|---:|
| `lexical` | 0.701 | 0.833 | 0.569 |
| `vector` | 0.474 | 0.915 | 0.364 |
| `hybrid` | 0.684 | 0.897 | 0.570 |
| **`hybrid_rerank` (app)** | **0.684** | **0.897** | **0.567** |

`lexical` leads passage hit on this label set because remapping scores shared
question terms (BM25-adjacent). Production stays on **`hybrid_rerank`**: better
book hit than lexical (0.897 vs 0.833), and `hybrid` matches the same chunk hit
at roughly a quarter of the latency. Rerank is flat vs hybrid here.

**Pre-drift archive (2026-09-06, 235 Q)** —
[`evals/results/retrieval.md`](evals/results/retrieval.md):

| arm | passage hit-rate@5 | book hit@5 | MRR@5 |
|---|---:|---:|---:|
| `lexical` | 0.064 | 0.077 | 0.055 |
| `vector` | 0.630 | 0.906 | 0.473 |
| `hybrid` | 0.638 | 0.906 | 0.483 |
| **`hybrid_rerank` (app)** | **0.638** | **0.906** | **0.572** |

Query rewrite was measured and left **off**. Floors:
[`evals/eval-baseline.json`](evals/eval-baseline.json). Archived check:
`just eval-gate`. Live bake-off: `python evals/retrieval_eval.py` /
`python evals/llm_eval.py`. Methodology: [`EVAL.md`](EVAL.md),
[ADR-001](docs/adrs/ADR-001-retrieval-arm.md), [ADR-003](docs/adrs/ADR-003-answer-prompt.md).

**LLM prompts.** Four arms including a `production` control; judge variance can
exceed between-arm spread, so the incumbent prompt stays (ADR-003).

### Monitoring

Open the **Observatory** door (or `GET /v1/observatory`): nine chart definitions
over SQLite `query_log` + OTel spans + thumbs feedback. Judged relevance stays
empty until an operator runs `scripts/judge_recent.py` (off by default).

```bash
HOMELIB_SQLITE_PATH=data/homelib.sqlite uv run python -m scripts.demo_traffic --n 40
```

## Quickstart — Docker Compose

```bash
cp .env.example .env   # paste GROQ_API_KEY=… ; never commit
just up && just seed && just seed-sqlite
# UI http://localhost:8501 · API http://localhost:8000/docs · health: curl -fsS http://localhost:8000/health
```

Both seeds are required: Postgres for the v1 Grafana path, SQLite for the tip
API/UI. Prefer `just …` over raw compose so `--env-file` and `-p homelib` stay
correct. Details and port overrides: [`.env.example`](.env.example).

## Data

Pinned artefacts — no re-download for the demo: 18 Gutenberg texts
(`data/corpus_snapshot.jsonl.gz`) and an Open Library **metadata** catalog
snapshot (`data/catalog.jsonl`). Provenance: [`docs/data-sources.md`](docs/data-sources.md),
[`data/manifest.yaml`](data/manifest.yaml).

## Development

```bash
uv sync --all-extras
just ci      # ruff + mypy --strict + pytest, 90% coverage floor
just drill   # cold-clone reproducibility gate
```

Specs in [`specs/`](specs/); build log in [`docs/evidence.md`](docs/evidence.md).
Maintainer maps (optional): [`docs/course-map.md`](docs/course-map.md),
[`docs/zoomcamp-2026-gap-report.md`](docs/zoomcamp-2026-gap-report.md).

## Rubric self-audit

Status vocabulary in [`CHECKLIST.md`](CHECKLIST.md): `done` means verified in
[`docs/evidence.md`](docs/evidence.md), not merely “code exists.”

| Criterion | Points | Status | Code evidence |
|---|---:|---|---|
| Problem description | 2 | done | [`README.md`](README.md) (problem + architecture) |
| Retrieval flow (KB + LLM) | 2 | done | [`answer.py`](packages/homelib-rag/src/homelib_rag/answer.py), [`hybrid.py`](packages/homelib-rag/src/homelib_rag/hybrid.py), [`apps/api/main.py`](apps/api/main.py) |
| Retrieval evaluation | 2 | done | [`retrieval_eval.py`](evals/retrieval_eval.py), [`ADR-001`](docs/adrs/ADR-001-retrieval-arm.md), [`retrieval-2026-09-11-remapped.md`](evals/results/retrieval-2026-09-11-remapped.md) |
| LLM evaluation | 2 | done | [`llm_eval.py`](evals/llm_eval.py), [`ADR-003`](docs/adrs/ADR-003-answer-prompt.md), [`llm_eval.md`](evals/results/llm_eval.md) |
| Interface (UI + API) | 2 | done | [`apps/ui/app.py`](apps/ui/app.py), [`apps/api/main.py`](apps/api/main.py), [`openapi.snapshot.json`](specs/openapi.snapshot.json) |
| Ingestion (dlt) | 2 | done | [`sqlite_pipeline.py`](apps/ingest/sqlite_pipeline.py), [`pipeline.py`](apps/ingest/pipeline.py) |
| Monitoring (≥5 charts + feedback) | 2 | done | [`observatory.py`](apps/store/observatory.py), [`apps/api/main.py`](apps/api/main.py) (`POST /v1/feedback`) |
| Containerization | 2 | done | [`docker/docker-compose.yml`](docker/docker-compose.yml) |
| Reproducibility | 2 | done | [`justfile`](justfile) (`just drill`), [`.env.example`](.env.example), [`uv.lock`](uv.lock) |
| Hybrid + rerank + rewrite (measured) | 3 | done | [`hybrid.py`](packages/homelib-rag/src/homelib_rag/hybrid.py), [`rerank.py`](packages/homelib-rag/src/homelib_rag/rerank.py), [`rewrite.py`](packages/homelib-rag/src/homelib_rag/rewrite.py), [`ADR-001`](docs/adrs/ADR-001-retrieval-arm.md) |
| Cloud (bonus) | 2 | done — https://homelib.streamlit.app/ | [`streamlit_app.py`](streamlit_app.py) |
| Extras (bonus) | — | partial — Mentor, eval gate, Coffee Table, rotunda | [`mentor.py`](packages/homelib-rag/src/homelib_rag/mentor.py), [`gate.py`](evals/gate.py), [`coffee_table.py`](apps/store/coffee_table.py), [`rotunda.py`](apps/ui/rotunda.py) |

## License

Code: [PolyForm Noncommercial 1.0.0](LICENSE). Docs/screenshots:
[CC BY-NC-SA 4.0](LICENSE-docs.md). Reasoning:
[ADR-007](docs/adrs/ADR-007-licence-provisional.md). Demo corpus is public-domain
text only; Open Library is metadata, not full-text ingest.
