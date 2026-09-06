# LLM prompt-variant eval

Generated: 2026-09-06T22:35:29+00:00
Judge prompt: version 1, hash `cdf1891b3c1d266425c9b9f02ece648b9e9a1e17f01c2fa540790d5d26f31745`
Answer arm: `hybrid_rerank`, k=5

| variant | n | faithfulness | relevance | citation_quality | suggested_score | ungrounded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `cited_first` | 10 | 3.00 | 3.70 | 3.00 | 2.80 | 0/10 |
| `concise` | 10 | 2.60 | 3.30 | 2.60 | 2.50 | 0/10 |
| `production` | 10 | 2.60 | 2.90 | 2.30 | 2.40 | 1/10 |
| `stepwise` | 10 | 3.40 | 3.80 | 2.70 | 3.00 | 0/10 |

`ungrounded` counts answers that succeeded while citing nothing — the legitimate "the passages do not answer this" reply. It is here because such an answer still counts as a success, so a variant can climb this table by declining more often, and a judge scoring everything near 2/5 has little room to punish reticence. **If the leading arm is also the one declining most, this ranking is measuring hedging, not quality.**

**Winner: `stepwise`** — highest mean suggested_score (3.00), the judge's own overall rating rather than an average of the sub-scores.

## Answer similarity (cosine)

Second LLM-eval method, judge-free: embeds each generated answer and its reference (the ground-truth chunk's own text) with `all-MiniLM-L6-v2` and scores cosine similarity between the two — cheap, deterministic, and independent of the judge table above, which it complements rather than replaces. Re-run: `uv run python evals/answer_similarity.py --answers <path>`.

| variant | n | mean similarity | median similarity |
| --- | ---: | ---: | ---: |
| `cited_first` | 10 | 0.441 | 0.457 |
| `concise` | 10 | 0.480 | 0.504 |
| `production` | 10 | 0.515 | 0.564 |
| `stepwise` | 10 | 0.534 | 0.518 |
