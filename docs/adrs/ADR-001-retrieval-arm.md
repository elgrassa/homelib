# ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** Pavlo (owner)
- **Related:** `specs/hybrid.md`, `specs/rerank.md`, `specs/rewrite.md`,
  `evals/results/retrieval.md`, `docs/evidence.md`

## Context

Four retrieval arms are implemented: Postgres full-text search, pgvector
cosine similarity, RRF fusion of the two, and fusion followed by a
cross-encoder rerank. A fifth practice, LLM query rewriting, sits in front of
any of them. Something has to be the default, and "hybrid plus a reranker,
obviously" is a fashion, not a measurement.

The corpus is 18 public-domain books — 729 blocks, 9,168 chunks. The ground
truth is 235 generated question/chunk pairs, each labelling exactly one chunk
as correct.

## Decision

**Ship `hybrid_rerank`. Ship query rewrite OFF.**

## Evidence

All 235 questions, k=5, zero degraded queries across all 940 arm-runs — so
every row measures the arm it names rather than a silent fallback:

| arm | hit-rate@5 | MRR@5 | mean latency |
|---|---:|---:|---:|
| `lexical` | 0.072 | 0.066 | 77 ms |
| `vector` | 0.106 | 0.092 | 137 ms |
| `hybrid` | 0.174 | 0.152 | 164 ms |
| **`hybrid_rerank`** | **0.174** | **0.167** | 276 ms |

Two things in that table are worth more than the winner:

**Fusion is where the gain is.** Hybrid beats the better single arm by 64%
(0.174 vs 0.106). Lexical and vector retrieval fail on different questions —
lexical misses paraphrase, vector misses proper nouns and numbers — so
combining them recovers more than either ranking alone contains.

**The reranker does exactly what a reranker does, and no more.** It lifts
MRR (0.152 → 0.167) while leaving hit-rate identical. That is the signature
of a component that reorders a fixed candidate set: it cannot retrieve a
chunk that fusion did not already surface. Anyone expecting it to raise
hit-rate has misunderstood what it is for, and the measurement says so
plainly.

### Query rewrite: measured, and rejected

Compared on the **same 80 questions** — an unmatched sample would have proved
nothing:

| | hit-rate@5 | MRR@5 | mean latency |
|---|---:|---:|---:|
| rewrite off | 0.150 | 0.144 | 649 ms |
| rewrite on | 0.150 | **0.138** | 688 ms |

No gain in hit-rate, a small loss in MRR, and an extra LLM call per query.

The rewriter is not silently no-opping — checked, because "no difference"
and "did nothing" look identical in a results table. It rewrote 6 of 6
sampled questions, turning prose into keyword form:

> `"What analogy does the lawyer use to indicate…"` → `"analogy lawyer professions openings"`

That is a competent rewrite. It just does not help here, and the likely
reason is that hybrid retrieval already covers what it offers: stripping a
question to keywords is close to what the lexical arm's `tsquery` does
anyway, so the rewrite mostly duplicates work fusion has already done —
while discarding phrasing the vector arm could have used.

Rewrite stays implemented, tested, and one flag away. It is off because the
evidence says off.

## What the absolute numbers do and do not mean

A hit-rate of 0.174 looks alarming, so it should be read correctly. A
diagnostic over 60 sampled questions, asking not "was the labelled chunk
retrieved" but "was anything near it retrieved":

| | rate |
|---|---:|
| exact labelled chunk in top-5 | 0.133 |
| correct **book** in top-5 | 0.650 |
| correct **section** in top-5 | 0.400 |

Retrieval finds the right book about two-thirds of the time across 18 books,
against 5.6% for chance. The signal is real. What the metric scores is the
single chunk a generator happened to label, so a neighbouring chunk carrying
equally relevant prose counts as a total miss — and at 9,168 chunks over 18
books, near-misses are the common case.

Both statements are true, and neither should be dropped:

- **The metric understates usefulness.** It is single-positive and
  chunk-exact. It is still the right metric to *compare arms with*, because
  every arm is penalised identically — which is all a bake-off needs.
- **There is genuine headroom.** 0.650 book-level accuracy is not a good
  score in absolute terms either. Chunking granularity and ground-truth
  question quality are both plausible causes; roughly a third of the
  generated questions are of the "what does the author describe" shape, which
  carries little retrieval signal even for a human.

## Consequences

