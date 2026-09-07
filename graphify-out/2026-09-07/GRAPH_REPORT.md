# Graph Report - hostexecutor  (2026-09-07)

## Corpus Check
- 220 files · ~262,750 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3660 nodes · 7711 edges · 331 communities (184 shown, 147 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 1046 edges (avg confidence: 0.63)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5d66a63b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- v2_routes.py
- test_judge.py
- test_api.py
- ApiClient
- BaseModel
- ChatMessage
- test_answer.py
- test_view_model.py
- test_fetch_corpus.py
- models.py
- hybrid_search
- test_index.py
- LLMResponse
- connect
- test_pipeline.py
- test_gate.py
- test_rewrite.py
- test_format_pdf.py
- decision-log.md
- test_metrics.py
- connectors.py
- coffee_table.py
- InProcessClient
- test_ground_truth.py
- sqlite_pipeline.py
- test_sqlite_ingest.py
- sqlite.py
- test_format_djvu.py
- HttpClient
- pipeline.py
- chunk_book
- test_fetch_catalog.py
- view_model.py
- app.py
- test_retrieval_eval.py
- sqlite_index.py
- chunk.py
- test_rotunda.py
- test_models.py
- v2 target — product.md §8 (markdown this WP; not in the snapshot yet)
- bump_index_revision
- write_report
- answer.py
- retrieval_eval.py
- parse_txt
- parse_epub
- ground_truth.py
- test_rerank.py
- test_v2_routes.py
- Handoff — Zoomcamp checklist + plan v2.1 verification
- test_inprocess_bridge.py
- Extension points
- sqlite_deps.py
- 3. Proposed SQLite tables
- parse_djvu
- Data model and schemas
- Decision log
- Local development
- HomeLib v2 — reviewer handoff
- Debugging and troubleshooting
- Retrieval pipeline
- roadmap.py
- HomeLib — improved product and build plan v2
- SyncASGITransport
- 12.3 Work packages
- homelib — submission checklist
- Stakeholder picky review + wiki/mermaid handoff — 2026-09-05
- HomeLib v2.1 — final merged execution plan (capstone rebuild + product)
- Architecture overview
- prompt_hash
- QueryOutcome
- test_index_sqlite_dispatch.py
- 5. Signature product experience
- test_cloud_files.py
- ADR-002 — Catalog source: Open Library, and three rejections
- ADR-003 — Answer prompt: keep the incumbent, on a null result
- test_mentor.py
- homelib
- test_coffee_table.py
- test_app_doors.py
- Submission runbook — LLM Zoomcamp 2026
- test_openapi_snapshot.py
- cold_clone_drill.sh
- test_repo_hygiene.py
- ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off
- Decision
- Repo structure
- write_ground_truth
- spec: answer — `homelib_rag.answer`
- spec: audio — capabilities and one lawful preview
- spec: chunking — `homelib_core.chunk`
- spec: connectors — lawful catalog federation (“Forbidden Stacks”)
- spec: core-models — `homelib_core.models`
- spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`
- spec: ui — `apps/ui` (Streamlit Crossroads)
- User flows
- _is_substantial
- Per-book breakdown
- parse_file
- sqlite_only_smoke.sh
- spec: agent-tools — `homelib_rag.agent`
- spec: coffee-table — persistent playlist (product §5.6)
- spec: eval-gate — `evals/gate.py`
- spec: evals-llm — `evals/llm_eval.py` + `evals/judge.py`
- spec: evals-retrieval — `evals/ground_truth.py` + `evals/retrieval_eval.py`
- spec: formats — `homelib_core.formats` + `homelib_core.normalize`
- spec: ingestion — `apps/ingest/pipeline.py` (dlt)
- spec: monitoring — `query_log` + Grafana + `scripts/demo_traffic.py`
- 7. Technical architecture
- spec: progress — reading and listening positions
- spec: projection — projector reading mode (product §5.9)
- spec: provider — `LLMProvider` seam
- spec: rerank — `homelib_rag.rerank`
- spec: rewrite — `homelib_rag.rewrite`
- spec: roadmap — `homelib_rag.roadmap`
- spec: rotunda — Library Crossroads doors (product §5.2)
- spec: scene-search — within-book exact/keyword/semantic/smart/ask
- CLAUDE.md — HomeLib
- rerank.py
- spec: client — `HomelibClient` in-process vs HTTP seam
- spec: editions — `APP_MODE` and the capability matrix
- spec: hybrid — `homelib_rag.hybrid`
- spec: indexing — `homelib_rag.index`
- spec: observatory — in-app monitoring (replaces Grafana)
- spec: principals — demo sessions and local-user identity
- 4. Editions and deployment model
- Commercial split and product ladder (owner 2026-09-01; evening pivot)
- spec: rights — fail-closed gate before index and audio
- test_packaging.py
- RuntimeError
- demo_ask.py
- demo_roadmap.py
- 14. Acceptance journeys
- 15. Post-capstone roadmap
- ADR-005 — Observatory replaces Grafana
- ADR-007 — Licence (provisional)
- ADR-009 — Audio deferred
- Design — how the magic-library look reaches the product
- _compose
- _gate_steps
- ADR-004 — SQLite replaces Postgres
- ADR-006 — Editions and hosting
- ADR-008 — Rights gate (unknown fails closed)
- Crossroads and doors
- HomeLib v2 — Developer Wiki
- 12. Delivery plan
- 6. Data and rights model
- 9. Evaluation and monitoring
- _all_job_commands
- pre-push
- homelib
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- Build evidence log
- README.md
- __init__.py
- llm_eval.md
- _default_retrieve
- __init__.py
- __init__.py
- _reset_rerank_state
- __init__.py
- test_ci_declares_no_permissions_block
- test_pre_push_hook_stays_fast_by_excluding_the_slow_markers
- test_the_full_suite_does_not_run_on_the_quick_lane
- test_compose_pins_the_ollama_context_window
- test_ui_dockerfile_pins_pythonpath_so_apps_imports_resolve
- test_streamlit_theme_pins_parchment_gold_from_mockups
- test_ui_dockerfile_copies_streamlit_theme_into_image
- test_compose_api_wires_homelib_sqlite_path_for_v2_doors
- test_ci_pytest_forces_workspace_basetemp
- test_run_agent_is_not_on_the_demo_request_path
- test_gitleaks_allowlists_never_exempt_whole_files
- test_drill_asserts_seed_counts_via_health
- test_drill_verifies_monitoring_via_observatory_not_grafana_panel_count
- test_specs_ui_door_list_matches_crossroads_doors
- test_no_dotenv_file_is_tracked
- test_ci_graph_guard_job_exists
- test_ci_graph_refresh_pushes_to_current_protected_branch
- test_ci_graph_refresh_commits_the_bootstrap_graph
- test_graphifyignore_excludes_generated_and_data_paths
- test_just_ci_includes_the_secret_scan
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- test_specs_ui_door_list_matches_crossroads_doors
- test_no_dotenv_file_is_tracked
- test_ci_graph_guard_job_exists
- Path
- demo_traffic.py
- ui-entrypoint.sh
- chunking.md
- Any
- AskResponse
- Block
- BookSummary
- Connection
- RoadmapResponse
- SentenceTransformer
- Self
- Any
- Block
- BookSummary
- Connection
- Path
- Any
- Block
- Exception
- MonkeyPatch
- MonkeyPatch
- Path
- Path
- Any
- Client
- Path
- Client
- Path
- Any
- DltResource
- LoadInfo
- Path
- Pipeline
- SentenceTransformer
- Any
- Connection
- DltResource
- LoadInfo
- Path
- Pipeline
- Path
- MonkeyPatch
- Path
- MonkeyPatch
- Path
- MonkeyPatch
- Path
- CaptureFixture
- Connection
- MonkeyPatch
- Path
- Any
- Path
- Response
- Any
- Connection
- datetime
- Row
- Connection
- Connection
- Any
- Connection
- datetime
- Path
- Path
- Any
- MonkeyPatch
- Path
- MonkeyPatch
- Path
- Path
- Self
- OpenAI
- Path
- Citation
- CaptureFixture
- Path
- CaptureFixture
- MonkeyPatch
- Path
- Block
- Path
- Path
- Path
- Path
- Self
- Path
- Block
- Provenance
- MonkeyPatch
- Path
- MonkeyPatch
- Path
- MonkeyPatch
- Path
- Path
- Block
- Provenance
- Path
- Any
- Connection
- SentenceTransformer
- OpenAI
- CatalogSearch
- Level
- Connection
- Any
- Connection
- Path
- Row
- Any
- Exception
- MonkeyPatch
- Any
- MonkeyPatch
- Connection
- MonkeyPatch
- Path
- MonkeyPatch
- MonkeyPatch
- Any
- Exception
- Connection
- MonkeyPatch
- Path
- Connection
- MonkeyPatch
- Path
- Namespace
- Namespace
- MonkeyPatch
- Path

## God Nodes (most connected - your core abstractions)
1. `connect()` - 93 edges
2. `migrate()` - 85 edges
3. `ApiClient` - 57 edges
4. `GroundTruthRow` - 54 edges
5. `ChatMessage` - 50 edges
6. `LLMResponse` - 45 edges
7. `Deps` - 40 edges
8. `LLMUnreachableError` - 40 edges
9. `_make_deps()` - 38 edges
10. `Universal in-memory book representation — see specs/core-models.md.  One data mo` - 38 edges

## Surprising Connections (you probably didn't know these)
- `QueryLogRow` --uses--> `LLMUnreachableError`  [INFERRED]
  apps/api/main.py → packages/homelib-rag/src/homelib_rag/answer.py
- `QueryLogRow` --uses--> `OpenAICompatibleClient`  [INFERRED]
  apps/api/main.py → packages/homelib-rag/src/homelib_rag/answer.py
- `QueryLogRow` --uses--> `BookDoc`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py
- `QueryLogRow` --uses--> `CatalogEntry`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py
- `QueryLogRow` --uses--> `Chunk`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py

## Import Cycles
- None detected.

## Communities (331 total, 147 thin omitted)

### Community 0 - "v2_routes.py"
Cohesion: 0.17
Nodes (6): SQLite dispatch on homelib_rag.index when HOMELIB_SQLITE_PATH is set., The reviewer-visible symptom: with only SQLite reachable, a grounded     answer, `agent.search_catalog` is bound in three places (API deps, the roadmap     wrapp, _ScriptedClient, test_agent_search_catalog_uses_sqlite_when_path_set(), test_answer_end_to_end_not_degraded_on_sqlite_only_host()

### Community 1 - "test_judge.py"
Cohesion: 0.06
Nodes (77): answer(), _book_metadata(), default_llm_client(), _dsn(), OpenAIClient, `(base_url, api_key, model)` from the environment, in this order:      1. `LLM_A, Default `OpenAICompatibleClient`, backed by the `openai` SDK against     an Open, `book_id -> (title, authors)` for every id in `book_ids`.      Test seam: monkey (+69 more)

### Community 2 - "test_api.py"
Cohesion: 0.11
Nodes (34): append_history(), Baseline, compare_to_baseline(), _current_git_sha(), _describe(), load_baseline(), MetricSpec, Eval regression gate — see specs/eval-gate.md.  Turns "the eval numbers got wors (+26 more)

### Community 3 - "ApiClient"
Cohesion: 0.04
Nodes (73): _build_default_deps(), _compute_cost_usd(), _connect(), _default_counts(), _default_db_reachable(), _default_ingest(), _default_list_books(), _default_llm_reachable() (+65 more)

### Community 4 - "BaseModel"
Cohesion: 0.15
Nodes (35): Deps, get_health(), post_feedback(), post_ingest(), post_roadmap(), RoadmapResponse, QueryLogRow, Everything an endpoint needs, injected via `Depends(get_deps)`.      Every field (+27 more)

### Community 5 - "ChatMessage"
Cohesion: 0.06
Nodes (53): _block_from_pg_row(), build_roadmap(), _connect(), _dsn(), get_block(), get_book_block(), _parse_arguments(), Any (+45 more)

### Community 6 - "test_answer.py"
Cohesion: 0.14
Nodes (56): connect(), current_index_revision(), logical_checksum(), migrate(), Path, reset_demo(), row_counts(), seed() (+48 more)

### Community 7 - "test_view_model.py"
Cohesion: 0.04
Nodes (68): TokenUsage, _imported_modules(), _make_ask_response(), _make_book(), _make_citation(), _make_step(), AskResponse, BookSummary (+60 more)

### Community 8 - "test_fetch_corpus.py"
Cohesion: 0.07
Nodes (33): ApiClient, Block, _extract_detail(), Any, Client, Response, Best-effort extraction of the ``{"detail": str}`` error envelope., Thin synchronous client over the homelib public API. (+25 more)

### Community 9 - "models.py"
Cohesion: 0.07
Nodes (56): build_read_article_html(), Clean article HTML for Safari Listen to Page (not Streamlit chrome)., Top-level HTML document Safari Reader / Listen to Page can detect., ReadPage, _api_base(), _fetch_block(), _fetch_book_title(), main() (+48 more)

### Community 10 - "hybrid_search"
Cohesion: 0.06
Nodes (54): build_book_spread_html(), official_book_by_id(), Two-page PDF spread for Official Pottermore preview (display-only).  Served from, Full HTML: open book + text layer + Listen/Reading panel., Official Pottermore two-page book viewer + allowlisted PDF proxy., A render rejection inside showLeaf must not latch busy=true forever —     the fi, test_book_spread_busy_flag_has_finally(), test_book_spread_html_is_two_page_pdfjs_stage() (+46 more)

### Community 11 - "test_index.py"
Cohesion: 0.12
Nodes (36): LLMUsage, _build_prompt(), build_roadmap(), _candidate_line(), _parse_and_validate(), Personalized reading roadmap generation — see specs/roadmap.md.  Turns a user's, Parse+validate one LLM roadmap response. Raises `RoadmapParseError`.      Trunca, Build a `RoadmapResponse` grounded only in retrieved catalog candidates.      `L (+28 more)

### Community 12 - "LLMResponse"
Cohesion: 0.15
Nodes (33): AgentResult, ToolCallRecord, ChatMessage, CitationValidationError, LLMUnreachableError, OpenAICompatibleClient, Raised by an `OpenAICompatibleClient` on any connection/timeout/     transport f, One turn in a chat-completion request. See specs/agent-tools.md. (+25 more)

### Community 13 - "connect"
Cohesion: 0.07
Nodes (31): _default_rewriter(), Production query rewrite. Imported lazily — see `_default_retrieve`., _call_llm(), _client(), _model_name(), LLM query rewriter — see specs/rewrite.md.  Asks an LLM to turn a user's natural, Internal typed shape the LLM is asked to produce.      Not exposed publicly — `r, Call the configured LLM and return its raw response content.      Raises on any (+23 more)

### Community 14 - "test_pipeline.py"
Cohesion: 0.19
Nodes (38): AddPlaylistItemRequest, AudioCapabilities, delete_playlist_item(), get_audio_capabilities(), get_observatory(), get_playlist_current(), get_resources(), OkResponse (+30 more)

### Community 15 - "test_gate.py"
Cohesion: 0.07
Nodes (57): fetch_one(), FetchOutcome, load_manifest(), main(), ManifestEntry, Client, Path, Shelf fetcher — see specs/corpus.md.  Downloads the public-domain books listed i (+49 more)

### Community 16 - "test_rewrite.py"
Cohesion: 0.12
Nodes (21): _is_substantial(), Skip chunks too short, or too table-of-contents-like, to ask about., _fake_chunk(), fixture_chunks(), _load_committed_rows(), _make_book(), Tests for evals/ground_truth.py — see specs/evals-retrieval.md.  No test in this, A tiny synthetic book with enough sentence-delimited text for a few     substant (+13 more)

### Community 17 - "test_format_pdf.py"
Cohesion: 0.10
Nodes (34): PdfReader, _extract_authors(), _extract_title(), _is_likely_scanned(), _ocr_extract(), parse_pdf(), PDF format handler — see specs/formats.md.  Two extraction paths, chosen per doc, Run PyMuPDF's OCR text extraction over every page of `path`.      Raises `Runtim (+26 more)

### Community 18 - "decision-log.md"
Cohesion: 0.08
Nodes (52): AnswerSimilarityScore, build_reference_lookup(), _cosine(), _default_embed(), _get_embedder(), load_answers(), _load_ground_truth_rows(), main() (+44 more)

### Community 19 - "test_metrics.py"
Cohesion: 0.11
Nodes (40): ChunkId, _first_relevant_rank(), hit_rate_at_k(), hit_rate_book(), mrr_at_k(), Retrieval-quality metrics — see specs/evals-retrieval.md.  Reimplemented from fi, Mean reciprocal rank, over queries in `relevant`, within the top `k` of `results, Book-level hit-rate@k: a hit if any of the top-`k` results' book ids     matches (+32 more)

### Community 20 - "connectors.py"
Cohesion: 0.06
Nodes (50): HomelibClient, FixtureRequest, MockTransport, Protocol, client(), demo_client(), _inprocess(), WP08 HomelibClient InProcess/Http conformance — specs/client.md named reds. (+42 more)

### Community 21 - "coffee_table.py"
Cohesion: 0.19
Nodes (27): _current_playlist_id(), _now_iso(), _require_write_principal(), LookupError, StrEnum, accept_proposed(), add_item(), get_playlist() (+19 more)

### Community 22 - "InProcessClient"
Cohesion: 0.11
Nodes (29): parse_djvu(), Extract a `BookDoc` from a DJVU file via `djvutxt`.      Raises `RuntimeError` (, _attach_page_text(), _build_real_djvu_fixture(), _fake_run(), _FakeWhich, Red-first tests for `homelib_core.formats.djvu` — see specs/formats.md.  Written, `shutil.which` monkeypatched to `None` -> a specific, actionable `RuntimeError`. (+21 more)

### Community 23 - "test_ground_truth.py"
Cohesion: 0.15
Nodes (21): LogCaptureFixture, build_ground_truth(), generate_questions(), load_corpus_chunks(), Recompute every chunk in the committed corpus snapshot.      Deterministic given, Stratified, seeded sample of up to `n` chunks spread across all books.      Chun, One LLM call generating up to `n` specific, retrieval-shaped questions.      Ret, Generate ground-truth rows for `chunks`, one LLM call per chunk.      A chunk th (+13 more)

### Community 24 - "sqlite_pipeline.py"
Cohesion: 0.09
Nodes (45): _default_retrieve(), Production retrieval for the fixed `_ARM`: hybrid search plus rerank.      Impor, Judge every case and reduce to one `VariantScore` per variant.      A case whose, score_variants(), _answered_case(), _citation(), _hit(), _judge_body() (+37 more)

### Community 25 - "test_sqlite_ingest.py"
Cohesion: 0.15
Nodes (28): TempPathFactory, run_sqlite_pipeline(), staging_db_path(), _book(), _corpus_counts(), _create_minimal_staging(), _fake_embeddings(), _fresh_db() (+20 more)

### Community 26 - "sqlite.py"
Cohesion: 0.09
Nodes (31): _book(), clean_corpus_tables(), _drop_staging_schemas(), live_database_url(), Tests for apps/ingest/pipeline.py — see specs/ingestion.md named red tests.  Uni, This process's throwaway database — never the application's., Drop dlt's staging dataset (and the `_staging` merge dataset dlt makes     along, Empty the canonical tables and drop dlt's staging schemas. (+23 more)

### Community 27 - "test_format_djvu.py"
Cohesion: 0.09
Nodes (38): _hit(), _build_context_prompt(), _build_intake_prompt(), build_path(), detect_high_stakes_notice(), mentor_intake(), _mentor_tools(), Any (+30 more)

### Community 28 - "HttpClient"
Cohesion: 0.12
Nodes (38): books_default_rights_status(), compute_index_revision(), create_demo_session(), _current_reset_generation(), DemoSession, DemoSessionExpired, _enforce_active_demo_session(), _ensure_local_user() (+30 more)

### Community 29 - "pipeline.py"
Cohesion: 0.13
Nodes (35): _fuse(), _hybrid(), hybrid_search(), Reciprocal Rank Fusion over the lexical and vector search arms — see specs/hybri, Reciprocal-Rank-Fuse two arms' hits, dedup by `chunk_id`, top `k`.      Each arm, Search `q`, returning `(hits, mode_used)`.      `mode="lexical"` or `mode="vecto, _hit(), Exception (+27 more)

### Community 30 - "chunk_book"
Cohesion: 0.12
Nodes (29): DrawFn, test_sampling_skips_short_chunks(), chunk_book(), Chunk `doc` into retrieval-sized, citation-traceable `Chunk`s.      Chunks never, _build_doc(), _lorem_sentences(), _make_block(), _make_provenance() (+21 more)

### Community 31 - "test_fetch_catalog.py"
Cohesion: 0.15
Nodes (20): Cursor, _connect(), _dsn(), _embed_query(), _first_page(), _load_embedder(), Lexical (Postgres FTS) and vector (pgvector) search arms — see specs/indexing.md, Render an embedding as pgvector's text input format: `[0.1,0.2,...]`.      Retur (+12 more)

### Community 32 - "view_model.py"
Cohesion: 0.14
Nodes (14): 1. Project intent, 2. Architecture & schema (v2 — on `main` since the 2026-09-06 collapse), 3. How to run locally, 4. Plan 2.1 / Zoomcamp checklist matrix, 5. Wiki map, 6. What to verify in review, 7. Known gaps / improvements (priority), 8. Current git state (+6 more)

### Community 33 - "app.py"
Cohesion: 0.08
Nodes (7): _insert_block(), _insert_book(), _insert_chunk(), WP04 scene-search red tests — see specs/scene-search.md.  Cross-encoder rerank a, scene_db(), test_metadata_only_resource_raises_not_searchable(), test_unknown_resource_raises_not_found()

### Community 34 - "test_retrieval_eval.py"
Cohesion: 0.15
Nodes (31): load_questions(), Ground-truth rows, spread round-robin across books, capped at `budget`.      `bu, Partition `rows` into (scoreable, drifted) against the live index.      A row wh, Score one arm over `rows`.      `rewrite=True` routes every question through `ho, run_arm(), split_on_index(), _fixed_retriever(), Tests for evals/retrieval_eval.py — the retrieval-arm bake-off.  Every test here (+23 more)

### Community 35 - "sqlite_index.py"
Cohesion: 0.15
Nodes (24): float32, book_metadata(), _connect(), _decode_embedding(), _embed_query(), _first_page(), _fts_query(), _json_list() (+16 more)

### Community 36 - "chunk.py"
Cohesion: 0.11
Nodes (22): _atomic_unit_spans(), _chapter_key(), _make_chunk_id(), _pack_indices(), _pack_sentences(), _points_to_spans(), Block-aware, sentence-boundary chunking — see specs/chunking.md.  Turns a `BookD, End offsets partitioning `text` into sentences (last point == len(text)). (+14 more)

### Community 37 - "test_rotunda.py"
Cohesion: 0.10
Nodes (27): build_rotunda_html(), door_from_query(), _json_for_script(), The Crossroads rotunda — the rotating room of doors (specs/rotunda.md).  Pure mo, JSON that is safe inside an inline `<script>`.      Every `<` becomes the JSON e, Resolve the door an Enter link asked for.      `?door=X` arrives when the rotund, Return the rotunda fragment that `app.py` renders with `st.html`.      `active`, Rotunda: pure-string behaviour of the rotating room (specs/rotunda.md).  No scre (+19 more)

### Community 39 - "v2 target — product.md §8 (markdown this WP; not in the snapshot yet)"
Cohesion: 0.09
Nodes (13): _connect_never_called(), Red tests for `homelib_rag.index` — see specs/indexing.md.  Unit tests (the defa, Undo whatever a test left in the lazy embedder singleton.      The unit tests ab, A constant name lets two concurrent runs delete each other's database.      Guar, Point `index.py`'s `_connect()` at the throwaway test database for one test., _restore_embedder_singleton(), _seeded_db(), test_search_lexical_empty_query_raises() (+5 more)

### Community 40 - "bump_index_revision"
Cohesion: 0.11
Nodes (28): _judge_metrics(), load_questions(), _machine_snapshot(), main(), _mean(), _parse_args(), Namespace, Path (+20 more)

### Community 41 - "write_report"
Cohesion: 0.14
Nodes (29): ArmMetrics, _coverage_lines(), _degradation_section(), _no_winner_lines(), _per_book_section(), One arm's score over the ground-truth set.      `hit_rate_at_5` / `mrr_at_5` kee, The winning arm, or `None` when the comparison is not sound.      Refuses in thr, The header stating exactly what was and was not covered.      Every arm is score (+21 more)

### Community 42 - "answer.py"
Cohesion: 0.14
Nodes (16): bump_index_revision(), Rebuild the FTS5 mirror from canonical `chunks` rows (WP04)., Recompute and persist `index_revision` after ingest or FTS rebuild., rebuild_chunks_fts(), _reset_caches_for_tests(), sqlite_dispatch_db(), WP04 SQLite index tests — FTS5 + cached NumPy matrix., Ingest stores embeddings as float32 BLOBs; JSON-only decode fully degraded vecto (+8 more)

### Community 43 - "retrieval_eval.py"
Cohesion: 0.19
Nodes (21): _book_id_in_clause(), _default_db_path(), _default_manifest_path(), _embedding_json_to_blob(), main(), manifest_rights_from_path(), _purge_non_indexable_corpus(), dlt ingestion into SQLite — WP03; see specs/ingestion.md and ADR-004. (+13 more)

### Community 44 - "parse_txt"
Cohesion: 0.12
Nodes (17): _answer_one(), AnsweredCase, One question answered under one prompt variant., An `OpenAICompatibleClient` that substitutes the system prompt.      `answer()`, Answer one question, retrying once, then recording the failure honestly.      `a, Answer every question in `questions` under `variant`'s system prompt.      Alway, run_variant(), _VariantClient (+9 more)

### Community 45 - "parse_epub"
Cohesion: 0.18
Nodes (19): Element, _check_not_zip_bomb(), _element_text(), _localname(), parse_epub(), EPUB format handler — see specs/formats.md.  Block granularity: each `h1`-`h6`,, Extract a `BookDoc` from an EPUB file., _build_epub_bytes() (+11 more)

### Community 46 - "ground_truth.py"
Cohesion: 0.12
Nodes (19): Request, build_inprocess_client(), inflate_seed_if_missing(), _inside_data_dir(), Wire InProcessClient for APP_MODE=demo (outside apps/ui AST boundary).  Streamli, Sync façade over ``httpx.ASGITransport`` for a blocking ``httpx.Client``.      `, One loop thread per app object per process: Streamlit builds a client     on eve, Build an InProcessClient backed by the FastAPI app over ASGI. (+11 more)

### Community 47 - "test_rerank.py"
Cohesion: 0.12
Nodes (22): _call_llm(), _clean_questions(), _client(), _echoes_opening(), _is_self_referential(), main(), _model_name(), _normalize_words() (+14 more)

### Community 48 - "test_v2_routes.py"
Cohesion: 0.17
Nodes (17): _load_json_line(), Deserialize from `to_jsonl` output.          Raises `ValueError` naming the offe, _make_block(), _make_book_doc(), _make_provenance(), Red-first tests for `homelib_core.models` — see specs/core-models.md.  These tes, A field nobody anticipated must survive a full serialize/deserialize cycle., test_block_offsets_index_into_canonical_text() (+9 more)

### Community 49 - "Handoff — Zoomcamp checklist + plan v2.1 verification"
Cohesion: 0.07
Nodes (28): Contract-drift guard, `DELETE /v1/playlists/current/items/{item_id}`, Endpoints — live v1 (OpenAPI snapshot), Error and degradation behavior, `GET /health`, `GET /v1/areas` / `POST /v1/areas`, `GET /v1/audio/capabilities`, `GET /v1/blocks/{id}` (+20 more)

### Community 50 - "test_inprocess_bridge.py"
Cohesion: 0.11
Nodes (17): _base_deps(), _missing_block(), _missing_book_block(), Block, Behavioural tests for `apps/api` — see specs/api.md.  No live Postgres, no live, Placeholder home for the drift-guard assertion — the real, spec-named     test l, test_books_block_by_ordinal_not_found(), test_books_block_by_ordinal_returns_page() (+9 more)

### Community 51 - "Extension points"
Cohesion: 0.16
Nodes (18): _markdown_heading(), parse_txt(), _plaintext_heading(), TXT/Markdown format handler — see specs/formats.md.  Heading inference: a Markdo, An all-caps / Title-Case line under 80 chars, followed by a blank line., Extract a `BookDoc` from a plain-text or Markdown file., _assert_offsets_dense_and_stable(), Red-first tests for `homelib_core.formats.txt` — see specs/formats.md.  Written (+10 more)

### Community 52 - "sqlite_deps.py"
Cohesion: 0.07
Nodes (48): AskResponse, BookSummary, Citation, HttpClient, HTTP client for the homelib public API.  This is the ONLY module under ``apps/ui, Selfhosted edition — FastAPI over HTTP with per-call timeouts., RoadmapStep, Server forgot the session (TTL sweep): the client remints on the 401,     the fr (+40 more)

### Community 53 - "3. Proposed SQLite tables"
Cohesion: 0.13
Nodes (25): blocks_resource(), books_resource(), catalog_resource(), chunk_embeddings_resource(), chunks_resource(), _embed_batch(), embed_texts(), _ensure_ivfflat_index() (+17 more)

### Community 54 - "parse_djvu"
Cohesion: 0.11
Nodes (27): _hit(), _patch_connect(), MonkeyPatch, The `rerank` span wraps the real cross-encoder call inside the     production re, A pre-seeded cache entry for the exact key this request would compute     is ign, The `query_log` row for a cache hit has `cache_hit=True` — captured     via the, test_ask_writes_query_log_row(), test_cache_hit_is_logged_and_flagged() (+19 more)

### Community 55 - "Data model and schemas"
Cohesion: 0.18
Nodes (10): A model swap does not fix it either (2026-08-31), ADR-003 — Answer prompt: keep the incumbent, on a null result, Baseline, Consequences, Context, Correction: these measurements are less stable than either of us claimed, Decision, The winner is flagged unproven, and that is the point (+2 more)

### Community 56 - "Decision log"
Cohesion: 0.11
Nodes (19): Degradation tests, Documentation improvements, Editions and entitlements, Eval before default changes, Extension points, Import boundaries, Improving the system, New API routes (v2 §8) (+11 more)

### Community 57 - "Local development"
Cohesion: 0.11
Nodes (23): _db(), Connection, Path, Behavioural tests for `apps.api.tracing` — C5 (specs/monitoring.md "Tracing")., A span tree exported through `SqliteSpanExporter` reads back via     `read_trace, A span whose parent_span_id names nothing in this batch (e.g. a     partially fl, test_build_span_tree_nests_by_parent_and_computes_duration(), test_build_span_tree_orders_children_by_start_ns() (+15 more)

### Community 58 - "HomeLib v2 — reviewer handoff"
Cohesion: 0.06
Nodes (53): CrossEncoder, _CountingFakeCrossEncoder, _CountingFakeEmbedder, _hit(), MonkeyPatch, C9 speed confirmation: the embedder and cross-encoder load once per process — se, Two `_embed_query` calls construct the sentence embedder once; two     `rerank`, test_models_load_once_per_process() (+45 more)

### Community 59 - "Debugging and troubleshooting"
Cohesion: 0.12
Nodes (27): _doc_to_entry(), fetch_catalog_entries(), _fetch_page(), main(), Any, Client, Path, Open Library catalog fetcher — see specs/corpus.md.  Pulls curated subject slice (+19 more)

### Community 60 - "Retrieval pipeline"
Cohesion: 0.11
Nodes (18): 1. Sources examined, 2. Entities mined from the HTML, 3. Proposed SQLite tables, 4. HTML → table map, 5. Mockup-only entities (not in the HTML), 6. Contradictions (CONFUSION — do not silently pick), 7. WP02 red-test hooks, 8. Out of scope this PR / paid-tier must not be created this week (+10 more)

### Community 61 - "roadmap.py"
Cohesion: 0.11
Nodes (9): API tests for observatory + Coffee Table routes (WP07/WP10)., Compose mounts a pipeline-seeded DB that never ran store.seed().      After HOME, WP10 live feedback path: POST /v1/feedback updates query_log (UI→API→DB)., WP10: demo_traffic.py --n 40 leaves Observatory with ≥5 non-empty chart ids., The server-side contract the client fix (H3) relies on: a minted     `X-Demo-Ses, test_demo_mode_same_header_shares_principal_and_missing_header_does_not(), test_demo_traffic_populates_observatory_charts(), test_feedback_ui_to_db_roundtrip() (+1 more)

### Community 62 - "HomeLib — improved product and build plan v2"
Cohesion: 0.15
Nodes (15): RuntimeError, _decode_djvu_string(), djvu_available(), _djvutxt_version(), _extract_page_texts(), _first_quoted_string(), _iter_top_level_forms(), DJVU format handler — see specs/formats.md.  Extracts the hidden text layer via (+7 more)

### Community 63 - "SyncASGITransport"
Cohesion: 0.08
Nodes (37): _connect(), _dsn(), _gate_metrics(), load_indexed_chunk_ids(), main(), _make_retrieve(), _parse_args(), Any (+29 more)

### Community 64 - "12.3 Work packages"
Cohesion: 0.17
Nodes (25): build_observatory(), ObservatoryChart, ObservatoryPoint, Connection, Observatory aggregates from query_log — specs/observatory.md (WP10)., _db(), _insert_query_log(), _insert_query_log_with_cache_hit() (+17 more)

### Community 65 - "homelib — submission checklist"
Cohesion: 0.15
Nodes (24): filter_rows_to_available_books(), Rows whose `book_id` is present in `docs`, and how many were dropped.      Scori, Write `evals/results/chunking.md` from scratch.      Unlike `evals/retrieval_eva, write_report(), _build_doc(), _corpus(), _provenance(), ndarray (+16 more)

### Community 66 - "Stakeholder picky review + wiki/mermaid handoff — 2026-09-05"
Cohesion: 0.13
Nodes (23): _in_memory_tracer_provider(), _llm_json(), Vector search "raises" (simulated at the retrieve seam): response is     200 wit, ADR-001 (docs/adrs/ADR-001-retrieval-arm.md) measured query rewriting     agains, Neither `LLM_PRICE_PER_1K_*` var set (the compose/Ollama default):     `query_lo, With both prices set, `cost_usd` is     `tokens_prompt/1000 * prompt_price + tok, A scripted fake `OpenAICompatibleClient`. No network., A `TracerProvider` wired to an `InMemorySpanExporter`, synchronously     (`Simpl (+15 more)

### Community 67 - "HomeLib v2.1 — final merged execution plan (capstone rebuild + product)"
Cohesion: 0.18
Nodes (22): cache_key(), lookup(), _normalize_question(), AskResponse, Connection, Demo-only answer cache — C4b (specs/monitoring.md "Demo answer cache").  Read-th, Whitespace-collapsed, case-folded — "Does it Jump?" and "does it     jump?  " mu, `None` on a miss. Raises on a genuinely broken store (bad JSON, no     `answer_c (+14 more)

### Community 68 - "Architecture overview"
Cohesion: 0.13
Nodes (15): API endpoint map, Catalog and rights, Core entities, Corpus (ported from v1), Data model and schemas, Entity relationship diagram, Identity, Index and embedding revision (+7 more)

### Community 69 - "prompt_hash"
Cohesion: 0.13
Nodes (15): Answer prompt and rewrite (supplementary), Chunk ID stability for eval ground truth, Decision log, HomelibClient: InProcess vs Http, Hybrid search: BM25/FTS5 + vector + RRF vs alternatives, Ingest: dlt ELT shape, staging → canonical, idempotency, Licence — owner decision, recorded not fixed, Observability: Observatory vs Grafana (+7 more)

### Community 70 - "QueryOutcome"
Cohesion: 0.18
Nodes (20): judge_recent_rows(), JudgedRow, Connection, Online judge on live traffic — core logic behind `scripts/judge_recent.py`.  C6, One row this run actually scored and wrote back., Judge up to `n` of the most recent unjudged, answer-logged rows.      `client` i, _unjudged_rows(), _db() (+12 more)

### Community 71 - "test_index_sqlite_dispatch.py"
Cohesion: 0.13
Nodes (22): build_vector_index(), ChunkConfigResult, Embedder, One `(target_chars, overlap)` config's book-level retrieval scores., An in-memory, brute-force cosine-similarity index over chunk texts., Re-chunk `docs` at `(target_chars, overlap)` and score both arms.      Every met, Score every `(target_chars, overlap)` pair in `configs` over the same `rows`., run_chunk_sweep() (+14 more)

### Community 72 - "5. Signature product experience"
Cohesion: 0.14
Nodes (14): Coverage floor (90%), Data / ingest, Debugging and troubleshooting, dlt / SQLite connection hygiene, Eval regression gate, Forgejo CI lanes, Getting help from logs, Infrastructure (+6 more)

### Community 73 - "test_cloud_files.py"
Cohesion: 0.14
Nodes (14): Arm 1: Lexical (FTS5 / BM25), Arm 2: Vector (semantic), Degradation matrix, `degraded` flags contract, Evaluation, `Hit` shape (shared contract), Pipeline overview, Related pages (+6 more)

### Community 74 - "ADR-002 — Catalog source: Open Library, and three rejections"
Cohesion: 0.14
Nodes (14): 0. Executive decision, 10. Security, privacy and reliability, 11. Capstone rubric plan, 13. Cut order, 16. Final definition of done, 17. Authoritative implementation references, 1. Product problem, 2.1 Primary users (+6 more)

### Community 75 - "ADR-003 — Answer prompt: keep the incumbent, on a null result"
Cohesion: 0.15
Nodes (12): 0. Review verdict on the consolidated plan (adopted, with these corrections), 1. Owner actions (Pavlo) — GitHub + Streamlit at the VERY END (owner decision 2026-09-01), 2. Safety track (unchanged, binding), 3. Executor operating rules (binding, restored from v1), 4. What v2 ports from verified v1 (do not rewrite the database-agnostic 60%), 5. Work packages = product doc §12.3 (WP00–WP11), with these verification teeth added, 6. Rubric target (product doc §11): 21 core + 2 cloud = 23 before discretionary extras + 9 peer reviews. Never trade a scored criterion for polish. Cut order and never-cut list: product doc §13, with the correction that the HTML prototype is first to cut., 7. Restored guards (apply exactly as v1) (+4 more)

### Community 76 - "test_mentor.py"
Cohesion: 0.15
Nodes (13): 12.3 Work packages, WP00 — Freeze, fallback and canary, WP01 — Contracts and acceptance tests, WP02 — SQLite and principals, WP03 — Ingestion and rights, WP04 — Retrieval and evaluation, WP05 — Lawful connectors, WP06 — Mentor and artifacts (+5 more)

### Community 78 - "test_coffee_table.py"
Cohesion: 0.17
Nodes (12): Architecture overview, Edition topology (who talks to what), Editions at a glance, High-level system diagram, Home topology (self-hosted), Ingestion, LLM ([`specs/provider.md`](../../specs/provider.md)), Related pages (+4 more)

### Community 79 - "test_app_doors.py"
Cohesion: 0.17
Nodes (12): 5.10 Book-to-audio and Memory Sphere, 5.11 Forbidden Stacks, 5.1 Information architecture, 5.2 Library Crossroads and rotating room, 5.3 Explore flow, 5.4 Wing and shelf screen, 5.5 Mentor Journal, 5.6 Coffee Table (+4 more)

### Community 80 - "Submission runbook — LLM Zoomcamp 2026"
Cohesion: 0.18
Nodes (10): 1. Kaggle "15K+ Books Across 100+ Categories" — banned in any form, 2. Google Books API directly — unusable, 3. UCSD Goodreads Book Graph — unusable, ADR-002 — Catalog source: Open Library, and three rejections, Consequences, Context, Decision, Notes on sourcing (+2 more)

### Community 81 - "test_openapi_snapshot.py"
Cohesion: 0.16
Nodes (19): _block_from_row(), open_store(), Any, Block, BookSummary, Connection, Path, SQLite-backed helpers for FastAPI when HOMELIB_SQLITE_PATH is set (P0 wire). (+11 more)

### Community 82 - "cold_clone_drill.sh"
Cohesion: 0.22
Nodes (19): _install_fake_baseline(), _no_db(), MonkeyPatch, Path, Taking the first N lines would sample one book; round-robin must not., _stub_run(), test_load_questions_returns_everything_when_the_budget_exceeds_the_file(), test_load_questions_spreads_across_books_and_honours_the_budget() (+11 more)

### Community 83 - "test_repo_hygiene.py"
Cohesion: 0.24
Nodes (8): API_PORT, fail(), GRAFANA_PORT, OLLAMA_PORT, POSTGRES_PORT, cold_clone_drill.sh script, step(), UI_PORT

### Community 84 - "ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off"
Cohesion: 0.20
Nodes (7): Streamlit Community Cloud edition: the files Cloud reads and the seed it needs., `streamlit_app.py` is a shim over `apps/ui/app.py`, not a second UI., Cloud resolves from uv.lock; GPU torch wheels would blow its disk/RSS., `.python-version` (uv, pyenv, Cloud reviewers) agrees with pyproject., test_cloud_entrypoint_runs_the_same_ui_main(), test_python_version_file_matches_requires_python(), test_uv_lock_pins_cpu_torch_index()

### Community 85 - "Decision"
Cohesion: 0.18
Nodes (8): Course-module map, How we run each piece, Build evidence log, Plan addendum — post-merge corrections (2026-09-01), Answer similarity (cosine), LLM prompt-variant eval, Documentation licence, What this licence does NOT cover

### Community 86 - "Repo structure"
Cohesion: 0.17
Nodes (16): build_lexical_index(), _fts_query(), lexical_search(), load_book_docs(), load_ground_truth_rows(), main(), _parse_args(), Connection (+8 more)

### Community 87 - "write_ground_truth"
Cohesion: 0.16
Nodes (12): _clear_overrides(), Any, Every test gets a fresh tracer provider, built lazily on next     `get_tracer()`, `HOMELIB_LOG_ANSWERS` unset (the default): a real /v1/ask call, with a     real, `HOMELIB_LOG_ANSWERS=1` plus a real SQLite store: the question and     answer AR, APP_MODE=demo: asking the SAME question twice calls the LLM once —     the secon, _reset_tracer(), test_answer_log_off_by_default() (+4 more)

### Community 88 - "spec: answer — `homelib_rag.answer`"
Cohesion: 0.22
Nodes (9): ADR-010 — Single repo until public; paid tier after, Consequences, Context, Decision, Obsidian (post-public-publish, contract-first — product §15), Post-public-publish / paid tier (same Forgejo repo later — not another git remote), Product ladder, Public app this week (+1 more)

### Community 89 - "spec: audio — capabilities and one lawful preview"
Cohesion: 0.14
Nodes (7): Exception, Any, Any, Any, LLMResponse, Any, The normalized result of one `OpenAICompatibleClient.chat` call.

### Community 90 - "spec: chunking — `homelib_core.chunk`"
Cohesion: 0.22
Nodes (9): Apps, Branch model, Docker and CI, Documentation map, Packages, Related pages, Repo structure, Specs vs code vs tests vs data (+1 more)

### Community 91 - "spec: connectors — lawful catalog federation (“Forbidden Stacks”)"
Cohesion: 0.12
Nodes (11): MonkeyPatch, Crossroads doors rendered through Streamlit's own test harness.  `streamlit.test, `?source=` must be consumed into session state once, not re-added on     every r, The Projection ordinal must be keyed per book, not global (BUG 2): a     stale g, The rotunda's Enter reloads the page on `?door=X`; the app must open X     and d, `?projection=1` must open projector mode exactly once. Regression for the     tr, _selfhosted_against_closed_port(), test_door_query_param_opens_that_door_and_is_consumed() (+3 more)

### Community 92 - "spec: core-models — `homelib_core.models`"
Cohesion: 0.22
Nodes (9): parse_file(), Format dispatcher — see specs/formats.md.  `parse_file` is the single entry poin, Derive a `book_id` slug from a file stem (e.g. `"Moby Dick!" -> "moby-dick"`)., Dispatch `path` to the right format handler by its suffix.      Dispatches on `p, _slugify(), The dispatcher doesn't swallow the encrypted-PDF refusal either., test_parse_file_dispatches_encrypted_pdf_and_raises(), test_parse_file_dispatches_txt_and_md() (+1 more)

### Community 93 - "spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`"
Cohesion: 0.12
Nodes (16): APP_MODE behaviour, Canonical commands, Common debug commands, Compose profiles, Demo smoke (Sep 2 gate per evidence addendum), Environment, First-time setup, iPad / AirPlay / Speak Screen (+8 more)

### Community 94 - "spec: ui — `apps/ui` (Streamlit Crossroads)"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: answer — `homelib_rag.answer`, Store dispatch (2026-09-05), Verify

### Community 95 - "User flows"
Cohesion: 0.14
Nodes (14): _compose(), Guards on the gates themselves.  A config file that looks like a guarantee but i, The pre-push gate must not grow into the full suite.      Quality gates live on, Peer-facing shell: parchment/ink/gold tokens from magic-library mockup.      Wit, `.env.example` ships `APP_MODE=demo` for the Community Cloud path. The     api s, Hygiene (string/structure match, not behavioural). The api service reads     `/d, Purchased ebooks never leave this machine: `data/books/` and     `data/private/`, PRs must not carry a private graphify-out/ snapshot (studio-kit #47). (+6 more)

### Community 96 - "_is_substantial"
Cohesion: 0.14
Nodes (14): BookMetrics, _per_book(), QueryOutcome, What one arm actually returned for one ground-truth question., True when the arm that ran is not the arm that was asked for., One book's slice of an arm's score., Run one query through one arm, recording what actually happened.      A retrieva, hit-rate@k and MRR@k over `outcomes`, via `evals.metrics`.      Both mappings ar (+6 more)

### Community 97 - "Per-book breakdown"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error/degradation behavior, Named red tests, Planned (not this capstone): live Open Library connector, Public interface, Purpose, spec: connectors — lawful catalog federation (“Forbidden Stacks”), Verify

### Community 98 - "parse_file"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error behavior, Invariants, Named red tests (write before the code), Public interface, Purpose, spec: core-models — `homelib_core.models`, Verify

### Community 99 - "sqlite_only_smoke.sh"
Cohesion: 0.22
Nodes (8): Banned sources (binding), Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`, Verify

### Community 100 - "spec: agent-tools — `homelib_rag.agent`"
Cohesion: 0.43
Nodes (7): _db(), WP07 Coffee Table + progress named red tests — specs/coffee-table.md., test_acceptance_required_before_queued(), test_independent_read_listen_progress(), test_manual_survives_regeneration(), test_no_silent_reinsert_of_completed_or_removed(), test_remove_keeps_resource()

### Community 101 - "spec: coffee-table — persistent playlist (product §5.6)"
Cohesion: 0.40
Nodes (5): Addendum 2026-09-05 — what is true on the tip path, ADR-005 — Observatory replaces Grafana, Consequences, Context, Decision

### Community 102 - "spec: eval-gate — `evals/gate.py`"
Cohesion: 0.25
Nodes (8): Coffee Table playlist (spec-level), Cold start / demo session, Demo reset, Ingest pipeline run, Related pages, Scene anchor open, Search → cited answer, User flows

### Community 103 - "spec: evals-llm — `evals/llm_eval.py` + `evals/judge.py`"
Cohesion: 0.17
Nodes (6): _FakeConnection, _FakeCursor, Seed the fixture book/blocks/chunks/embeddings using the SAME embedder     `sear, Records every `execute()` call; replays one queued `fetchall()` result     per c, _seed(), _test_db_dsn()

### Community 104 - "spec: evals-retrieval — `evals/ground_truth.py` + `evals/retrieval_eval.py`"
Cohesion: 0.25
Nodes (7): APP_MODE, HOMELIB_SQLITE_PATH, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT_SECONDS, sqlite_only_smoke.sh script

### Community 105 - "spec: formats — `homelib_core.formats` + `homelib_core.normalize`"
Cohesion: 0.14
Nodes (14): _make_deps(), SQLite creates the file on first connect, so a never-seeded clone has a     reac, `/health` reports booleans only about the LLM — no substring of the     configur, test_feedback_success(), test_feedback_unknown_request_id_returns_404(), test_get_books(), test_health_degraded_when_db_down(), test_health_is_degraded_when_store_has_zero_books() (+6 more)

### Community 106 - "spec: ingestion — `apps/ingest/pipeline.py` (dlt)"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: coffee-table — persistent playlist (product §5.6), Verify

### Community 107 - "spec: monitoring — `query_log` + Grafana + `scripts/demo_traffic.py`"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: eval-gate — `evals/gate.py`, Verify

### Community 108 - "7. Technical architecture"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: evals-llm — `evals/llm_eval.py` + `evals/judge.py`, Verify

### Community 109 - "spec: progress — reading and listening positions"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: evals-retrieval — `evals/ground_truth.py` + `evals/retrieval_eval.py`, Verify

### Community 110 - "spec: projection — projector reading mode (product §5.9)"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: formats — `homelib_core.formats` + `homelib_core.normalize`, Verify

### Community 111 - "spec: provider — `LLMProvider` seam"
Cohesion: 0.25
Nodes (8): Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: ingestion — `apps/ingest/pipeline.py` (dlt), SQLite seed CLI (2026-09-05), Verify

### Community 112 - "spec: rerank — `homelib_rag.rerank`"
Cohesion: 0.14
Nodes (13): 10. Provenance and rights contract, 11. Numbers, 12. Models and providers, 1. What this project is built on, 2. At a glance, 3. The Shelf: Project Gutenberg, 4. The Catalog: Open Library Search API, 5. Banned sources and why (+5 more)

### Community 113 - "spec: rewrite — `homelib_rag.rewrite`"
Cohesion: 0.25
Nodes (8): 7.1 One service layer, two clients, 7.2 Provider contract, 7.3 Other interchangeability seams, 7.4 SQLite, 7.5 Embeddings, 7.6 Ingestion, 7.7 RAG and agent flow, 7. Technical architecture

### Community 114 - "spec: roadmap — `homelib_rag.roadmap`"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: progress — reading and listening positions, Verify

### Community 115 - "spec: rotunda — Library Crossroads doors (product §5.2)"
Cohesion: 0.14
Nodes (14): Architecture, Course map, Data, Development, Evaluation results, homelib, License, Quickstart (+6 more)

### Community 116 - "spec: scene-search — within-book exact/keyword/semantic/smart/ask"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: provider — `LLMProvider` seam, Verify

### Community 117 - "CLAUDE.md — HomeLib"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: rerank — `homelib_rag.rerank`, Verify

### Community 118 - "rerank.py"
Cohesion: 0.24
Nodes (11): prompt_hash(), `sha256("|".join([version, template, schema_shape]))`, hex-encoded.      The "|", Tests for `evals.judge.prompt_hash` — the prompt drift detector (specs/evals-llm, The spec pins the construction itself, not just "some hash"., Moving a character across the separator must not collide.      A naive `version, test_prompt_hash_changes_when_schema_shape_changes(), test_prompt_hash_changes_when_template_changes(), test_prompt_hash_changes_when_version_changes() (+3 more)

### Community 119 - "spec: client — `HomelibClient` in-process vs HTTP seam"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: rewrite — `homelib_rag.rewrite`, Verify

### Community 120 - "spec: editions — `APP_MODE` and the capability matrix"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: roadmap — `homelib_rag.roadmap`, Verify

### Community 121 - "spec: hybrid — `homelib_rag.hybrid`"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: rotunda — Library Crossroads doors (product §5.2), Verify

### Community 122 - "spec: indexing — `homelib_rag.index`"
Cohesion: 0.17
Nodes (11): Cost estimate (C1), Data contracts (field-level), Demo answer cache (C4b), Error/degradation behavior, Named red tests (write before the code), Online judge (C6), Public interface, Purpose (+3 more)

### Community 123 - "spec: observatory — in-app monitoring (replaces Grafana)"
Cohesion: 0.33
Nodes (6): expected_chunk_ids_from_snapshot(), manifest_rights_by_book_id(), test_chunk_ids_match_v1_snapshot(), test_expected_chunk_ids_match_canonical_count(), test_manifest_rights_maps_explicit_public_domain(), test_manifest_rights_skips_non_dict_entries()

### Community 124 - "spec: principals — demo sessions and local-user identity"
Cohesion: 0.29
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: editions — `APP_MODE` and the capability matrix, Verify

### Community 125 - "4. Editions and deployment model"
Cohesion: 0.29
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: hybrid — `homelib_rag.hybrid`, Verify

### Community 126 - "Commercial split and product ladder (owner 2026-09-01; evening pivot)"
Cohesion: 0.29
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: indexing — `homelib_rag.index`, Verify

### Community 127 - "spec: rights — fail-closed gate before index and audio"
Cohesion: 0.29
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: observatory — in-app monitoring (replaces Grafana), Verify

### Community 128 - "test_packaging.py"
Cohesion: 0.29
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: principals — demo sessions and local-user identity, Verify

### Community 129 - "RuntimeError"
Cohesion: 0.29
Nodes (7): 4.1 Edition matrix, 4.2 Public demo rules, 4.3 Home topology, 4.4 Reviewer Compose profile, 4.5 Future Apple provider, 4.6 Public-repository and commercial-product boundary, 4. Editions and deployment model

### Community 130 - "demo_ask.py"
Cohesion: 0.29
Nodes (7): Commercial split and product ladder (owner 2026-09-01; evening pivot), Obsidian (post-capstone §15, contract-first), Paid Home/Pro — same Forgejo repo after public GitHub; not this week, Product ladder, Protecting the product, Public app this week — restrained showcase copy, TTS / STT / Apple (post-capstone; do not ship this week)

### Community 131 - "demo_roadmap.py"
Cohesion: 0.29
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: rights — fail-closed gate before index and audio, Verify

### Community 132 - "14. Acceptance journeys"
Cohesion: 0.29
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: scene-search — within-book exact/keyword/semantic/smart/ask, Verify

### Community 133 - "15. Post-capstone roadmap"
Cohesion: 0.40
Nodes (3): A private write referenced a principal that does not exist., UnknownPrincipal, Exception

### Community 134 - "ADR-005 — Observatory replaces Grafana"
Cohesion: 0.21
Nodes (12): _graph_refresh_script(), Path, Homelib refreshes on the pushed protected ref — main, and only main.      The re, Execute the graph-refresh step script in a scratch repo with a stub graphify., Behavioural: a push to main rebuilds, commits and pushes the graph.      Until 2, Behavioural: the committed graph never carries the runner's workdir.      graphi, Behavioural: a push to a recreated `v2` neither rebuilds nor pushes.      A seco, _run_graph_refresh() (+4 more)

### Community 135 - "ADR-007 — Licence (provisional)"
Cohesion: 0.33
Nodes (5): Packaging invariants.  These are cheap to assert and expensive to discover later, PEP 561: without this file, installed type hints are invisible to mypy.      hom, The documented surface must be importable from the package root., test_package_ships_py_typed_marker(), test_public_names_are_exported()

### Community 136 - "ADR-009 — Audio deferred"
Cohesion: 0.31
Nodes (10): MonkeyPatch, Path, Direct unit tests for `apps.api.sqlite_deps.sqlite_get_book_block`.  Companion t, Migrate `db` (idempotent) and insert `book_id` with one block per text,     dens, Unknown book, and ordinal past the last block, both miss.      The function's ow, _seed_book_blocks(), sqlite_env(), test_sqlite_get_book_block_ignores_other_books_same_ordinal() (+2 more)

### Community 137 - "Design — how the magic-library look reaches the product"
Cohesion: 0.33
Nodes (6): 14. Acceptance journeys, Journey A — public reviewer, Journey B — manual playlist, Journey C — scene search, Journey D — home projector, Journey E — degraded operation

### Community 138 - "_compose"
Cohesion: 0.33
Nodes (6): 15. Post-capstone roadmap, Obsidian integration design, Phase 1 — home product hardening, Phase 2 — persistent cloud trial, Phase 3 — native Apple companion, Phase 4 — richer lawful federation

### Community 139 - "_gate_steps"
Cohesion: 0.18
Nodes (11): A. Rubric — the graded criteria (26 points), B. Self-hosted Docker readiness, C. Engineering quality (the "maintainable, extendable" half), Cut order (HTML prototype first), D. Nice to have — extendability, E. Known gaps, stated plainly, F. v2 work packages (WP00–WP11), H. WP00 landing checklist (this PR) (+3 more)

### Community 140 - "ADR-004 — SQLite replaces Postgres"
Cohesion: 0.40
Nodes (4): ADR-009 — Audio deferred, Consequences, Context, Decision

### Community 141 - "ADR-006 — Editions and hosting"
Cohesion: 0.20
Nodes (9): ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off, Consequences, Context, Decision, Evidence, Query rewrite: measured, and rejected, v2 SQLite re-measurement (2026-09-03), Verification (+1 more)

### Community 142 - "ADR-008 — Rights gate (unknown fails closed)"
Cohesion: 0.60
Nodes (4): main(), _parse_args(), _print_result(), Demo CLI: `POST /v1/ask` against a running homelib API — see specs/api.md.  Usag

### Community 143 - "Crossroads and doors"
Cohesion: 0.60
Nodes (4): main(), _parse_args(), _print_result(), Demo CLI: `POST /v1/roadmap` against a running homelib API — see specs/api.md.

### Community 144 - "HomeLib v2 — Developer Wiki"
Cohesion: 0.22
Nodes (7): _normalize_openapi(), Any, Contract-drift guard — see specs/api.md.  Asserts the generated OpenAPI schema (, Reduce a full OpenAPI document to the slice specs/api.md's     contract-drift gu, A cheap independent check that the snapshot itself is not stale: every     endpo, test_openapi_snapshot_matches(), test_snapshot_covers_every_endpoint_in_api_md()

### Community 145 - "12. Delivery plan"
Cohesion: 0.20
Nodes (9): Binding invariants, Chunking experiment (2026-09-06), Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: chunking — `homelib_core.chunk` (+1 more)

### Community 146 - "6. Data and rights model"
Cohesion: 0.28
Nodes (8): MonkeyPatch, Mentor door tool-use caption — `streamlit.testing.v1.AppTest`, same harness as `, A Mentor response whose `tool_calls` is non-empty renders a caption     naming t, An empty `tool_calls` (e.g. abstention, or an LLM-unreachable degrade)     rende, _seeded_mentor_response(), _selfhosted_against_closed_port(), test_mentor_tab_omits_tool_use_caption_when_no_tools_were_called(), test_mentor_tab_shows_tool_use_caption_when_tools_were_called()

### Community 147 - "9. Evaluation and monitoring"
Cohesion: 0.22
Nodes (8): Arm actually used, `hybrid`, `hybrid_rerank`, `lexical`, Per-book breakdown, Retrieval arm eval, RRF k sweep, `vector`

### Community 148 - "_all_job_commands"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error/degradation behavior, Named red tests, On-device Listen in Projection (iPadOS), Public interface, Purpose, spec: audio — capabilities and one lawful preview, Verify

### Community 149 - "pre-push"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error/degradation behavior, Named tests (all present), Public interface, Purpose, spec: ui — `apps/ui` (Streamlit Crossroads), The doors, Verify

### Community 150 - "homelib"
Cohesion: 1.00
Nodes (3): homelib, homelib-core, homelib-rag

### Community 151 - "__init__.py"
Cohesion: 0.50
Nodes (4): ADR-006 — Editions and hosting, Consequences, Context, Decision

### Community 152 - "__init__.py"
Cohesion: 0.50
Nodes (4): ADR-008 — Rights gate (unknown fails closed), Consequences, Context, Decision

### Community 153 - "__init__.py"
Cohesion: 0.50
Nodes (3): Crossroads and doors, Door map, How a door opens

### Community 154 - "__init__.py"
Cohesion: 0.22
Nodes (9): Move dlt's staged rows into the canonical `public` tables.      One `INSERT ..., _sync_staging_to_public(), _make_pipeline(), Row counts for every canonical table., Idempotency proof: load again over an existing load, counts identical.      Buil, The ELT transform is idempotent on its own, independent of dlt's merge.      Re-, _table_counts(), test_second_run_adds_no_duplicates() (+1 more)

### Community 155 - "__init__.py"
Cohesion: 0.50
Nodes (4): 12.1 Safety track, 12.2 Corrected calendar, 12.4 GO/NO-GO definition, 12. Delivery plan

### Community 156 - "__init__.py"
Cohesion: 0.50
Nodes (4): 6.1 Capstone datasets, 6.2 Rights manifest, 6.3 Deduplication, 6. Data and rights model

### Community 157 - "__init__.py"
Cohesion: 0.50
Nodes (4): 9.1 Retrieval evaluation, 9.2 LLM evaluation, 9.3 Observatory, 9. Evaluation and monitoring

### Community 158 - "Build evidence log"
Cohesion: 0.33
Nodes (9): _connect_returning(), _row(), test_search_lexical_maps_rows_to_hits_dense_rank_and_score_order(), test_search_lexical_page_none_when_block_ids_empty_skips_lookup(), test_search_lexical_page_none_when_no_block_has_page(), test_search_lexical_page_uses_first_block_with_page_in_block_ids_order(), test_search_lexical_query_is_parameterized_not_interpolated(), test_search_vector_embeds_query_and_uses_parameterized_cast() (+1 more)

### Community 161 - "llm_eval.md"
Cohesion: 0.25
Nodes (8): chunk_corpus(), Re-chunk every book in `docs` with one `(target_chars, overlap)` pair., Whitespace-token approximation, per the task brief (no `tiktoken`:     not a pro, Mean whitespace-token count of one whole chapter/section, across the     corpus, _whitespace_token_count(), whole_section_token_baseline(), test_chunk_corpus_produces_more_smaller_chunks_at_a_smaller_target(), test_whole_section_token_baseline_is_positive_and_book_independent_of_chunking()

### Community 162 - "_default_retrieve"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: agent-tools — `homelib_rag.agent`, Verify

### Community 171 - "test_ui_dockerfile_pins_pythonpath_so_apps_imports_resolve"
Cohesion: 0.29
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: client — `HomelibClient` in-process vs HTTP seam, Verify

### Community 172 - "test_streamlit_theme_pins_parchment_gold_from_mockups"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: projection — projector reading mode (product §5.9), Verify

### Community 175 - "test_ci_pytest_forces_workspace_basetemp"
Cohesion: 0.25
Nodes (7): Guards on the licence swap itself (ADR-007).  The repo used to ship an unfilled, LICENSE must be the PolyForm Noncommercial 1.0.0 text, not Apache., LICENSE-docs.md must exist and declare CC BY-NC-SA 4.0., Every pyproject.toml must declare PolyForm-Noncommercial-1.0.0.      None of the, test_docs_licence_is_cc_by_nc_sa(), test_license_is_polyform_noncommercial(), test_no_pyproject_declares_apache()

### Community 177 - "test_gitleaks_allowlists_never_exempt_whole_files"
Cohesion: 0.14
Nodes (29): ApiClientError, ApiUnavailableError, Raised for a 4xx/5xx response from the API.      ``detail`` carries the API's er, Raised when the API cannot be reached at all (timeout/connection)., _cast_vote(), main(), Client, Streamlit UI. Talks only to the public API, never to the database.  Rendering sh (+21 more)

### Community 178 - "test_drill_asserts_seed_counts_via_health"
Cohesion: 0.32
Nodes (7): Path, Guards on the public snapshot itself.  This repo is developed on a private Forge, No tracked, reviewer-facing doc may name the private Forgejo host,     its SSH p, `docs/handoffs/` becomes untracked in this same PR, so no tracked doc     may st, test_no_tracked_doc_links_to_handoffs(), test_public_docs_have_no_internal_hosts(), _tracked_public_doc_files()

### Community 179 - "test_drill_verifies_monitoring_via_observatory_not_grafana_panel_count"
Cohesion: 0.29
Nodes (6): AGENTS.md — HomeLib, Module map, Read-first order (token discipline), Skill routing, Standing rules, What this is

### Community 180 - "test_specs_ui_door_list_matches_crossroads_doors"
Cohesion: 0.29
Nodes (6): CLAUDE.md — HomeLib, Module map, Read-first order (token discipline), Skill routing, Standing rules, What this is

### Community 181 - "test_no_dotenv_file_is_tracked"
Cohesion: 0.33
Nodes (7): _default_embed(), _get_embedder(), float64, NDArray, Lazy singleton — mirrors `homelib_rag.index`/`sqlite_index`'s pattern.      Impo, Up to `k` `(chunk_id, book_id)` pairs, best first, by cosine similarity., vector_search()

### Community 182 - "test_ci_graph_guard_job_exists"
Cohesion: 0.43
Nodes (5): _doc(), docs/data-sources.md must agree with the pinned artefacts it describes., test_data_sources_doc_cites_only_existing_paths(), test_data_sources_doc_matches_manifest_and_catalog(), test_data_sources_doc_names_the_dataset_and_the_api()

### Community 183 - "test_ci_graph_refresh_pushes_to_current_protected_branch"
Cohesion: 0.33
Nodes (6): _fixes_items(), The 2026 gap report is a promise list: every numbered item in its "FIXES gap LLM, Behavioural: no numbered FIXES item may still carry a `**TODO**`; each     must, The report is only useful if a reviewer can find it from the two     documents t, test_gap_report_is_linked_from_readme_and_course_map(), test_gap_report_items_are_all_resolved()

### Community 184 - "test_ci_graph_refresh_commits_the_bootstrap_graph"
Cohesion: 0.33
Nodes (5): Cloud runtime (showcase URL), If something is red at the deadline, Open it as a stranger, Submission — LLM Zoomcamp 2026, What is submitted

### Community 185 - "test_graphifyignore_excludes_generated_and_data_paths"
Cohesion: 0.33
Nodes (6): FIXES gap LLM Zoomcamp 2026, HomeLib vs LLM Zoomcamp 2026 — coverage gap report, Part 1 — What the 2026 cohort teaches and where HomeLib shows it, Part 3 — Corrections to `docs/course-map.md`, Table 1 — Module → techniques taught → homework asks, Table 2 — Course topic → module → HomeLib status

### Community 186 - "test_just_ci_includes_the_secret_scan"
Cohesion: 0.33
Nodes (6): _collapse_whitespace(), The shape the LLM is asked to produce for one citation.      Deliberately has NO, Whitespace-insensitive form for quote comparison.      Book text is hard-wrapped, The passage a quote actually came from, or `None` if it came from none.      The, _RawCitation, _resolve_quote()

### Community 187 - "__init__.py"
Cohesion: 0.40
Nodes (4): ADR-007 — Licence (provisional), Consequences, Context, Decision

### Community 188 - "__init__.py"
Cohesion: 0.40
Nodes (4): Design — how the magic-library look reaches the product, Path from mockup to screen, Skills and gates, What is not built, and why

### Community 189 - "__init__.py"
Cohesion: 0.40
Nodes (5): _gate_steps(), The scan is a CI step, not just a file sitting in the repo., A shallow clone would make the history scan vacuous.      `gitleaks git` reads t, test_ci_checks_out_full_history_for_the_secret_scan(), test_gitleaks_runs_in_ci()

### Community 190 - "__init__.py"
Cohesion: 0.50
Nodes (4): HomeLib v2 — Developer Wiki, Implementation status (v2 branch stack), Pages, Quick links

### Community 191 - "test_specs_ui_door_list_matches_crossroads_doors"
Cohesion: 0.50
Nodes (4): _all_job_commands(), Every `run:` command in the workflow, keyed by job name., Whatever the hook defers must actually be enforced somewhere.      The fast loca, test_some_ci_job_runs_the_full_suite_the_hook_skips()

### Community 192 - "test_no_dotenv_file_is_tracked"
Cohesion: 0.50
Nodes (4): ADR-004 — SQLite replaces Postgres, Consequences, Context, Decision

### Community 193 - "test_ci_graph_guard_job_exists"
Cohesion: 0.50
Nodes (4): make_block_id(), Compute a `Block.block_id`.      Stable across runs and processes: same `(book_i, test_parse_pdf_native_text_page_provenance_and_offsets(), test_make_block_id_is_stable_and_deterministic()

### Community 194 - "Path"
Cohesion: 0.67
Nodes (3): can_index_text(), Full-text indexing is allowed only for explicit bundle/public-domain rights., test_can_index_text_allows_only_bundle_and_public_domain()

## Knowledge Gaps
- **563 isolated node(s):** `ui-entrypoint.sh script`, `API_PORT`, `UI_PORT`, `GRAFANA_PORT`, `POSTGRES_PORT` (+558 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **147 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Universal in-memory book representation — see specs/core-models.md.  One data mo` connect `decision-log.md` to `ApiClient`, `BaseModel`, `ChatMessage`, `test_index.py`, `LLMResponse`, `test_gate.py`, `test_rewrite.py`, `test_format_pdf.py`, `InProcessClient`, `test_sqlite_ingest.py`, `sqlite.py`, `test_format_djvu.py`, `chunk_book`, `sqlite_index.py`, `chunk.py`, `retrieval_eval.py`, `parse_epub`, `test_rerank.py`, `test_v2_routes.py`, `test_inprocess_bridge.py`, `Extension points`, `3. Proposed SQLite tables`, `Debugging and troubleshooting`, `HomeLib — improved product and build plan v2`, `homelib — submission checklist`, `test_openapi_snapshot.py`, `Repo structure`, `spec: core-models — `homelib_core.models``?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **Why does `A single ranked retrieval result from one search arm or rerank pass.` connect `SyncASGITransport` to `v2_routes.py`, `test_judge.py`, `test_retrieval_eval.py`, `ApiClient`, `BaseModel`, `ChatMessage`, `sqlite_index.py`, `bump_index_revision`, `LLMResponse`, `test_inprocess_bridge.py`, `sqlite_pipeline.py`, `HomeLib v2 — reviewer handoff`, `test_format_djvu.py`, `pipeline.py`, `test_fetch_catalog.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `AppMode` connect `sqlite_deps.py` to `ApiClient`, `BaseModel`, `test_view_model.py`, `coffee_table.py`, `Local development`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `connect()` (e.g. with `test_inprocess_client_serves_real_requests_over_asgi()` and `_connect()`) actually correct?**
  _`connect()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `migrate()` (e.g. with `test_inprocess_client_serves_real_requests_over_asgi()` and `_connect()`) actually correct?**
  _`migrate()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `GroundTruthRow` (e.g. with `AnswerSimilarityScore` and `SavedAnswer`) actually correct?**
  _`GroundTruthRow` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `homelib applications: api, ui, ingest.`, `FastAPI service — the single contract every consumer talks through.`, `FastAPI service — the single contract every consumer talks through.  See specs/a` to the rest of the system?**
  _1262 weakly-connected nodes found - possible documentation gaps or missing edges._