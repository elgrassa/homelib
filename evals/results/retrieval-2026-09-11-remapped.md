# Retrieval arm eval — 2026-09-11, re-labelled ground truth

Same four arms as [`retrieval.md`](retrieval.md) (2026-09-06, hybrid_rerank
0.638 / 0.572), scored against `evals/ground_truth.jsonl` after
`evals/remap_ground_truth.py` re-pointed 161 of 235 questions whose `chunk_id`
survived the September seed rebuild but whose text did not (one question had
no plausible target and was dropped; every move is in
`evals/ground_truth_remap.jsonl`). Rows now carry `passage_sha256` /
`corpus_revision=seed-627-9119`. Before re-labelling, the same tip scored
hybrid_rerank 0.409 / 0.358 — the retriever had not changed, the labels had.
Gate floors in `evals/eval-baseline.json` were not lowered.

Read the `lexical` line with care: the remap picks the chunk sharing the most
question terms, which is close to what BM25 ranks by, so lexical gains most
from the re-labelling. Production stays on `hybrid_rerank`
([ADR-001](../../docs/adrs/ADR-001-retrieval-arm.md)): it finds the right
*book* for 0.897 of questions against lexical's 0.833, and `hybrid` reaches the
same chunk hit rate in a quarter of the latency. This is the current number to
compare future runs against; the 2026-09-06 file stays as the pre-drift record.

Generated: 2026-09-11T14:44:08+00:00
Ground truth: `evals/ground_truth.jsonl` — 234 row(s) loaded, 234 scored, 0 skipped because the labelled `chunk_id` is not in the current index (corpus drift; excluded rather than counted as a miss).
Coverage: k=5, question budget = 234 (`--questions`), query rewrite = off (`--rewrite`).
Arms compared: `lexical`, `vector`, `hybrid`, `hybrid_rerank`.

| arm | rewrite | n | hit-rate@5 | hit@k (book) | MRR@5 | degraded | mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `lexical` **(winner)** | off | 234 | 0.701 | 0.833 | 0.569 | 0 | 283 |
| `vector` | off | 234 | 0.474 | 0.915 | 0.364 | 0 | 170 |
| `hybrid` | off | 234 | 0.684 | 0.897 | 0.570 | 0 | 77 |
| `hybrid_rerank` | off | 234 | 0.684 | 0.897 | 0.567 | 0 | 464 |

**Winner: `lexical`** — highest hit-rate@5 (0.701), MRR@5 (0.569) breaking ties.


## Arm actually used

`hybrid_search` returns the mode it really ran and falls back to a single arm when a backend is down; `rerank` returns `None` when the cross-encoder cannot load. These are the arms that actually produced the rankings scored above — `error` means retrieval raised and nothing was returned.

| arm requested | arm actually used (queries) |
| --- | --- |
| `lexical` | `lexical`: 234 |
| `vector` | `vector`: 234 |
| `hybrid` | `hybrid`: 234 |
| `hybrid_rerank` | `hybrid_rerank`: 234 |

## Per-book breakdown

### `lexical`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.467 | 0.400 |
| `aurelius-meditations` | 15 | 0.467 | 0.302 |
| `barnum-art-of-money-getting` | 15 | 0.667 | 0.589 |
| `conwell-acres-of-diamonds` | 15 | 0.867 | 0.756 |
| `emerson-essays-second-series` | 14 | 0.286 | 0.286 |
| `ford-my-life-and-work` | 14 | 0.500 | 0.336 |
| `franklin-autobiography` | 15 | 0.667 | 0.502 |
| `keller-story-of-my-life` | 14 | 1.000 | 0.857 |
| `machiavelli-the-prince` | 15 | 0.800 | 0.633 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.933 | 0.867 |
| `mill-on-liberty` | 14 | 0.714 | 0.607 |
| `smiles-self-help` | 15 | 0.600 | 0.472 |
| `smith-wealth-of-nations` | 10 | 0.900 | 0.703 |
| `strunk-elements-of-style` | 10 | 0.800 | 0.503 |
| `suntzu-art-of-war` | 8 | 0.875 | 0.650 |
| `taylor-scientific-management` | 10 | 0.800 | 0.583 |
| `thoreau-walden` | 10 | 0.600 | 0.525 |
| `washington-up-from-slavery` | 10 | 0.900 | 0.770 |

