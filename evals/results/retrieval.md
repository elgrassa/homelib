# Retrieval arm eval

Generated: 2026-09-03T13:10:49+00:00
Ground truth: `evals/ground_truth.jsonl` — 235 row(s) loaded, 235 scored, 0 skipped because the labelled `chunk_id` is not in the current index (corpus drift; excluded rather than counted as a miss).
Coverage: k=5, question budget = all rows (`--questions`), query rewrite = off (`--rewrite`).
Arms compared: `lexical`, `vector`, `hybrid`, `hybrid_rerank`.

| arm | rewrite | n | hit-rate@5 | MRR@5 | degraded | mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `lexical` | off | 235 | 0.064 | 0.055 | 0 | 12 |
| `vector` | off | 235 | 0.630 | 0.473 | 0 | 45 |
| `hybrid` | off | 235 | 0.638 | 0.483 | 0 | 11 |
| `hybrid_rerank` **(winner)** | off | 235 | 0.638 | 0.572 | 0 | 68 |

**Winner: `hybrid_rerank`** — highest hit-rate@5 (0.638), MRR@5 (0.572) breaking ties.

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
| `barnum-art-of-money-getting` | 15 | 0.067 | 0.067 |
| `conwell-acres-of-diamonds` | 15 | 0.200 | 0.167 |
| `emerson-essays-second-series` | 15 | 0.000 | 0.000 |
| `ford-my-life-and-work` | 14 | 0.000 | 0.000 |
| `franklin-autobiography` | 15 | 0.067 | 0.067 |
| `keller-story-of-my-life` | 14 | 0.071 | 0.071 |
| `machiavelli-the-prince` | 15 | 0.067 | 0.067 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.200 | 0.167 |
| `mill-on-liberty` | 14 | 0.071 | 0.036 |
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
| `allen-as-a-man-thinketh` | 15 | 0.667 | 0.424 |
| `aurelius-meditations` | 15 | 0.200 | 0.067 |
| `barnum-art-of-money-getting` | 15 | 0.800 | 0.611 |
| `conwell-acres-of-diamonds` | 15 | 0.800 | 0.683 |
| `emerson-essays-second-series` | 15 | 0.267 | 0.267 |
| `ford-my-life-and-work` | 14 | 0.643 | 0.464 |
| `franklin-autobiography` | 15 | 0.333 | 0.300 |
| `keller-story-of-my-life` | 14 | 0.786 | 0.556 |
| `machiavelli-the-prince` | 15 | 0.667 | 0.483 |
| `mackay-extraordinary-popular-delusions` | 15 | 1.000 | 0.883 |
| `mill-on-liberty` | 14 | 0.786 | 0.643 |
| `smiles-self-help` | 15 | 0.600 | 0.394 |
| `smith-wealth-of-nations` | 10 | 0.700 | 0.650 |
| `strunk-elements-of-style` | 10 | 0.400 | 0.117 |
| `suntzu-art-of-war` | 8 | 0.625 | 0.448 |
| `taylor-scientific-management` | 10 | 0.700 | 0.583 |
| `thoreau-walden` | 10 | 0.700 | 0.387 |
| `washington-up-from-slavery` | 10 | 0.700 | 0.525 |

### `hybrid`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.667 | 0.424 |
| `aurelius-meditations` | 15 | 0.200 | 0.067 |
| `barnum-art-of-money-getting` | 15 | 0.800 | 0.611 |
| `conwell-acres-of-diamonds` | 15 | 0.867 | 0.706 |
| `emerson-essays-second-series` | 15 | 0.267 | 0.267 |
| `ford-my-life-and-work` | 14 | 0.643 | 0.464 |
| `franklin-autobiography` | 15 | 0.333 | 0.333 |
| `keller-story-of-my-life` | 14 | 0.786 | 0.592 |
| `machiavelli-the-prince` | 15 | 0.733 | 0.550 |
| `mackay-extraordinary-popular-delusions` | 15 | 1.000 | 0.867 |
| `mill-on-liberty` | 14 | 0.786 | 0.607 |
| `smiles-self-help` | 15 | 0.600 | 0.394 |
| `smith-wealth-of-nations` | 10 | 0.700 | 0.650 |
| `strunk-elements-of-style` | 10 | 0.400 | 0.125 |
| `suntzu-art-of-war` | 8 | 0.625 | 0.448 |
| `taylor-scientific-management` | 10 | 0.700 | 0.583 |
| `thoreau-walden` | 10 | 0.700 | 0.453 |
| `washington-up-from-slavery` | 10 | 0.700 | 0.525 |

### `hybrid_rerank`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.667 | 0.589 |
| `aurelius-meditations` | 15 | 0.200 | 0.200 |
| `barnum-art-of-money-getting` | 15 | 0.800 | 0.660 |
| `conwell-acres-of-diamonds` | 15 | 0.867 | 0.756 |
| `emerson-essays-second-series` | 15 | 0.267 | 0.267 |
| `ford-my-life-and-work` | 14 | 0.643 | 0.643 |
| `franklin-autobiography` | 15 | 0.333 | 0.333 |
| `keller-story-of-my-life` | 14 | 0.786 | 0.702 |
| `machiavelli-the-prince` | 15 | 0.733 | 0.733 |
| `mackay-extraordinary-popular-delusions` | 15 | 1.000 | 0.947 |
| `mill-on-liberty` | 14 | 0.786 | 0.607 |
| `smiles-self-help` | 15 | 0.600 | 0.517 |
| `smith-wealth-of-nations` | 10 | 0.700 | 0.650 |
| `strunk-elements-of-style` | 10 | 0.400 | 0.270 |
| `suntzu-art-of-war` | 8 | 0.625 | 0.625 |
| `taylor-scientific-management` | 10 | 0.700 | 0.650 |
| `thoreau-walden` | 10 | 0.700 | 0.483 |
| `washington-up-from-slavery` | 10 | 0.700 | 0.650 |

