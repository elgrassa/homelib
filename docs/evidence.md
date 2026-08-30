# Build evidence log

One row per completed work package. `verify` lists the commands the orchestrator
re-ran itself (subagent claims are never accepted as evidence).

| WP | branch / PR | verify commands run | result | date |
|---|---|---|---|---|
| WP-00 preflight | (local) | `which djvutxt` | **djvulibre GO** — /opt/homebrew/bin/djvutxt (3.5.30); WP-05 is in scope | 2026-08-30 |
| WP-00 preflight | (local) | `docker info` | Docker Desktop 29.7.2 daemon up (was down; started) | 2026-08-30 |
| WP-00 preflight | (local) | OpenAI-SDK function-calling probe vs Ollama `/v1` | **`qwen2.5:7b-instruct` GO** — emitted `search_catalog{"query":"building machine learning systems","subjects":[]}`. Chosen as the compose default (4.7 GB, reviewer-friendly). `gemma4:26b-a4b-it-qat` also GO (no `subjects`), kept as the local heavy override. | 2026-08-30 |
| WP-00 scaffold | feat/scaffold | `just ci` | ruff clean · ruff format clean (13 files) · mypy --strict clean (9 files) · pytest 1 passed, coverage 100% ≥ 90% floor | 2026-08-30 |
