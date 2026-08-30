# Retrieval arm eval

Generated: 2026-08-30T15:56:31+00:00
Ground truth: `evals/ground_truth.jsonl` — 235 row(s) loaded, 235 scored, 0 skipped because the labelled `chunk_id` is not in the current index (corpus drift; excluded rather than counted as a miss).
Coverage: k=5, question budget = all rows (`--questions`), query rewrite = off (`--rewrite`).
Arms compared: `lexical`, `vector`, `hybrid`, `hybrid_rerank`.

| arm | rewrite | n | hit-rate@5 | MRR@5 | degraded | mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `lexical` | off | 235 | 0.072 | 0.066 | 0 | 173 |
| `vector` | off | 235 | 0.106 | 0.092 | 0 | 233 |
| `hybrid` | off | 235 | 0.174 | 0.152 | 0 | 252 |
| `hybrid_rerank` **(winner)** | off | 235 | 0.174 | 0.167 | 0 | 338 |

**Winner: `hybrid_rerank`** — highest hit-rate@5 (0.174), MRR@5 (0.167) breaking ties.

## Arm actually used

`hybrid_search` returns the mode it really ran and falls back to a single arm when a backend is down; `rerank` returns `None` when the cross-encoder cannot load. These are the arms that actually produced the rankings scored above — `error` means retrieval raised and nothing was returned.

| arm requested | arm actually used (queries) |
| --- | --- |
| `lexical` | `lexical`: 235 |
| `vector` | `vector`: 235 |
| `hybrid` | `hybrid`: 235 |
| `hybrid_rerank` | `hybrid_rerank`: 235 |

## Per-book breakdown

### `lexical`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.000 | 0.000 |
| `aurelius-meditations` | 15 | 0.000 | 0.000 |
| `barnum-art-of-money-getting` | 15 | 0.000 | 0.000 |
| `conwell-acres-of-diamonds` | 15 | 0.333 | 0.300 |
| `emerson-essays-second-series` | 15 | 0.000 | 0.000 |
| `ford-my-life-and-work` | 14 | 0.000 | 0.000 |
| `franklin-autobiography` | 15 | 0.067 | 0.067 |
| `keller-story-of-my-life` | 14 | 0.071 | 0.071 |
| `machiavelli-the-prince` | 15 | 0.067 | 0.067 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.200 | 0.167 |
| `mill-on-liberty` | 14 | 0.143 | 0.143 |
| `smiles-self-help` | 15 | 0.067 | 0.067 |
| `smith-wealth-of-nations` | 10 | 0.000 | 0.000 |
| `strunk-elements-of-style` | 10 | 0.100 | 0.050 |
| `suntzu-art-of-war` | 8 | 0.000 | 0.000 |
| `taylor-scientific-management` | 10 | 0.000 | 0.000 |
| `thoreau-walden` | 10 | 0.100 | 0.100 |
| `washington-up-from-slavery` | 10 | 0.100 | 0.100 |

### `vector`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.400 | 0.400 |
| `aurelius-meditations` | 15 | 0.067 | 0.067 |
| `barnum-art-of-money-getting` | 15 | 0.000 | 0.000 |
| `conwell-acres-of-diamonds` | 15 | 0.133 | 0.133 |
| `emerson-essays-second-series` | 15 | 0.067 | 0.067 |
| `ford-my-life-and-work` | 14 | 0.071 | 0.036 |
| `franklin-autobiography` | 15 | 0.000 | 0.000 |
| `keller-story-of-my-life` | 14 | 0.143 | 0.060 |
| `machiavelli-the-prince` | 15 | 0.067 | 0.067 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.067 | 0.067 |
| `mill-on-liberty` | 14 | 0.000 | 0.000 |
| `smiles-self-help` | 15 | 0.133 | 0.100 |
| `smith-wealth-of-nations` | 10 | 0.100 | 0.100 |
| `strunk-elements-of-style` | 10 | 0.000 | 0.000 |
| `suntzu-art-of-war` | 8 | 0.250 | 0.167 |
| `taylor-scientific-management` | 10 | 0.300 | 0.250 |
| `thoreau-walden` | 10 | 0.200 | 0.200 |
| `washington-up-from-slavery` | 10 | 0.000 | 0.000 |

### `hybrid`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.400 | 0.400 |
| `aurelius-meditations` | 15 | 0.067 | 0.067 |
| `barnum-art-of-money-getting` | 15 | 0.000 | 0.000 |
| `conwell-acres-of-diamonds` | 15 | 0.400 | 0.356 |
| `emerson-essays-second-series` | 15 | 0.067 | 0.067 |
| `ford-my-life-and-work` | 14 | 0.071 | 0.036 |
| `franklin-autobiography` | 15 | 0.067 | 0.067 |
| `keller-story-of-my-life` | 14 | 0.214 | 0.131 |
| `machiavelli-the-prince` | 15 | 0.133 | 0.133 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.267 | 0.222 |
| `mill-on-liberty` | 14 | 0.143 | 0.143 |
| `smiles-self-help` | 15 | 0.200 | 0.167 |
| `smith-wealth-of-nations` | 10 | 0.100 | 0.100 |
| `strunk-elements-of-style` | 10 | 0.100 | 0.033 |
| `suntzu-art-of-war` | 8 | 0.250 | 0.167 |
| `taylor-scientific-management` | 10 | 0.300 | 0.250 |
| `thoreau-walden` | 10 | 0.300 | 0.300 |
| `washington-up-from-slavery` | 10 | 0.100 | 0.100 |

### `hybrid_rerank`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.400 | 0.400 |
| `aurelius-meditations` | 15 | 0.067 | 0.067 |
| `barnum-art-of-money-getting` | 15 | 0.000 | 0.000 |
| `conwell-acres-of-diamonds` | 15 | 0.400 | 0.367 |
| `emerson-essays-second-series` | 15 | 0.067 | 0.067 |
| `ford-my-life-and-work` | 14 | 0.071 | 0.071 |
| `franklin-autobiography` | 15 | 0.067 | 0.067 |
| `keller-story-of-my-life` | 14 | 0.214 | 0.214 |
| `machiavelli-the-prince` | 15 | 0.133 | 0.133 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.267 | 0.233 |
| `mill-on-liberty` | 14 | 0.143 | 0.143 |
| `smiles-self-help` | 15 | 0.200 | 0.200 |
| `smith-wealth-of-nations` | 10 | 0.100 | 0.100 |
| `strunk-elements-of-style` | 10 | 0.100 | 0.033 |
| `suntzu-art-of-war` | 8 | 0.250 | 0.250 |
| `taylor-scientific-management` | 10 | 0.300 | 0.300 |
| `thoreau-walden` | 10 | 0.300 | 0.300 |
| `washington-up-from-slavery` | 10 | 0.100 | 0.100 |

