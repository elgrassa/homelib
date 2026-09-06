# Chunking experiment

Generated: 2026-09-06T22:36:27+00:00
Corpus: 6/18 book(s) (`--books`) re-chunked per config from `data/corpus_snapshot.jsonl.gz`. See the module docstring for why embedding the WHOLE 18-book corpus at three granularities is the actual bottleneck (not question count) and, when a full 18-book run exceeds the 20-minute budget, why a book subset — not a question cap — is the lever that brings it back under.
Ground truth: `evals/ground_truth.jsonl`, question budget = 235 (`--questions`); every config below scored the same 73 row(s) (162 row(s) dropped: labelled book not in the corpus subset used).

Ground-truth `chunk_id`s do not survive re-chunking (a different `target_chars`/`overlap` produces different chunk boundaries and freshly-hashed ids), so hit-rate/MRR below are BOOK-level (`evals/metrics.py:hit_rate_book`, and `mrr_at_k` fed book ids) — the fair comparison across configs.

| target_chars/overlap | n chunks | lexical hit@5 (book) | lexical MRR@5 (book) | vector hit@5 (book) | vector MRR@5 (book) | mean tokens (top-5 chunks) | mean tokens (whole section) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 600/100 | 8618 | 0.027 | 0.027 | 0.973 | 0.924 | 422 | 3073 |
| 1200/200 | 4121 | 0.027 | 0.027 | 0.986 | 0.912 | 893 | 3073 |
| 2000/400 | 2586 | 0.027 | 0.027 | 0.973 | 0.924 | 1560 | 3073 |

**Conclusion:** the best config on book-level hit@5 is `1200/200` (0.986 vector, vs `2000/400`'s 0.973 — a 0.014 spread across the three configs); retrieving the top-5 chunks costs ~958 mean tokens against a ~3073-token whole-section baseline, so chunked retrieval is the cheaper context regardless of which config wins.
