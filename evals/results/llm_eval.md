# LLM prompt-variant eval

Generated: 2026-08-30T21:22:03+00:00
Judge prompt: version 1, hash `cdf1891b3c1d266425c9b9f02ece648b9e9a1e17f01c2fa540790d5d26f31745`
Answer arm: `hybrid_rerank`, k=5

| variant | n | faithfulness | relevance | citation_quality | suggested_score | ungrounded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `cited_first` | 30 | 1.93 | 1.90 | 2.07 | 1.80 | 4/30 |
| `concise` | 30 | 2.03 | 2.40 | 2.07 | 1.80 | 5/30 |
| `production` | 30 | 2.00 | 2.47 | 1.87 | 1.73 | 5/30 |
| `stepwise` | 30 | 2.37 | 2.73 | 2.00 | 2.07 | 7/30 |

`ungrounded` counts answers that succeeded while citing nothing — the legitimate "the passages do not answer this" reply. It is here because such an answer still counts as a success, so a variant can climb this table by declining more often, and a judge scoring everything near 2/5 has little room to punish reticence. **If the leading arm is also the one declining most, this ranking is measuring hedging, not quality.**

**Winner: `stepwise`** — highest mean suggested_score (2.07), the judge's own overall rating rather than an average of the sub-scores.

⚠ **Treat that winner as unproven.** `stepwise` also declined to cite anything more often than any other arm (7/30), so its lead may be reticence rather than quality — an arm that answers less has less for a weak judge to mark down.
