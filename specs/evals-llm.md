# spec: evals-llm — `evals/llm_eval.py` + `evals/judge.py`

**Implemented by:** WP-15.
**Consumed by:** `apps/api` `/v1/ask` (winning prompt variant wired into production),
`specs/eval-gate.md` (judge scores feed the regression gate).

## Purpose

Pick which answer-synthesis prompt ships, on evidence rather than taste, and
guard against the judge silently grading its own homework. At least 3 prompt
variants are scored by an LLM judge whose prompt carries sub-scores, its own
independent overall score, and an explicit instruction that it is not the model
being evaluated — so an over-confident judge cannot inflate the very prompt it
would have produced itself.

## Public interface

```python
# evals/llm_eval.py
PROMPT_VARIANTS: dict[str, str]        # >= 3 named variants, e.g. "concise", "cited_first", "stepwise"

def run_variant(variant: str, questions: list[GroundTruthRow]) -> list[AnsweredCase]: ...
def score_variants(cases_by_variant: dict[str, list[AnsweredCase]]) -> list[VariantScore]: ...
def write_report(scores: list[VariantScore], path: Path) -> None: ...
    # evals/results/llm_eval.md, winner marked

# evals/judge.py
def judge(question: str, answer: str, citations: list[Citation]) -> JudgeScore: ...
def prompt_hash(version: str, template: str, schema_shape: str) -> str: ...
    # sha256("|".join([version, template, schema_shape]))
```

## Data contracts (field-level)

```
AnsweredCase   question: str
               variant: str
               answer: str
               citations: list[Citation]        # per specs/api.md
               latency_ms: int

JudgeScore     faithfulness: int        # 1-5, does the answer only claim what citations support
               relevance: int           # 1-5, does the answer address the question
               citation_quality: int    # 1-5, are citations specific and resolvable
               suggested_score: int     # 1-5, judge's OWN independent overall rating
               verdict: str             # 1-2 sentence justification
               judge_model: str         # provider/model that produced this score

VariantScore   variant: str
               n: int
               mean_faithfulness: float
               mean_relevance: float
               mean_citation_quality: float
               mean_suggested_score: float
```

**Judge prompt requirements (binding):**

1. Carries all three sub-scores (`faithfulness`, `relevance`, `citation_quality`)
   as separate 1-5 ratings, not one blended number.
2. Carries `suggested_score` as an **independent** overall judgment — computed
   by the judge from its own reading, not a mechanical average of the
   sub-scores (the harness may compute that average separately for comparison,
   but never overwrites `suggested_score` with it).
3. **Bias control (explicit, non-negotiable):** the judge system prompt states
   verbatim that the judge is a different model invocation from, and is **not**,
   the model whose prompt variant produced the answer — grading its own output
   under a different name is the exact failure this line prevents.

## Error/degradation behavior

- A judge call that fails to parse into `JudgeScore` gets **one** bounded
  repair retry (re-prompt with the parse error); a second failure raises
  `JudgeParseError` and that case is excluded from `VariantScore.n` — never
  silently scored as a default/neutral value.
- `run_variant` on an LLM failure for a single question retries once, then
  records the case with `answer=""` and lets the judge score it on its own
  merits (an empty answer should score low on `faithfulness`/`relevance`, not
  be dropped and hide the failure).
- `write_report` refuses to mark a winner if any variant has `n == 0` —
  a report with a missing arm is a build failure, not a 2-way comparison
  presented as complete.

## Named red tests (write before the code)

- `test_judge_prompt_states_it_is_not_the_scoring_model` — the rendered judge
  system prompt (for every variant) contains an explicit first-person
  disclaimer that it is not the model being scored; behavioral assertion on
  rendered text, not a docstring check.
- `test_judge_score_sub_scores_and_suggested_score_are_independent_fields` —
  a scripted fake judge response with sub-scores `(5,5,5)` and
  `suggested_score=2` round-trips unchanged; the harness never recomputes
  `suggested_score` from the sub-scores.
- `test_prompt_hash_changes_when_template_changes` — hashing two templates
  that differ by one character yields different hashes.
- `test_prompt_hash_pinned` — `prompt_hash(CURRENT_VERSION, CURRENT_TEMPLATE,
  CURRENT_SCHEMA_SHAPE)` equals a hardcoded literal committed in the test;
  this is the drift detector — it fails the moment a shipped prompt changes
  without a deliberate hash update in the same diff.
- `test_judge_parse_failure_retries_once_then_excludes_case`.
- `test_at_least_three_variants_registered` — `len(PROMPT_VARIANTS) >= 3`.

## Verify

```
just eval-llm
cat evals/results/llm_eval.md            # >= 3 variants scored, winner marked
uv run pytest evals/tests/test_judge.py evals/tests/test_prompt_hash.py -v
```
