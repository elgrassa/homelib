# spec: evals-retrieval — `evals/ground_truth.py` + `evals/retrieval_eval.py`

**Implemented by:** WP-12 (lexical/vector/hybrid), WP-13 (+rerank, +rewrite).
**Consumed by:** `docs/adrs/ADR-001-retrieval-arm.md`, `apps/api` (production `arm` default).

## Purpose

Answer, on evidence, which retrieval arm ships as the production default. Ground
truth is LLM-generated then human-skimmed so the eval is cheap to regenerate but
not rubber-stamped; the metrics themselves are reimplemented from their published
definitions (never derived from the code under test) so a bug in `hybrid.py`
cannot also be the bug in its own eval.

## Public interface

```python
# evals/ground_truth.py
def sample_chunks(n: int, *, seed: int = 0) -> list[Chunk]: ...
    # stratified across books; deterministic given seed
def generate_questions(chunk: Chunk, *, n: int = 5) -> list[str]: ...
    # one LLM call per chunk; returns exactly n non-empty, deduplicated questions
def build_ground_truth(chunks: list[Chunk]) -> list[GroundTruthRow]: ...
def write_ground_truth(rows: list[GroundTruthRow], path: Path) -> None: ...
    # evals/ground_truth.jsonl — committed only after a human skim (see below)

# evals/retrieval_eval.py
class GroundTruthRow(BaseModel):
    question: str
    chunk_id: str
    book_id: str

def hit_rate_at_k(results: list[list[str]], relevant: list[str], k: int) -> float: ...
def mrr_at_k(results: list[list[str]], relevant: list[str], k: int) -> float: ...
def run_arm(rows: list[GroundTruthRow], *, arm: str, k: int = 5, rewrite: bool) -> ArmMetrics: ...
def run_all_arms(rows: list[GroundTruthRow]) -> list[ArmMetrics]: ...
def write_report(results: list[ArmMetrics], path: Path) -> None: ...
    # evals/results/retrieval.md
```

## Data contracts (field-level)

```
GroundTruthRow  question: str
                chunk_id: str            # the chunk the question was generated FROM
                book_id: str

ArmMetrics      arm: str                 # "lexical"|"vector"|"hybrid"|"hybrid_rerank"
                rewrite: bool
                hit_rate_at_5: float      # [0, 1], averaged over ALL rows
                mrr_at_5: float           # [0, 1], averaged over ALL rows
                per_book: dict[str, {hit_rate_at_5: float, mrr_at_5: float, n: int}]
                n: int                    # total ground-truth rows scored
```

**Metric definitions (reimplemented from these definitions, not from `index.py`):**

- **hit-rate@k** — for one query, 1 if the labeled-relevant id appears anywhere
  in the top-k results, else 0. Overall hit-rate@k is the mean of that indicator
  across all queries.
- **MRR@k** — for one query, `1 / rank` where `rank` (1-based) is the position
  of the labeled-relevant id within the top-k results, else 0 if absent from the
  top-k. Overall MRR@k is the mean across all queries.

**Ground truth generation:** sample ~30-50 chunks stratified across the 15-25
book shelf, generate ~5 questions per chunk via one LLM call each ->
150-250 `question -> chunk_id` pairs. `evals/ground_truth.jsonl` is committed
**only after a human skim** removes unanswerable or duplicate questions — the
skim is a manual step, not automated, and its completion is recorded in
`docs/evidence.md`.

**Arms (four, per §4.4):** `lexical`, `vector`, `hybrid` (RRF), `hybrid_rerank`
(RRF + cross-encoder), each run twice — `rewrite=true` and `rewrite=false` —
so `evals/results/retrieval.md` reports up to 8 rows plus the marked winner.

## Error/degradation behavior

- `generate_questions` returning fewer than `n` non-empty questions after one
  retry is a **warning row** in the ground-truth build log, not a silent
  under-count — `build_ground_truth` records how many questions each chunk
  actually contributed.
- A `GroundTruthRow` whose `chunk_id` no longer exists in the current index
  (corpus drift) is skipped and counted in the report's `n`, never scored as
  a miss it wasn't given a fair chance to hit.
- `run_arm` on a backend failure (e.g. rerank model unavailable) surfaces the
  same degradation the production path uses (specs/api.md) — the arm's
  metrics are computed on whatever ranking was actually returned, and the
  report row is annotated `degraded: true` rather than silently scoring the
  fallback as if it were the requested arm.
- `hit_rate_at_k`/`mrr_at_k` raise `ValueError` on empty `results` or `relevant`
  input — an eval run over zero data is a bug, not a score of 0.

## Named red tests (write before the code)

- `test_hit_rate_hand_computed` — fixed toy case: 3 queries, top-5 result lists
  where the relevant id is at rank 1, rank 4, and absent; hand-computed
  hit-rate@5 = `2/3`, asserted against `hit_rate_at_k`.
- `test_mrr_hand_computed` — same 3-query toy case; hand-computed MRR@5 =
  `(1/1 + 1/4 + 0) / 3`, asserted against `mrr_at_k`.
- `test_hit_rate_and_mrr_agree_when_relevant_always_rank_one` — synthetic
  arm where every query's relevant id is rank 1: both metrics equal `1.0`.
- `test_metrics_raise_on_empty_input`.
- `test_ground_truth_row_chunk_id_exists_in_fixture_index`.
- `test_per_book_breakdown_sums_to_overall_n` — `sum(per_book[b].n) == n`.

## Verify

```
just eval-retrieval
cat evals/results/retrieval.md          # table: arms x rewrite on/off x hit-rate@5/MRR@5, winner marked, per-book breakdown
uv run pytest evals/tests/test_metrics.py -v
cat docs/adrs/ADR-001-retrieval-arm.md  # winner named, evidence cited
```
