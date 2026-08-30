# Build evidence log

One row per completed work package. `verify` lists the commands the orchestrator
re-ran itself (subagent claims are never accepted as evidence).

| WP | branch / PR | verify commands run | result | date |
|---|---|---|---|---|
| WP-00 preflight | (local) | `which djvutxt` | **djvulibre GO** — /opt/homebrew/bin/djvutxt (3.5.30); WP-05 is in scope | 2026-08-30 |
| WP-00 preflight | (local) | `docker info` | Docker Desktop 29.7.2 daemon up (was down; started) | 2026-08-30 |
| WP-00 preflight | (local) | OpenAI-SDK function-calling probe vs Ollama `/v1` | **`qwen2.5:7b-instruct` GO** — emitted `search_catalog{"query":"building machine learning systems","subjects":[]}`. Chosen as the compose default (4.7 GB, reviewer-friendly). `gemma4:26b-a4b-it-qat` also GO (no `subjects`), kept as the local heavy override. | 2026-08-30 |
| WP-00 scaffold | feat/scaffold | `just ci` | ruff clean · ruff format clean (13 files) · mypy --strict clean (9 files) · pytest 1 passed, coverage 100% ≥ 90% floor | 2026-08-30 |
| WP-01 specs | feat/scaffold | `ls specs/*.md \| wc -l`; section-structure grep over all 18 | 18 specs, each with the mandated sections. Orchestrator cross-read found ONE contradiction: `answer.md` and `monitoring.md` both consume a `query_log.degraded` flag that `indexing.md` (schema owner) never defined, and monitoring hedged its error-rate panel on "if degraded is logged". Reconciled by adding `degraded boolean NOT NULL DEFAULT false` to the DDL and making the panel unconditional. | 2026-08-30 |
| WP-02 core models | feat/scaffold | `just ci` re-run by orchestrator; read `models.py` + `test_extra_metadata_survives_roundtrip` | 13 tests pass; mypy --strict clean (10 files); ruff clean; coverage 93.94% ≥ 90%. `extra="allow"` on all 6 models, verified by reading the source, and the round-trip test genuinely serializes through JSON text rather than asserting on construction. | 2026-08-30 |
| WP-00 fix | feat/scaffold | `uv run ruff format --check .` | ruff 0.16 formats Python fences inside Markdown, so all 18 specs failed the format gate. Excluded `*.md` from ruff — specs carry illustrative signatures, not runnable code. | 2026-08-30 |