**Positive**
- The default is chosen on evidence, and the evidence is reproducible:
  `just eval-retrieval` re-runs the whole comparison in ~155 seconds with no
  LLM in the measurement path.
- The negative result on rewrite is recorded, so it does not get re-proposed
  as an obvious improvement.

**Negative**
- `hybrid_rerank` costs 276 ms against 77 ms for lexical — 3.6× for a gain
  concentrated in MRR. Acceptable here because retrieval is a small fraction
  of a request dominated by ~13 s of local generation. On a faster model this
  trade would be worth revisiting.
- The reranker loads a cross-encoder, which is why it degrades to `None`
  rather than failing when the model cannot load.

**Baseline**
The eval regression gate's floors are set from this measurement, with a note
on each recording that they are low and why. Setting them at an aspirational
0.70 would have left the gate permanently red, which trains people to ignore
it; setting them silently at 0.174 would quietly ratify a weak result as the
standard. Recording the number *and* the reason is the only version that
stays honest.

## v2 SQLite re-measurement (2026-09-03)

**Status:** Accepted (store migration). Does **not** retract the v1 Postgres
table above — that remains the historical evidence for ADR-001 on `main`.

Re-ran `just eval-retrieval` against a WP03-seeded SQLite corpus
(`HOMELIB_SQLITE_PATH=data/homelib.sqlite`, counts 18/729/9168/9168, FTS5 +
float32 BLOB matrix, k=5, rewrite off, 0 degraded, 0 corpus-drift skips):

| arm | hit-rate@5 | MRR@5 | mean latency |
|---|---:|---:|---:|
| `lexical` | 0.064 | 0.055 | 12 ms |
| `vector` | 0.630 | 0.473 | 45 ms |
| `hybrid` | 0.638 | 0.483 | 11 ms |
| **`hybrid_rerank`** | **0.638** | **0.572** | 68 ms |

**Decision unchanged: ship `hybrid_rerank`; rewrite stays off.**

Two bugs found and fixed before this table was trustworthy (same PR):

1. `_load_matrix` JSON-decoded embeddings; ingest stores **float32 BLOBs** →
   vector arm 100% degraded. Fixed with dual BLOB/JSON decode + regression
   `test_load_matrix_accepts_float32_blob_embeddings`.
2. `_fts_query` AND-required every token including `What`/`is`, unlike
   Postgres `plainto_tsquery('english', …)` → near-zero lexical. Fixed with
   stopword drop + `test_fts_query_drops_english_stopwords_like_plainto_tsquery`.

Vector@5 jumped vs Postgres (0.106 → 0.630) under the same ground truth and
embedder — contiguous float32 matrix / no ivfflat approximation is the likely
cause; do not treat the absolute lift as a chunker win without a matched
re-run on both stores. Gate floors in `evals/eval-baseline.json` updated to
the SQLite measurement (notes record the supersession).

**RRF k sweep (2026-09-06):** `hybrid_search` gained a keyword-only `rrf_k`
parameter (default 60, unchanged) so the fusion constant could be measured
rather than assumed; swept over `{1, 10, 60, 100, 200}` on the same SQLite
corpus (`just eval-rrf-k`, hybrid arm, k=5, `evals/results/retrieval.md` §"RRF
k sweep"), hit-rate@5/MRR@5/hit@5(book) came back **identical to three
decimal places at every k** (0.638 / 0.483 / 0.906) — zero spread, so **k
stays 60**, the RRF paper's default, since nothing in this corpus rewards
moving it. The mechanism is visible in the arms themselves: the constant only
changes the fused order when a chunk appears in *both* lists, and with the
lexical arm at 0.064 hit-rate the two top-10 lists typically share one chunk
or none (spot-checked on the seed: 1 of 10, identical fused order at
`rrf_k=1` and `rrf_k=200`), so fusion degenerates to "vector order, lexical
tail" whatever `k` is. A corpus with a competitive lexical arm would need the
sweep re-run.

## Verification

```bash
export HOMELIB_SQLITE_PATH=$PWD/data/homelib.sqlite   # after WP03 seed
just eval-retrieval                      # all four arms, 235 questions
cat evals/results/retrieval.md

# the rewrite comparison, matched sample
uv run python evals/retrieval_eval.py --questions 80 --arm hybrid_rerank
uv run python evals/retrieval_eval.py --questions 80 --arm hybrid_rerank --rewrite
```
