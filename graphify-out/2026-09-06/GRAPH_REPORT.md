# Graph Report - hostexecutor  (2026-09-06)

## Corpus Check
- 189 files · ~226,364 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3077 nodes · 5637 edges · 380 communities (160 shown, 220 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 1336 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `636d72ef`
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
- test_ci_graph_refresh_pushes_to_current_protected_branch
- test_ci_graph_refresh_commits_the_bootstrap_graph
- test_graphifyignore_excludes_generated_and_data_paths
- test_just_ci_includes_the_secret_scan
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
- Connection
- MonkeyPatch
- Path
- Any
- Client
- Response
- Client
- MonkeyPatch
- Any
- MonkeyPatch
- Path
- MonkeyPatch
- Path
- AskResponse
- BookSummary
- Citation
- RoadmapStep
- Any
- AskResponse
- BookSummary
- Citation
- Level
- RoadmapStep
- Path
- Self
- OpenAI
- Path
- Citation
- Any
- Namespace
- Path
- Any
- Connection
- Namespace
- Path
- CaptureFixture
- Path
- CaptureFixture
- MonkeyPatch
- Path
- Any
- Exception
- MonkeyPatch
- Path
- Any
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
- Any
- Block
- Connection
- Level
- RoadmapResponse
- Any
- Path
- Any
- Connection
- SentenceTransformer
- CatalogSearch
- Citation
- Level
- RoadmapStep
- OpenAI
- CatalogSearch
- Level
- Connection
- Any
- Connection
- Path
- Row
- Any
- MonkeyPatch
- Any
- Exception
- MonkeyPatch
- Exception
- MonkeyPatch
- Any
- MonkeyPatch
- Connection
- MonkeyPatch
- Path
- Any
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
1. `connect()` - 61 edges
2. `ApiClient` - 55 edges
3. `migrate()` - 54 edges
4. `ChatMessage` - 44 edges
5. `answer()` - 35 edges
6. `Universal in-memory book representation — see specs/core-models.md.  One data mo` - 34 edges
7. `LLMUnreachableError` - 34 edges
8. `Deps` - 33 edges
9. `Citation` - 32 edges
10. `RoadmapParseError` - 32 edges

## Surprising Connections (you probably didn't know these)
- `_fetch_page()` --references--> `Error/degradation behavior`  [EXTRACTED]
  apps/ingest/fetch_catalog.py → specs/client.md
- `fetch_catalog_entries()` --references--> `Error/degradation behavior`  [EXTRACTED]
  apps/ingest/fetch_catalog.py → specs/client.md
- `main()` --calls--> `Error/degradation behavior`  [EXTRACTED]
  apps/ingest/fetch_catalog.py → specs/client.md
- `fetch_one()` --references--> `Error/degradation behavior`  [EXTRACTED]
  apps/ingest/fetch_corpus.py → specs/client.md
- `run_fetch()` --references--> `Error/degradation behavior`  [EXTRACTED]
  apps/ingest/fetch_corpus.py → specs/client.md

## Import Cycles
- None detected.

## Communities (380 total, 220 thin omitted)

### Community 0 - "v2_routes.py"
Cohesion: 0.06
Nodes (79): GroundTruthRow, One `question -> chunk_id` ground-truth pair., judge(), JudgeParseError, JudgeScore, LLM-as-judge scoring for answer-synthesis prompt variants — see specs/evals-llm., One judged case. `suggested_score` is the judge's own overall rating and     is, The judge system prompt as it will actually be sent, for `variant`.      `str.re (+71 more)

### Community 1 - "test_judge.py"
Cohesion: 0.06
Nodes (75): answer(), _book_metadata(), _build_context_prompt(), _degraded_response(), _dsn(), OpenAIClient, `(base_url, api_key, model)` from the environment, in this order:      1. `LLM_A, Default `OpenAICompatibleClient`, backed by the `openai` SDK against     an Open (+67 more)

### Community 2 - "test_api.py"
Cohesion: 0.05
Nodes (63): append_history(), Baseline, compare_to_baseline(), _current_git_sha(), _describe(), load_baseline(), MetricSpec, Eval regression gate — see specs/eval-gate.md.  Turns "the eval numbers got wors (+55 more)

### Community 3 - "ApiClient"
Cohesion: 0.11
Nodes (22): FixtureRequest, MockTransport, HomelibClient, HttpClient, Selfhosted edition — FastAPI over HTTP with per-call timeouts., client(), demo_client(), _inprocess() (+14 more)

### Community 4 - "BaseModel"
Cohesion: 0.13
Nodes (42): BaseModel, OkResponse, Deps, get_health(), post_feedback(), post_ingest(), post_roadmap(), QueryLogRow (+34 more)

### Community 5 - "ChatMessage"
Cohesion: 0.16
Nodes (21): Exception, ApiClientError, ApiUnavailableError, Raised for a 4xx/5xx response from the API.      ``detail`` carries the API's er, Raised when the API cannot be reached at all (timeout/connection)., _cast_vote(), main(), Streamlit UI. Talks only to the public API, never to the database.  Rendering sh (+13 more)

### Community 6 - "test_answer.py"
Cohesion: 0.12
Nodes (52): Compose mounts a pipeline-seeded DB that never ran store.seed().      After HOME, sqlite_env(), test_playlist_current_ok_on_migrate_only_sqlite_without_seed(), _create_minimal_staging(), test_sync_staging_rolls_back_on_catalog_error(), connect(), current_index_revision(), logical_checksum() (+44 more)

### Community 7 - "test_view_model.py"
Cohesion: 0.05
Nodes (65): AST, _imported_modules(), _make_ask_response(), _make_book(), _make_citation(), _make_step(), Behavioural tests for apps/ui/view_model.py.  These drive the pure helper functi, Named red from specs/client.md — alias of the AST walk above. (+57 more)

### Community 8 - "test_fetch_corpus.py"
Cohesion: 0.07
Nodes (28): ApiClient, Block, Thin synchronous client over the homelib public API., Mint a demo principal via `POST /v1/demo/session` and use it from now on., Adopt an existing demo session id (e.g. one kept in Streamlit session         st, RoadmapResponse, client(), Behavioural tests for apps/ui/api_client.py against a stubbed transport.  Every (+20 more)

### Community 9 - "models.py"
Cohesion: 0.09
Nodes (34): What the LLM itself is asked to produce.      Deliberately has no `judge_model`, _RawJudgeScore, Provenance, Where a `Block` came from in the original source file., AgentResult, Drive the request -> tool -> result loop until the model produces a     final me, run_agent(), ToolCallRecord (+26 more)

### Community 10 - "hybrid_search"
Cohesion: 0.15
Nodes (20): Cursor, _connect(), _dsn(), _embed_query(), _first_page(), _load_embedder(), Lexical (Postgres FTS) and vector (pgvector) search arms — see specs/indexing.md, Render an embedding as pgvector's text input format: `[0.1,0.2,...]`.      Retur (+12 more)

### Community 11 - "test_index.py"
Cohesion: 0.10
Nodes (32): LLMUsage, SQLite dispatch on homelib_rag.index when HOMELIB_SQLITE_PATH is set., The reviewer-visible symptom: with only SQLite reachable, a grounded     answer, `agent.search_catalog` is bound in three places (API deps, the roadmap     wrapp, _ScriptedClient, test_agent_search_catalog_uses_sqlite_when_path_set(), test_answer_end_to_end_not_degraded_on_sqlite_only_host(), _catalog_returning() (+24 more)

### Community 12 - "LLMResponse"
Cohesion: 0.10
Nodes (38): An `OpenAICompatibleClient` that substitutes the system prompt.      `answer()`, _VariantClient, CatalogEntry, A catalog record (e.g. Open Library) used to enrich, never to replace, our copy., Citation, CitationValidationError, _collapse_whitespace(), LLMUnreachableError (+30 more)

### Community 13 - "connect"
Cohesion: 0.07
Nodes (31): _default_rewriter(), Production query rewrite. Imported lazily — see `_default_retrieve`., _call_llm(), _client(), _model_name(), LLM query rewriter — see specs/rewrite.md.  Asks an LLM to turn a user's natural, Internal typed shape the LLM is asked to produce.      Not exposed publicly — `r, Call the configured LLM and return its raw response content.      Raises on any (+23 more)

### Community 14 - "test_pipeline.py"
Cohesion: 0.18
Nodes (37): get_deps(), FastAPI dependency. `apps/api/tests/test_api.py` overrides this     wholesale vi, AddPlaylistItemRequest, AudioCapabilities, delete_playlist_item(), get_audio_capabilities(), get_observatory(), get_playlist_current() (+29 more)

### Community 15 - "test_gate.py"
Cohesion: 0.12
Nodes (33): fetch_one(), FetchOutcome, load_manifest(), main(), ManifestEntry, Shelf fetcher — see specs/corpus.md.  Downloads the public-domain books listed i, Download, hash-verify, and (for txt) boilerplate-strip one manifest entry., Fetch every manifest entry, continuing past individual failures. (+25 more)

### Community 16 - "test_rewrite.py"
Cohesion: 0.10
Nodes (28): _is_substantial(), load_corpus_chunks(), Recompute every chunk in the committed corpus snapshot.      Deterministic given, Skip chunks too short, or too table-of-contents-like, to ask about., Stratified, seeded sample of up to `n` chunks spread across all books.      Chun, sample_chunks(), _fake_chunk(), fixture_chunks() (+20 more)

### Community 17 - "test_format_pdf.py"
Cohesion: 0.09
Nodes (36): PdfReader, _extract_authors(), _extract_title(), _is_likely_scanned(), _ocr_extract(), parse_pdf(), PDF format handler — see specs/formats.md.  Two extraction paths, chosen per doc, Run PyMuPDF's OCR text extraction over every page of `path`.      Raises `Runtim (+28 more)

### Community 19 - "test_metrics.py"
Cohesion: 0.12
Nodes (36): ChunkId, GroundTruth, RankedResults, _first_relevant_rank(), hit_rate_at_k(), mrr_at_k(), Retrieval-quality metrics — see specs/evals-retrieval.md.  Reimplemented from fi, 1-based rank of the first id in `topk` that is in `relevant_set`, or None. (+28 more)

### Community 20 - "connectors.py"
Cohesion: 0.11
Nodes (31): Protocol, _can_merge(), CatalogConnector, ConnectorHit, ConnectorName, ConnectorTimeout, DiscoverResult, _edition_ambiguous() (+23 more)

### Community 21 - "coffee_table.py"
Cohesion: 0.16
Nodes (33): LookupError, StrEnum, accept_proposed(), add_item(), get_playlist(), _parse_ts(), patch_items(), Playlist (+25 more)

### Community 22 - "InProcessClient"
Cohesion: 0.11
Nodes (27): parse_djvu(), Extract a `BookDoc` from a DJVU file via `djvutxt`.      Raises `RuntimeError` (, _attach_page_text(), _build_real_djvu_fixture(), _fake_run(), _FakeWhich, Red-first tests for `homelib_core.formats.djvu` — see specs/formats.md.  Written, `shutil.which` monkeypatched to `None` -> a specific, actionable `RuntimeError`. (+19 more)

### Community 23 - "test_ground_truth.py"
Cohesion: 0.21
Nodes (15): LogCaptureFixture, build_ground_truth(), generate_questions(), One LLM call generating up to `n` specific, retrieval-shaped questions.      Ret, Generate ground-truth rows for `chunks`, one LLM call per chunk.      A chunk th, test_build_ground_truth_never_reaches_a_real_llm(), test_build_ground_truth_retry_appends_a_genuinely_new_question(), test_build_ground_truth_warns_and_dedupes_when_llm_repeats_itself() (+7 more)

### Community 24 - "sqlite_pipeline.py"
Cohesion: 0.11
Nodes (30): _build_default_deps(), _connect(), _default_counts(), _default_db_reachable(), _default_ingest(), _default_list_books(), _default_llm_reachable(), _default_log_query() (+22 more)

### Community 25 - "test_sqlite_ingest.py"
Cohesion: 0.14
Nodes (30): TempPathFactory, expected_chunk_ids_from_snapshot(), manifest_rights_by_book_id(), run_sqlite_pipeline(), _book(), _corpus_counts(), _fake_embeddings(), _fresh_db() (+22 more)

### Community 26 - "sqlite.py"
Cohesion: 0.09
Nodes (29): _book(), clean_corpus_tables(), _drop_staging_schemas(), live_database_url(), Tests for apps/ingest/pipeline.py — see specs/ingestion.md named red tests.  Uni, This process's throwaway database — never the application's., Drop dlt's staging dataset (and the `_staging` merge dataset dlt makes     along, Empty the canonical tables and drop dlt's staging schemas. (+21 more)

### Community 27 - "test_format_djvu.py"
Cohesion: 0.10
Nodes (29): books_default_rights_status(), can_index_text(), create_demo_session(), _current_reset_generation(), DemoSession, DemoSessionExpired, _enforce_active_demo_session(), _ensure_local_user() (+21 more)

### Community 28 - "HttpClient"
Cohesion: 0.12
Nodes (21): SessionStateProxy, AppMode, AskResponse, BookSummary, Citation, _extract_detail(), Provenance, HTTP client for the homelib public API.  This is the ONLY module under ``apps/ui (+13 more)

### Community 29 - "pipeline.py"
Cohesion: 0.10
Nodes (25): build_rotunda_html(), door_from_query(), _json_for_script(), The Crossroads rotunda — the rotating room of doors (specs/rotunda.md).  Pure mo, JSON that is safe inside an inline `<script>`.      Every `<` becomes the JSON e, Resolve the door an Enter link asked for.      `?door=X` arrives when the rotund, Return the rotunda fragment that `app.py` renders with `st.html`.      `active`, Rotunda: pure-string behaviour of the rotating room (specs/rotunda.md).  No scre (+17 more)

### Community 30 - "chunk_book"
Cohesion: 0.13
Nodes (28): DrawFn, chunk_book(), Chunk `doc` into retrieval-sized, citation-traceable `Chunk`s.      Chunks never, _build_doc(), _lorem_sentences(), _make_block(), _make_provenance(), Red-first tests for `homelib_core.chunk` — see specs/chunking.md.  These tests a (+20 more)

### Community 31 - "test_fetch_catalog.py"
Cohesion: 0.16
Nodes (27): hybrid_search(), Search `q`, returning `(hits, mode_used)`.      `mode="lexical"` or `mode="vecto, _hit(), _raising(), Red tests for `homelib_rag.hybrid` — see specs/hybrid.md.  `search_lexical` and, Symmetric case to the lexical-down test above., Lexical-only mode: at most k, best-first, rank 1-based and dense., Vector-only mode: at most k, best-first, rank 1-based and dense. (+19 more)

### Community 32 - "view_model.py"
Cohesion: 0.12
Nodes (22): Universal in-memory book representation — see specs/core-models.md.  One data mo, _build_prompt(), build_roadmap(), _candidate_line(), _parse_and_validate(), Personalized reading roadmap generation — see specs/roadmap.md.  Turns a user's, Parse+validate one LLM roadmap response. Raises `RoadmapParseError`.      Trunca, Build a `RoadmapResponse` grounded only in retrieved catalog candidates.      `L (+14 more)

### Community 33 - "app.py"
Cohesion: 0.08
Nodes (7): _insert_block(), _insert_book(), _insert_chunk(), WP04 scene-search red tests — see specs/scene-search.md.  Cross-encoder rerank a, scene_db(), test_metadata_only_resource_raises_not_searchable(), test_unknown_resource_raises_not_found()

### Community 34 - "test_retrieval_eval.py"
Cohesion: 0.05
Nodes (76): Retriever, Rewriter, ArmMetrics, _connect(), _coverage_lines(), _degradation_section(), _dsn(), _gate_metrics() (+68 more)

### Community 35 - "sqlite_index.py"
Cohesion: 0.14
Nodes (25): float32, NDArray, book_metadata(), _connect(), _decode_embedding(), _embed_query(), _first_page(), _fts_query() (+17 more)

### Community 36 - "chunk.py"
Cohesion: 0.10
Nodes (25): NamedTuple, _atomic_unit_spans(), _chapter_key(), _make_chunk_id(), _pack_indices(), _pack_sentences(), _points_to_spans(), Block-aware, sentence-boundary chunking — see specs/chunking.md.  Turns a `BookD (+17 more)

### Community 37 - "test_rotunda.py"
Cohesion: 0.07
Nodes (27): Contract-drift guard, `DELETE /v1/playlists/current/items/{item_id}`, Endpoints — live v1 (OpenAPI snapshot), Error and degradation behavior, `GET /health`, `GET /v1/areas` / `POST /v1/areas`, `GET /v1/audio/capabilities`, `GET /v1/blocks/{id}` (+19 more)

### Community 39 - "v2 target — product.md §8 (markdown this WP; not in the snapshot yet)"
Cohesion: 0.09
Nodes (13): _connect_never_called(), Red tests for `homelib_rag.index` — see specs/indexing.md.  Unit tests (the defa, Undo whatever a test left in the lazy embedder singleton.      The unit tests ab, A constant name lets two concurrent runs delete each other's database.      Guar, Point `index.py`'s `_connect()` at the throwaway test database for one test., _restore_embedder_singleton(), _seeded_db(), test_search_lexical_empty_query_raises() (+5 more)

### Community 40 - "bump_index_revision"
Cohesion: 0.10
Nodes (9): _base_deps(), _missing_block(), Behavioural tests for `apps/api` — see specs/api.md.  No live Postgres, no live, test_get_block_endpoint_not_found(), test_get_deps_returns_same_singleton(), test_roadmap_llm_unreachable_maps_to_503(), test_roadmap_parse_error_maps_to_502(), test_roadmap_success() (+1 more)

### Community 41 - "write_report"
Cohesion: 0.16
Nodes (23): _doc_to_entry(), fetch_catalog_entries(), _fetch_page(), main(), Open Library catalog fetcher — see specs/corpus.md.  Pulls curated subject slice, Fetch and dedupe (by ``ol_key``) catalog entries across every subject slice., Write the provenance header line followed by one JSON line per entry., Fetch one page of results for ``subject``, retrying with backoff on failure. (+15 more)

### Community 42 - "answer.py"
Cohesion: 0.13
Nodes (18): bump_index_revision(), compute_index_revision(), Rebuild the FTS5 mirror from canonical `chunks` rows (WP04)., Stable revision id for the cached embedding matrix (product §7.5)., Recompute and persist `index_revision` after ingest or FTS rebuild., rebuild_chunks_fts(), _reset_caches_for_tests(), sqlite_dispatch_db() (+10 more)

### Community 43 - "retrieval_eval.py"
Cohesion: 0.17
Nodes (23): _book_id_in_clause(), _default_db_path(), _default_manifest_path(), _embedding_json_to_blob(), main(), manifest_rights_from_path(), _purge_non_indexable_corpus(), dlt ingestion into SQLite — WP03; see specs/ingestion.md and ADR-004. (+15 more)

### Community 44 - "parse_txt"
Cohesion: 0.18
Nodes (21): Reorder `hits` by cross-encoder relevance to `q`.      Returns the reordered hit, rerank(), _FakeCrossEncoder, _hit(), _RaisingCrossEncoder, Red tests for `homelib_rag.rerank` — see specs/rerank.md.  The cross-encoder its, Stand-in whose construction always fails, like a missing-weights load., Deterministic stand-in: scores a pair 1.0 if `text` mentions "bees". (+13 more)

### Community 45 - "parse_epub"
Cohesion: 0.18
Nodes (19): Element, _check_not_zip_bomb(), _element_text(), _localname(), parse_epub(), EPUB format handler — see specs/formats.md.  Block granularity: each `h1`-`h6`,, Extract a `BookDoc` from an EPUB file., _build_epub_bytes() (+11 more)

### Community 46 - "ground_truth.py"
Cohesion: 0.13
Nodes (21): build_book(), build_snapshot(), _clean_text_path(), main(), Build the committed corpus snapshot — see specs/corpus.md.  Parses every manifes, Path to the boilerplate-stripped text `fetch_corpus.py --fetch` wrote., Parse one manifest entry into a `BookDoc` carrying its manifest metadata.      `, Parse every manifest entry and write the gzipped snapshot. Returns book count. (+13 more)

### Community 47 - "test_rerank.py"
Cohesion: 0.12
Nodes (22): _call_llm(), _clean_questions(), _client(), _echoes_opening(), _is_self_referential(), main(), _model_name(), _normalize_words() (+14 more)

### Community 48 - "test_v2_routes.py"
Cohesion: 0.14
Nodes (21): _load_json_line(), make_block_id(), Compute a `Block.block_id`.      Stable across runs and processes: same `(book_i, Deserialize from `to_jsonl` output.          Raises `ValueError` naming the offe, test_parse_pdf_native_text_page_provenance_and_offsets(), _make_block(), _make_book_doc(), _make_provenance() (+13 more)

### Community 50 - "test_inprocess_bridge.py"
Cohesion: 0.10
Nodes (20): 0. Step-0 live snapshot (reconciled this session), 1. Local stack ports (this machine’s `.env`), 2.1 UI PYTHONPATH fix (independent re-verify), 2.2 Ask → citation resolve → feedback → query_log, 2.3 Seed / Grafana / embeddings vs chat, 2. Verified this session (paste / re-run), 3. Checklist verification matrix (`CHECKLIST.md` on **`v2` tip**), 4. Honest residuals (+12 more)

### Community 51 - "Extension points"
Cohesion: 0.16
Nodes (18): _markdown_heading(), parse_txt(), _plaintext_heading(), TXT/Markdown format handler — see specs/formats.md.  Heading inference: a Markdo, An all-caps / Title-Case line under 80 chars, followed by a blank line., Extract a `BookDoc` from a plain-text or Markdown file., _assert_offsets_dense_and_stable(), Red-first tests for `homelib_core.formats.txt` — see specs/formats.md.  Written (+10 more)

### Community 52 - "sqlite_deps.py"
Cohesion: 0.14
Nodes (16): Edition / runtime flags from the environment.  `APP_MODE` and timeout defaults., read_app_mode(), read_llm_max_output_tokens(), read_llm_timeout_seconds(), build_observatory(), ObservatoryChart, ObservatoryPoint, ObservatoryResponse (+8 more)

### Community 53 - "3. Proposed SQLite tables"
Cohesion: 0.19
Nodes (17): blocks_resource(), books_resource(), catalog_resource(), chunk_embeddings_resource(), chunks_resource(), _embed_batch(), embed_texts(), _get_model() (+9 more)

### Community 54 - "parse_djvu"
Cohesion: 0.12
Nodes (19): _ensure_ivfflat_index(), main(), _make_pipeline(), A token unique to this process, for namespacing shared-host resources.      The, Move dlt's staged rows into the canonical `public` tables.      One `INSERT ..., Build the pgvector cosine index AFTER data is loaded.      ivfflat centroids are, Load books/blocks/chunks/chunk_embeddings/catalog into dlt's staging     schema,, run_pipeline() (+11 more)

### Community 55 - "Data model and schemas"
Cohesion: 0.11
Nodes (13): A model swap does not fix it either (2026-08-31), ADR-003 — Answer prompt: keep the incumbent, on a null result, Baseline, Consequences, Context, Correction: these measurements are less stable than either of us claimed, Decision, The winner is flagged unproven, and that is the point (+5 more)

### Community 56 - "Decision log"
Cohesion: 0.11
Nodes (19): Degradation tests, Documentation improvements, Editions and entitlements, Eval before default changes, Extension points, Import boundaries, Improving the system, New API routes (v2 §8) (+11 more)

### Community 57 - "Local development"
Cohesion: 0.16
Nodes (10): _FakeCursor, _patch_connect(), Scripted cursor for exercising `main._connect()` production helpers., test_default_counts_returns_table_totals(), test_default_db_reachable_true_when_select_one_succeeds(), test_default_list_books_maps_rows_to_summaries(), test_default_log_query_inserts_monitoring_row(), test_default_log_query_swallows_db_errors() (+2 more)

### Community 58 - "HomeLib v2 — reviewer handoff"
Cohesion: 0.20
Nodes (10): 1. Project intent, 2. Architecture & schema (v2 on `v2` branch), 3. How to run locally, 5. Wiki map, 6. What to verify in review, 7. Known gaps / improvements (priority), 8. Current git state, HomeLib v2 — reviewer handoff (+2 more)

### Community 59 - "Debugging and troubleshooting"
Cohesion: 0.29
Nodes (17): _book_rights(), _canonical_text(), _chapter_section(), _chunk_in_chapter(), _context_window(), _exact_hits(), _filter_hits_to_scope(), _fuse_hits() (+9 more)

### Community 60 - "Retrieval pipeline"
Cohesion: 0.11
Nodes (18): 1. Sources examined, 2. Entities mined from the HTML, 3. Proposed SQLite tables, 4. HTML → table map, 5. Mockup-only entities (not in the HTML), 6. Contradictions (CONFUSION — do not silently pick), 7. WP02 red-test hooks, 8. Out of scope this PR / paid-tier must not be created this week (+10 more)

### Community 61 - "roadmap.py"
Cohesion: 0.12
Nodes (7): API tests for observatory + Coffee Table routes (WP07/WP10)., WP10 live feedback path: POST /v1/feedback updates query_log (UI→API→DB)., WP10: demo_traffic.py --n 40 leaves Observatory with ≥5 non-empty chart ids., The server-side contract the client fix (H3) relies on: a minted     `X-Demo-Ses, test_demo_mode_same_header_shares_principal_and_missing_header_does_not(), test_demo_traffic_populates_observatory_charts(), test_feedback_ui_to_db_roundtrip()

### Community 62 - "HomeLib — improved product and build plan v2"
Cohesion: 0.15
Nodes (15): _decode_djvu_string(), djvu_available(), _djvutxt_version(), _extract_page_texts(), _first_quoted_string(), _iter_top_level_forms(), DJVU format handler — see specs/formats.md.  Extracts the hidden text layer via, Yield each top-level parenthesized S-expression in `text`, in order. (+7 more)

### Community 63 - "SyncASGITransport"
Cohesion: 0.06
Nodes (43): Request, RuntimeError, open_store(), SQLite-backed helpers for FastAPI when HOMELIB_SQLITE_PATH is set (P0 wire)., sqlite_counts(), sqlite_db_reachable(), sqlite_get_block(), sqlite_list_books() (+35 more)

### Community 64 - "12.3 Work packages"
Cohesion: 0.16
Nodes (15): build_roadmap(), _connect(), _dsn(), get_block(), _parse_arguments(), Explicit function-calling agent loop — see specs/agent-tools.md.  A hand-rolled, Full-text search over the ingested book shelf (RRF hybrid search)., Open a new Postgres connection. Test seam: monkeypatch this directly. (+7 more)

### Community 65 - "homelib — submission checklist"
Cohesion: 0.17
Nodes (12): A. Rubric — the graded criteria (26 points), B. Self-hosted Docker readiness, C. Engineering quality (the "maintainable, extendable" half), Cut order (HTML prototype first), D. Nice to have — extendability, E. Known gaps, stated plainly, F. v2 work packages (WP00–WP11), G. Never commit before public GitHub (`just publish`) (+4 more)

### Community 66 - "Stakeholder picky review + wiki/mermaid handoff — 2026-09-05"
Cohesion: 0.33
Nodes (6): 0. Live snapshot (read-only, start of session), 1. Scoreboard (rubric, cold re-score on the stack), 3. Talk track (5–8 min), 4. Re-verify (next agent or owner), 5. Pasteable prompt for the next model, Stakeholder picky review + wiki/mermaid handoff — 2026-09-05

### Community 67 - "HomeLib v2.1 — final merged execution plan (capstone rebuild + product)"
Cohesion: 0.13
Nodes (15): _make_deps(), `/health` reports booleans only about the LLM — no substring of the     configur, SQLite creates the file on first connect, so a never-seeded clone has a     reac, test_feedback_success(), test_feedback_unknown_request_id_returns_404(), test_get_block_endpoint_found(), test_get_books(), test_health_degraded_when_db_down() (+7 more)

### Community 68 - "Architecture overview"
Cohesion: 0.13
Nodes (15): API endpoint map, Catalog and rights, Core entities, Corpus (ported from v1), Data model and schemas, Entity relationship diagram, Identity, Index and embedding revision (+7 more)

### Community 69 - "prompt_hash"
Cohesion: 0.13
Nodes (15): Answer prompt and rewrite (supplementary), Chunk ID stability for eval ground truth, Decision log, HomelibClient: InProcess vs Http, Hybrid search: BM25/FTS5 + vector + RRF vs alternatives, Ingest: dlt ELT shape, staging → canonical, idempotency, Licence — owner decision, recorded not fixed, Observability: Observatory vs Grafana (+7 more)

### Community 70 - "QueryOutcome"
Cohesion: 0.13
Nodes (15): APP_MODE behaviour, Canonical commands, Common debug commands, Compose profiles, Demo smoke (Sep 2 gate per evidence addendum), Environment, First-time setup, LM Studio (Mac home edition) (+7 more)

### Community 71 - "test_index_sqlite_dispatch.py"
Cohesion: 0.17
Nodes (6): _FakeConnection, _FakeCursor, Seed the fixture book/blocks/chunks/embeddings using the SAME embedder     `sear, Records every `execute()` call; replays one queued `fetchall()` result     per c, _seed(), _test_db_dsn()

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

### Community 77 - "homelib"
Cohesion: 0.24
Nodes (11): _llm_json(), Vector search "raises" (simulated at the retrieve seam): response is     200 wit, ADR-001 (docs/adrs/ADR-001-retrieval-arm.md) measured query rewriting     agains, A scripted fake `OpenAICompatibleClient`. No network., _ScriptedClient, test_ask_arm_none_uses_default_arm(), test_ask_degrades_to_200_when_vector_backend_down(), test_ask_explicit_arm_is_honored() (+3 more)

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
Cohesion: 0.18
Nodes (11): Architecture, Course map, Data, Development, Evaluation results, homelib, License, Quickstart (+3 more)

### Community 82 - "cold_clone_drill.sh"
Cohesion: 0.22
Nodes (8): _hit(), _fuse(), _hybrid(), Reciprocal Rank Fusion over the lexical and vector search arms — see specs/hybri, Reciprocal-Rank-Fuse two arms' hits, dedup by `chunk_id`, top `k`.      Each arm, Hit, Shared retrieval hit model — see specs/indexing.md.  `Hit` is defined once, here, A single ranked retrieval result from one search arm or rerank pass.

### Community 83 - "test_repo_hygiene.py"
Cohesion: 0.24
Nodes (8): API_PORT, fail(), GRAFANA_PORT, OLLAMA_PORT, POSTGRES_PORT, cold_clone_drill.sh script, step(), UI_PORT

### Community 84 - "ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off"
Cohesion: 0.20
Nodes (7): Streamlit Community Cloud edition: the files Cloud reads and the seed it needs., `streamlit_app.py` is a shim over `apps/ui/app.py`, not a second UI., Cloud resolves from uv.lock; GPU torch wheels would blow its disk/RSS., `.python-version` (uv, pyenv, Cloud reviewers) agrees with pyproject., test_cloud_entrypoint_runs_the_same_ui_main(), test_python_version_file_matches_requires_python(), test_uv_lock_pins_cpu_torch_index()

### Community 85 - "Decision"
Cohesion: 0.20
Nodes (9): Guards on the gates themselves.  A config file that looks like a guarantee but i, Hygiene pin. `compose up --build` builds only the services it starts; the     in, Purchased ebooks never leave this machine: `data/books/` and     `data/private/`, Without 1bis, a committed graph is dead weight — sessions still crawl., A branch push plus an open PR must not fire two runs of the same commit.      Wi, test_ci_does_not_double_trigger_on_branch_push_and_a_pull_request(), test_claude_md_routes_named_symbols_through_graphify_explain(), test_personal_books_dir_is_untracked_and_ignored() (+1 more)

### Community 86 - "Repo structure"
Cohesion: 0.22
Nodes (3): Crossroads doors rendered through Streamlit's own test harness.  `streamlit.test, The rotunda's Enter reloads the page on `?door=X`; the app must open X     and d, test_door_query_param_opens_that_door_and_is_consumed()

### Community 87 - "write_ground_truth"
Cohesion: 0.22
Nodes (9): ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off, Consequences, Context, Decision, Evidence, Query rewrite: measured, and rejected, v2 SQLite re-measurement (2026-09-03), Verification (+1 more)

### Community 88 - "spec: answer — `homelib_rag.answer`"
Cohesion: 0.22
Nodes (9): ADR-010 — Single repo until public; paid tier after, Consequences, Context, Decision, Obsidian (post-public-publish, contract-first — product §15), Post-public-publish / paid tier (same Forgejo repo later — not another git remote), Product ladder, Public app this week (+1 more)

### Community 89 - "spec: audio — capabilities and one lawful preview"
Cohesion: 0.22
Nodes (9): Before pasting the URL, open it as a stranger, Final-day order of operations, If something is red at the deadline, Peer reviews — do not skip these, Preconditions — all of these, not most, Publishing, Streamlit Community Cloud (showcase URL), Submission runbook — LLM Zoomcamp 2026 (+1 more)

### Community 90 - "spec: chunking — `homelib_core.chunk`"
Cohesion: 0.22
Nodes (9): Apps, Branch model, Docker and CI, Documentation map, Packages, Related pages, Repo structure, Specs vs code vs tests vs data (+1 more)

### Community 91 - "spec: connectors — lawful catalog federation (“Forbidden Stacks”)"
Cohesion: 0.25
Nodes (6): _normalize_openapi(), Contract-drift guard — see specs/api.md.  Asserts the generated OpenAPI schema (, Reduce a full OpenAPI document to the slice specs/api.md's     contract-drift gu, A cheap independent check that the snapshot itself is not stale: every     endpo, test_openapi_snapshot_matches(), test_snapshot_covers_every_endpoint_in_api_md()

### Community 92 - "spec: core-models — `homelib_core.models`"
Cohesion: 0.25
Nodes (8): parse_file(), Format dispatcher — see specs/formats.md.  `parse_file` is the single entry poin, Derive a `book_id` slug from a file stem (e.g. `"Moby Dick!" -> "moby-dick"`)., Dispatch `path` to the right format handler by its suffix.      Dispatches on `p, _slugify(), test_parse_file_dispatches_djv_suffix(), test_parse_file_dispatches_txt_and_md(), test_parse_file_unknown_extension_raises_value_error()

### Community 93 - "spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`"
Cohesion: 0.33
Nodes (9): _connect_returning(), _row(), test_search_lexical_maps_rows_to_hits_dense_rank_and_score_order(), test_search_lexical_page_none_when_block_ids_empty_skips_lookup(), test_search_lexical_page_none_when_no_block_has_page(), test_search_lexical_page_uses_first_block_with_page_in_block_ids_order(), test_search_lexical_query_is_parameterized_not_interpolated(), test_search_vector_embeds_query_and_uses_parameterized_cast() (+1 more)

### Community 94 - "spec: ui — `apps/ui` (Streamlit Crossroads)"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: answer — `homelib_rag.answer`, Store dispatch (2026-09-05), Verify

### Community 95 - "User flows"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error/degradation behavior, Named red tests, Planned (not this capstone): on-device Listen in Projection, Public interface, Purpose, spec: audio — capabilities and one lawful preview, Verify

### Community 96 - "_is_substantial"
Cohesion: 0.22
Nodes (8): Binding invariants, Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: chunking — `homelib_core.chunk`, Verify

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
Cohesion: 0.25
Nodes (6): Addendum 2026-09-05 — what is true on the tip path, ADR-005 — Observatory replaces Grafana, Consequences, Context, Decision, Monitoring and feedback

### Community 102 - "spec: eval-gate — `evals/gate.py`"
Cohesion: 0.25
Nodes (8): Coffee Table playlist (spec-level), Cold start / demo session, Demo reset, Ingest pipeline run, Related pages, Scene anchor open, Search → cited answer, User flows

### Community 103 - "spec: evals-llm — `evals/llm_eval.py` + `evals/judge.py`"
Cohesion: 0.25
Nodes (7): Arm actually used, `hybrid`, `hybrid_rerank`, `lexical`, Per-book breakdown, Retrieval arm eval, `vector`

### Community 104 - "spec: evals-retrieval — `evals/ground_truth.py` + `evals/retrieval_eval.py`"
Cohesion: 0.25
Nodes (7): APP_MODE, HOMELIB_SQLITE_PATH, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT_SECONDS, sqlite_only_smoke.sh script

### Community 105 - "spec: formats — `homelib_core.formats` + `homelib_core.normalize`"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: agent-tools — `homelib_rag.agent`, Verify

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
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: monitoring — `query_log` + Grafana + `scripts/demo_traffic.py`, Verify

### Community 113 - "spec: rewrite — `homelib_rag.rewrite`"
Cohesion: 0.25
Nodes (8): 7.1 One service layer, two clients, 7.2 Provider contract, 7.3 Other interchangeability seams, 7.4 SQLite, 7.5 Embeddings, 7.6 Ingestion, 7.7 RAG and agent flow, 7. Technical architecture

### Community 114 - "spec: roadmap — `homelib_rag.roadmap`"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: progress — reading and listening positions, Verify

### Community 115 - "spec: rotunda — Library Crossroads doors (product §5.2)"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: projection — projector reading mode (product §5.9), Verify

### Community 116 - "spec: scene-search — within-book exact/keyword/semantic/smart/ask"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: provider — `LLMProvider` seam, Verify

### Community 117 - "CLAUDE.md — HomeLib"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: rerank — `homelib_rag.rerank`, Verify

### Community 118 - "rerank.py"
Cohesion: 0.29
Nodes (6): CrossEncoder, _load_model(), Cross-encoder reranker — see specs/rerank.md.  Improves ranking quality on top o, Return the process-wide `CrossEncoder` singleton, loading it if needed.      Ret, Reset the lazy singleton. Test-only — not part of the public API., _reset_singleton_for_tests()

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
Cohesion: 0.25
Nodes (8): Data contracts (field-level), Error/degradation behavior, Named tests (all present), Public interface, Purpose, spec: ui — `apps/ui` (Streamlit Crossroads), The doors, Verify

### Community 123 - "spec: observatory — in-app monitoring (replaces Grafana)"
Cohesion: 0.29
Nodes (6): CLAUDE.md — HomeLib, Module map, Read-first order (token discipline), Skill routing, Standing rules, What this is

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
Cohesion: 0.33
Nodes (6): 2. Findings, Fixed in this stack (each with named tests — see PR bodies for the regression matrix), Found while verifying (not in the review brief), Phase 2 picky review of the train (2026-09-06, owner: "verify picky all PRs"), Recorded, not fixed (owner decisions), Stack status at hand-off

### Community 134 - "ADR-005 — Observatory replaces Grafana"
Cohesion: 0.33
Nodes (6): _hit(), test_ask_writes_query_log_row(), test_default_retrieve_applies_rerank_for_hybrid_rerank(), test_default_retrieve_keeps_hybrid_order_when_rerank_unavailable(), test_default_retrieve_marks_degraded_when_search_falls_back(), test_default_retrieve_single_arms()

### Community 135 - "ADR-007 — Licence (provisional)"
Cohesion: 0.33
Nodes (5): Packaging invariants.  These are cheap to assert and expensive to discover later, PEP 561: without this file, installed type hints are invisible to mypy.      hom, The documented surface must be importable from the package root., test_package_ships_py_typed_marker(), test_public_names_are_exported()

### Community 136 - "ADR-009 — Audio deferred"
Cohesion: 0.33
Nodes (6): Data contracts (field-level), Named red tests, Public interface, Purpose, spec: client — `HomelibClient` in-process vs HTTP seam, Verify

### Community 137 - "Design — how the magic-library look reaches the product"
Cohesion: 0.33
Nodes (6): 14. Acceptance journeys, Journey A — public reviewer, Journey B — manual playlist, Journey C — scene search, Journey D — home projector, Journey E — degraded operation

### Community 138 - "_compose"
Cohesion: 0.33
Nodes (6): 15. Post-capstone roadmap, Obsidian integration design, Phase 1 — home product hardening, Phase 2 — persistent cloud trial, Phase 3 — native Apple companion, Phase 4 — richer lawful federation

### Community 139 - "_gate_steps"
Cohesion: 0.40
Nodes (4): ADR-007 — Licence (provisional), Consequences, Context, Decision

### Community 140 - "ADR-004 — SQLite replaces Postgres"
Cohesion: 0.40
Nodes (4): ADR-009 — Audio deferred, Consequences, Context, Decision

### Community 141 - "ADR-006 — Editions and hosting"
Cohesion: 0.40
Nodes (4): Design — how the magic-library look reaches the product, Path from mockup to screen, Skills and gates, What is not built, and why

### Community 142 - "ADR-008 — Rights gate (unknown fails closed)"
Cohesion: 0.60
Nodes (4): main(), _parse_args(), _print_result(), Demo CLI: `POST /v1/ask` against a running homelib API — see specs/api.md.  Usag

### Community 143 - "Crossroads and doors"
Cohesion: 0.60
Nodes (4): main(), _parse_args(), _print_result(), Demo CLI: `POST /v1/roadmap` against a running homelib API — see specs/api.md.

### Community 144 - "HomeLib v2 — Developer Wiki"
Cohesion: 0.50
Nodes (4): HomeLib v2 — Developer Wiki, Implementation status (v2 branch stack), Pages, Quick links

### Community 145 - "12. Delivery plan"
Cohesion: 0.40
Nodes (5): _compose(), `.env.example` ships `APP_MODE=demo` for the Community Cloud path. The     api s, Hygiene (string/structure match, not behavioural). The api service reads     `/d, test_compose_api_pins_selfhosted_like_ui(), test_compose_ingest_can_write_sqlite_seed()

### Community 146 - "6. Data and rights model"
Cohesion: 0.40
Nodes (5): _gate_steps(), The scan is a CI step, not just a file sitting in the repo., A shallow clone would make the history scan vacuous.      `gitleaks git` reads t, test_ci_checks_out_full_history_for_the_secret_scan(), test_gitleaks_runs_in_ci()

### Community 147 - "9. Evaluation and monitoring"
Cohesion: 0.50
Nodes (4): 4. Plan 2.1 / Zoomcamp checklist matrix, Named WP04 eval numbers (SQLite, 2026-09-03), Rubric (CHECKLIST §A) — mostly **v1 evidence on `main`**, v2 WPs (CHECKLIST §F)

### Community 148 - "_all_job_commands"
Cohesion: 0.50
Nodes (4): Resolve manifest rights — explicit `rights_status` only; else fail closed., rights_status_from_manifest(), test_rights_status_rejects_unknown_explicit_value(), test_rights_status_requires_explicit_manifest_field()

### Community 149 - "pre-push"
Cohesion: 0.50
Nodes (4): ADR-004 — SQLite replaces Postgres, Consequences, Context, Decision

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
Cohesion: 0.50
Nodes (4): _all_job_commands(), Every `run:` command in the workflow, keyed by job name., Whatever the hook defers must actually be enforced somewhere.      The fast loca, test_some_ci_job_runs_the_full_suite_the_hook_skips()

## Knowledge Gaps
- **560 isolated node(s):** `API_PORT`, `UI_PORT`, `GRAFANA_PORT`, `POSTGRES_PORT`, `OLLAMA_PORT` (+555 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **220 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Universal in-memory book representation — see specs/core-models.md.  One data mo` connect `view_model.py` to `BaseModel`, `models.py`, `test_index.py`, `LLMResponse`, `test_rewrite.py`, `test_format_pdf.py`, `InProcessClient`, `sqlite_pipeline.py`, `test_sqlite_ingest.py`, `sqlite.py`, `chunk_book`, `sqlite_index.py`, `chunk.py`, `bump_index_revision`, `write_report`, `retrieval_eval.py`, `parse_epub`, `ground_truth.py`, `test_rerank.py`, `test_v2_routes.py`, `Extension points`, `3. Proposed SQLite tables`, `HomeLib — improved product and build plan v2`, `SyncASGITransport`, `12.3 Work packages`, `spec: core-models — `homelib_core.models``?**
  _High betweenness centrality (0.266) - this node is a cross-community bridge._
- **Why does `Error/degradation behavior` connect `ChatMessage` to `test_fetch_corpus.py`, `write_report`, `ADR-009 — Audio deferred`, `test_gate.py`?**
  _High betweenness centrality (0.252) - this node is a cross-community bridge._
- **Why does `spec: client — `HomelibClient` in-process vs HTTP seam` connect `ADR-009 — Audio deferred` to `ChatMessage`, `test_models.py`?**
  _High betweenness centrality (0.233) - this node is a cross-community bridge._
- **Are the 60 inferred relationships involving `connect()` (e.g. with `open_store()` and `sqlite_env()`) actually correct?**
  _`connect()` has 60 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `ApiClient` (e.g. with `build_inprocess_client()` and `SyncASGITransport`) actually correct?**
  _`ApiClient` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 50 inferred relationships involving `migrate()` (e.g. with `open_store()` and `sqlite_env()`) actually correct?**
  _`migrate()` has 50 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `ChatMessage` (e.g. with `judge()` and `JudgeParseError`) actually correct?**
  _`ChatMessage` has 38 INFERRED edges - model-reasoned connections that need verification._