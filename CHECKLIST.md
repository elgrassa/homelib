# homelib — submission checklist

LLM Zoomcamp 2026 rubric tracker. **`done`** means verified in
[`docs/evidence.md`](docs/evidence.md), not “code exists.”

Live demo: https://homelib.streamlit.app/  
How to run: [`README.md`](README.md) · evals: [`EVAL.md`](EVAL.md) · trade-offs: [`TRADEOFFS.md`](TRADEOFFS.md)

Last updated: 2026-09-12.

---

## A. Rubric (26 + bonus)

| # | Criterion | Max | Status | Where to look |
|---|---|---|---|---|
| 1 | Problem description | 2 | ✅ done | [`README.md`](README.md) |
| 2 | Retrieval flow (KB + LLM) | 2 | ✅ done | Ask path; ADR-004 dual store; citations open a block |
| 3 | Retrieval evaluation | 2 | ✅ done | 4 arms; [`ADR-001`](docs/adrs/ADR-001-retrieval-arm.md); `evals/results/` |
| 4 | LLM evaluation | 2 | ✅ done | 4 arms; null result kept incumbent — [`ADR-003`](docs/adrs/ADR-003-answer-prompt.md) |
| 5 | Interface (UI + API) | 2 | ✅ done | Streamlit Crossroads (7 doors) + FastAPI; `specs/openapi.snapshot.json` |
| 6 | Ingestion (dlt) | 2 | ✅ done | `just seed` / `just seed-sqlite` → 18 books |
| 7 | Monitoring (≥5 charts + feedback) | 2 | ✅ done | Observatory door + `POST /v1/feedback` |
| 8 | Containerization | 2 | ✅ done | `docker/docker-compose.yml` (digest-pinned, healthchecked) |
| 9 | Reproducibility | 2 | ✅ done | pins + snapshot; `just drill` PASSED (`ee0f318`) |
| 10 | Hybrid + rerank + rewrite | 3 | ✅ done | all three measured; rewrite rejected on evidence (ADR-001) |
| 11 | Cloud (bonus) | 2 | ✅ done | https://homelib.streamlit.app/ |
| 12 | Extras (bonus) | 3 | 🟡 partial | eval gate, Mentor, Coffee Table, rotunda; not audiobook/Obsidian |
| — | Peer reviews (×3) | +9 | ⬜ todo | after submit |

Floor without bonus: **21/26**.

---

## B. Reviewer path (local)

```bash
just up && just seed && just seed-sqlite
# /health → 18 books; Ask → cited answer → 👍 → Observatory; Coffee Table add survives rerun
just drill   # cold-clone gate (quiet host; CPU Ollama can time out under load)
```

SQLite-only (matches Cloud): see README “Try”.

---

## C. Honest limits (current)

- Cold Ollama on a loaded host can hit the ask timeout; Cloud uses Groq.
- Zero-citation `degraded=False` is a valid “passages don’t answer” reply — bake-offs count ungrounded successes separately.
- Eval regression gate exists (`just eval-gate`); wiring it as a blocking CI job is still open.
- Open Library `search.json` has no `description` field; Roadmap writes its own rationale.

Detail and dated runs: [`docs/evidence.md`](docs/evidence.md).

---

## D. Out of scope for this submission

Audiobook chapter export, Obsidian BookShelf, multi-language FTS, incremental single-book re-ingest.