### `vector`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.600 | 0.402 |
| `aurelius-meditations` | 15 | 0.200 | 0.063 |
| `barnum-art-of-money-getting` | 15 | 0.667 | 0.522 |
| `conwell-acres-of-diamonds` | 15 | 0.800 | 0.733 |
| `emerson-essays-second-series` | 14 | 0.286 | 0.286 |
| `ford-my-life-and-work` | 14 | 0.214 | 0.161 |
| `franklin-autobiography` | 15 | 0.267 | 0.200 |
| `keller-story-of-my-life` | 14 | 0.714 | 0.449 |
| `machiavelli-the-prince` | 15 | 0.467 | 0.350 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.800 | 0.639 |
| `mill-on-liberty` | 14 | 0.500 | 0.321 |
| `smiles-self-help` | 15 | 0.333 | 0.256 |
| `smith-wealth-of-nations` | 10 | 0.600 | 0.525 |
| `strunk-elements-of-style` | 10 | 0.400 | 0.275 |
| `suntzu-art-of-war` | 8 | 0.375 | 0.375 |
| `taylor-scientific-management` | 10 | 0.400 | 0.400 |
| `thoreau-walden` | 10 | 0.300 | 0.133 |
| `washington-up-from-slavery` | 10 | 0.500 | 0.425 |

### `hybrid`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.667 | 0.500 |
| `aurelius-meditations` | 15 | 0.400 | 0.356 |
| `barnum-art-of-money-getting` | 15 | 0.800 | 0.667 |
| `conwell-acres-of-diamonds` | 15 | 0.933 | 0.789 |
| `emerson-essays-second-series` | 14 | 0.286 | 0.286 |
| `ford-my-life-and-work` | 14 | 0.429 | 0.250 |
| `franklin-autobiography` | 15 | 0.600 | 0.461 |
| `keller-story-of-my-life` | 14 | 1.000 | 0.881 |
| `machiavelli-the-prince` | 15 | 0.733 | 0.656 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.933 | 0.850 |
| `mill-on-liberty` | 14 | 0.714 | 0.643 |
| `smiles-self-help` | 15 | 0.533 | 0.411 |
| `smith-wealth-of-nations` | 10 | 0.800 | 0.750 |
| `strunk-elements-of-style` | 10 | 0.600 | 0.358 |
| `suntzu-art-of-war` | 8 | 0.750 | 0.588 |
| `taylor-scientific-management` | 10 | 0.800 | 0.578 |
| `thoreau-walden` | 10 | 0.500 | 0.500 |
| `washington-up-from-slavery` | 10 | 0.900 | 0.775 |

### `hybrid_rerank`

| book | n | hit-rate@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| `allen-as-a-man-thinketh` | 15 | 0.667 | 0.600 |
| `aurelius-meditations` | 15 | 0.400 | 0.400 |
| `barnum-art-of-money-getting` | 15 | 0.800 | 0.713 |
| `conwell-acres-of-diamonds` | 15 | 0.933 | 0.856 |
| `emerson-essays-second-series` | 14 | 0.286 | 0.286 |
| `ford-my-life-and-work` | 14 | 0.429 | 0.310 |
| `franklin-autobiography` | 15 | 0.600 | 0.547 |
| `keller-story-of-my-life` | 14 | 1.000 | 0.929 |
| `machiavelli-the-prince` | 15 | 0.733 | 0.656 |
| `mackay-extraordinary-popular-delusions` | 15 | 0.933 | 0.789 |
| `mill-on-liberty` | 14 | 0.714 | 0.494 |
| `smiles-self-help` | 15 | 0.533 | 0.386 |
| `smith-wealth-of-nations` | 10 | 0.800 | 0.603 |
| `strunk-elements-of-style` | 10 | 0.600 | 0.283 |
| `suntzu-art-of-war` | 8 | 0.750 | 0.650 |
| `taylor-scientific-management` | 10 | 0.800 | 0.523 |
| `thoreau-walden` | 10 | 0.500 | 0.367 |
| `washington-up-from-slavery` | 10 | 0.900 | 0.733 |

