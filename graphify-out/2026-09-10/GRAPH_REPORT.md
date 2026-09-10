# Graph Report - hostexecutor  (2026-09-10)

## Corpus Check
- 236 files · ~333,836 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 4233 nodes · 9225 edges · 299 communities (199 shown, 100 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 1698 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fda46c7f`
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
- Extension points
- ADR-006 — Editions and hosting
- Path
- Any
- DltResource
- LoadInfo
- Path
- Pipeline
- SentenceTransformer
- ADR-009 — Audio deferred
- _compute_cost_usd
- get_book_block_endpoint
- rights_status_from_manifest
- ADR-008 — Rights gate (unknown fails closed)
- COST-LATENCY.md
- Path
- MonkeyPatch
- Path
- HomeLib v2 — Developer Wiki
- EVAL.md — Track E interview artifact
- MonkeyPatch
- Path
- pre-push
- Any
- Path
- Response
- datetime
- Path
- test_gap_report.py
- ADR-007 — Licence (provisional)
- Design — how the magic-library look reaches the product
- MonkeyPatch
- Path
- test_user_agent.py
- LLM prompt-variant eval
- Documentation licence
- main
- ui-entrypoint.sh
- OpenAI
- Path
- Citation
- CaptureFixture
- MonkeyPatch
- Path
- Block
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
- Block
- Provenance
- Any
- Connection
- SentenceTransformer
- OpenAI
- Any
- MonkeyPatch
- Connection
- MonkeyPatch
- Path
- MonkeyPatch
- MonkeyPatch
- Namespace
- Namespace
- MonkeyPatch
- Path

## God Nodes (most connected - your core abstractions)
1. `connect()` - 97 edges
2. `migrate()` - 89 edges
3. `LLMResponse` - 69 edges
4. `ApiClient` - 59 edges
5. `CatalogEntry` - 56 edges
6. `Hit` - 53 edges
7. `ChatMessage` - 51 edges
8. `GroundTruthRow` - 47 edges
9. `answer()` - 47 edges
10. `_make_deps()` - 46 edges

## Surprising Connections (you probably didn't know these)
- `QueryLogRow` --uses--> `RoadmapParseError`  [INFERRED]
  apps/api/main.py → packages/homelib-rag/src/homelib_rag/roadmap.py
- `QueryLogRow` --uses--> `BookDoc`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py
- `QueryLogRow` --uses--> `CatalogEntry`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py
- `QueryLogRow` --uses--> `LLMUnreachableError`  [INFERRED]
  apps/api/main.py → packages/homelib-rag/src/homelib_rag/answer.py
- `QueryLogRow` --uses--> `OpenAICompatibleClient`  [INFERRED]
  apps/api/main.py → packages/homelib-rag/src/homelib_rag/answer.py

## Import Cycles
- None detected.

## Communities (299 total, 100 thin omitted)

### Community 0 - "v2_routes.py"
Cohesion: 0.17
Nodes (6): SQLite dispatch on homelib_rag.index when HOMELIB_SQLITE_PATH is set., The reviewer-visible symptom: with only SQLite reachable, a grounded     answer, `agent.search_catalog` is bound in three places (API deps, the roadmap     wrapp, _ScriptedClient, test_agent_search_catalog_uses_sqlite_when_path_set(), test_answer_end_to_end_not_degraded_on_sqlite_only_host()

### Community 1 - "test_judge.py"
Cohesion: 0.07
Nodes (72): append_history(), Baseline, _column_index(), compare_to_baseline(), _current_git_sha(), _describe(), _is_separator_row(), load_baseline() (+64 more)

### Community 2 - "test_api.py"
Cohesion: 0.17
Nodes (11): A. Rubric — the graded criteria (26 points), B. Self-hosted Docker readiness, C. Engineering quality (the "maintainable, extendable" half), Cut order (HTML prototype first), D. Nice to have — extendability, E. Known gaps, stated plainly, F. v2 work packages (WP00–WP11), H. WP00 landing checklist (this PR) (+3 more)

### Community 3 - "ApiClient"
Cohesion: 0.13
Nodes (26): AskResponse, answer_shelf_meta(), _book_matches_genre(), _catalog_link_line(), _CatalogLink, _format_book_line(), _genre_from_question(), is_shelf_meta_intent() (+18 more)

### Community 4 - "BaseModel"
Cohesion: 0.09
Nodes (42): _in_memory_tracer_provider(), _llm_json(), _make_deps(), Vector search "raises" (simulated at the retrieve seam): response is     200 wit, ADR-001 (docs/adrs/ADR-001-retrieval-arm.md) measured query rewriting     agains, Passage content Q must still retrieve + cite; shelf-meta must not short-circuit., A scripted fake `OpenAICompatibleClient`. No network., Inventory Ask must list books via list_books — never empty passage refuse. (+34 more)

### Community 5 - "ChatMessage"
Cohesion: 0.17
Nodes (18): MonkeyPatch, Path, apply_streamlit_secrets_to_environ(), build_homelib_client(), Copy known demo keys from Streamlit secrets into ``os.environ`` if unset., True for Cloud/local demo: ``APP_MODE=demo`` and no ``API_URL``.      Compose al, Factory: demo → InProcessClient; else HttpClient(API_URL)., wants_inprocess_client() (+10 more)

### Community 6 - "test_answer.py"
Cohesion: 0.13
Nodes (55): Path, Connection, MonkeyPatch, Path, MonkeyPatch, test_load_indexed_chunk_ids_reads_sqlite(), main(), connect() (+47 more)

### Community 7 - "test_view_model.py"
Cohesion: 0.10
Nodes (26): _make_ask_response(), _make_citation(), AskResponse, Citation, `/v1/blocks/{id}` is keyed on block ids; a chunk_id 404s there.      The previou, test_ask_metric_captions_include_latency_and_token_breakdown(), test_ask_metric_captions_mark_cache_hit(), test_block_id_for_citation_uses_the_block_id_not_the_chunk_id() (+18 more)

### Community 8 - "test_fetch_corpus.py"
Cohesion: 0.05
Nodes (35): ApiClient, Block, _extract_detail(), InProcessClient, Any, Client, Response, Best-effort extraction of the ``{"detail": str}`` error envelope. (+27 more)

### Community 9 - "models.py"
Cohesion: 0.07
Nodes (59): MonkeyPatch, Response, BaseHTTPRequestHandler, ParseResult, build_read_article_html(), Clean article HTML for Safari Listen to Page (not Streamlit chrome)., Top-level HTML document Safari Reader / Listen to Page can detect., ReadPage (+51 more)

### Community 10 - "hybrid_search"
Cohesion: 0.05
Nodes (48): MonkeyPatch, Path, build_official_preview_stage_html(), is_allowlisted_official_url(), load_official_preview_books(), normalize_official_language(), normalize_projection_source(), projection_wants_chrome_hidden() (+40 more)

### Community 11 - "test_index.py"
Cohesion: 0.19
Nodes (14): merge_catalog_with_shelf(), _needle_hits_blob(), Bridge shelf titles into catalog candidates for Mentor / Roadmap.  The Open Libr, Return shelf books matching the goal/interests by title, author, or topic., Catalog first, then shelf rows whose title is not already present., shelf_catalog_entries(), Shelf → catalog bridge for Stoicism / Meditations Mentor+Roadmap., test_merge_catalog_with_shelf_appends_new_title() (+6 more)

### Community 12 - "LLMResponse"
Cohesion: 0.09
Nodes (43): Any, Any, Any, MonkeyPatch, AgentResult, _parse_arguments(), Drive the request -> tool -> result loop until the model produces a     final me, run_agent() (+35 more)

### Community 13 - "connect"
Cohesion: 0.09
Nodes (24): _default_rewriter(), Production query rewrite. Imported lazily — see `_default_retrieve`., Ask an LLM to rewrite `q` for retrieval; fall back to `q` on failure.      Alway, rewrite_query(), _FakeChat, _FakeChoice, _FakeClient, _FakeCompletion (+16 more)

### Community 14 - "test_pipeline.py"
Cohesion: 0.05
Nodes (96): _book_titles_for_boost(), _build_default_deps(), _cache_index_revision(), _compute_cost_usd(), _connect(), _default_counts(), _default_db_reachable(), _default_ingest() (+88 more)

### Community 15 - "test_gate.py"
Cohesion: 0.13
Nodes (22): build_book(), build_snapshot(), _clean_text_path(), main(), Build the committed corpus snapshot — see specs/corpus.md.  Parses every manifes, Path to the boilerplate-stripped text `fetch_corpus.py --fetch` wrote., Parse one manifest entry into a `BookDoc` carrying its manifest metadata.      `, Parse every manifest entry and write the gzipped snapshot. Returns book count. (+14 more)

### Community 16 - "test_rewrite.py"
Cohesion: 0.10
Nodes (28): _is_substantial(), load_corpus_chunks(), Recompute every chunk in the committed corpus snapshot.      Deterministic given, Skip chunks too short, or too table-of-contents-like, to ask about., Stratified, seeded sample of up to `n` chunks spread across all books.      Chun, sample_chunks(), _fake_chunk(), fixture_chunks() (+20 more)

### Community 17 - "test_format_pdf.py"
Cohesion: 0.09
Nodes (36): PdfReader, _extract_authors(), _extract_title(), _is_likely_scanned(), _ocr_extract(), parse_pdf(), PDF format handler — see specs/formats.md.  Two extraction paths, chosen per doc, Run PyMuPDF's OCR text extraction over every page of `path`.      Raises `Runtim (+28 more)

### Community 18 - "decision-log.md"
Cohesion: 0.08
Nodes (49): Embedder, float64, Namespace, NDArray, Path, ndarray, Path, build_reference_lookup() (+41 more)

### Community 19 - "test_metrics.py"
Cohesion: 0.10
Nodes (40): ChunkId, GroundTruth, GroundTruthBooks, RankedBooks, RankedResults, _first_relevant_rank(), hit_rate_at_k(), hit_rate_book() (+32 more)

### Community 20 - "connectors.py"
Cohesion: 0.05
Nodes (69): Any, Client, Path, MonkeyPatch, Path, Protocol, Behavioural tests for lawful catalog federation — specs/connectors.md.  Fixtures, test_ambiguous_editions_never_merge() (+61 more)

### Community 21 - "coffee_table.py"
Cohesion: 0.18
Nodes (30): Any, Connection, datetime, Row, upsert_progress(), LookupError, StrEnum, _current_playlist_id() (+22 more)

### Community 22 - "InProcessClient"
Cohesion: 0.11
Nodes (29): parse_djvu(), Extract a `BookDoc` from a DJVU file via `djvutxt`.      Raises `RuntimeError` (, _attach_page_text(), _build_real_djvu_fixture(), _fake_run(), _FakeWhich, Red-first tests for `homelib_core.formats.djvu` — see specs/formats.md.  Written, `shutil.which` monkeypatched to `None` -> a specific, actionable `RuntimeError`. (+21 more)

### Community 23 - "test_ground_truth.py"
Cohesion: 0.21
Nodes (15): LogCaptureFixture, build_ground_truth(), generate_questions(), One LLM call generating up to `n` specific, retrieval-shaped questions.      Ret, Generate ground-truth rows for `chunks`, one LLM call per chunk.      A chunk th, test_build_ground_truth_never_reaches_a_real_llm(), test_build_ground_truth_retry_appends_a_genuinely_new_question(), test_build_ground_truth_warns_and_dedupes_when_llm_repeats_itself() (+7 more)

### Community 24 - "sqlite_pipeline.py"
Cohesion: 0.09
Nodes (55): Exception, Any, Any, _build_intake_prompt(), detect_high_stakes_notice(), mentor_intake(), Level, Analyze a goal and return a proposal — never persists Areas/Wings/items.      Dr (+47 more)

### Community 25 - "test_sqlite_ingest.py"
Cohesion: 0.14
Nodes (34): CaptureFixture, Connection, MonkeyPatch, Path, TempPathFactory, staging_db_path(), _book(), _corpus_counts() (+26 more)

### Community 26 - "sqlite.py"
Cohesion: 0.07
Nodes (37): books_resource(), _book(), clean_corpus_tables(), _drop_staging_schemas(), live_database_url(), Tests for apps/ingest/pipeline.py — see specs/ingestion.md named red tests.  Uni, This process's throwaway database — never the application's., Drop dlt's staging dataset (and the `_staging` merge dataset dlt makes     along (+29 more)

### Community 27 - "test_format_djvu.py"
Cohesion: 0.07
Nodes (61): Exception, Any, _blob_has_goal_tokens(), build_path(), _evidence_blob(), _goal_content_tokens(), _has_on_goal_evidence(), _LLMIntakeOutput (+53 more)

### Community 28 - "HttpClient"
Cohesion: 0.11
Nodes (39): Any, Connection, datetime, books_default_rights_status(), compute_index_revision(), create_demo_session(), current_index_revision(), _current_reset_generation() (+31 more)

### Community 29 - "pipeline.py"
Cohesion: 0.15
Nodes (29): Exception, MonkeyPatch, _hit(), _raising(), Red tests for `homelib_rag.hybrid` — see specs/hybrid.md.  `search_lexical` and, Symmetric case to the lexical-down test above., Lexical-only mode: at most k, best-first, rank 1-based and dense., Vector-only mode: at most k, best-first, rank 1-based and dense. (+21 more)

### Community 30 - "chunk_book"
Cohesion: 0.13
Nodes (28): DrawFn, chunk_book(), Chunk `doc` into retrieval-sized, citation-traceable `Chunk`s.      Chunks never, _build_doc(), _lorem_sentences(), _make_block(), _make_provenance(), Red-first tests for `homelib_core.chunk` — see specs/chunking.md.  These tests a (+20 more)

### Community 31 - "test_fetch_catalog.py"
Cohesion: 0.15
Nodes (20): Cursor, _connect(), _dsn(), _embed_query(), _first_page(), _load_embedder(), Lexical (Postgres FTS) and vector (pgvector) search arms — see specs/indexing.md, Render an embedding as pgvector's text input format: `[0.1,0.2,...]`.      Retur (+12 more)

### Community 32 - "view_model.py"
Cohesion: 0.20
Nodes (21): Rewriter, Score one arm over `rows`.      `rewrite=True` routes every question through `ho, run_arm(), _fixed_retriever(), A fake `Retriever` returning a canned ranking per question., _row(), test_default_run_never_calls_the_rewriter(), test_degraded_hybrid_is_reported_as_the_arm_that_actually_ran() (+13 more)

### Community 33 - "app.py"
Cohesion: 0.16
Nodes (32): scene_search(), _insert_block(), _insert_book(), _insert_chunk(), _mock_scene_embedder(), Connection, MonkeyPatch, Path (+24 more)

### Community 34 - "test_retrieval_eval.py"
Cohesion: 0.10
Nodes (33): delete_playlist_item(), _discover_from_catalog(), _discover_resources(), get_audio_capabilities(), get_observatory(), get_playlist_current(), get_progress_endpoint(), get_resources() (+25 more)

### Community 35 - "sqlite_index.py"
Cohesion: 0.10
Nodes (40): float32, Any, Connection, NDArray, Path, Row, book_metadata(), browse_catalog() (+32 more)

### Community 36 - "chunk.py"
Cohesion: 0.10
Nodes (25): NamedTuple, _atomic_unit_spans(), _chapter_key(), _make_chunk_id(), _pack_indices(), _pack_sentences(), _points_to_spans(), Block-aware, sentence-boundary chunking — see specs/chunking.md.  Turns a `BookD (+17 more)

### Community 37 - "test_rotunda.py"
Cohesion: 0.15
Nodes (23): MonkeyPatch, boost_books_named_in_query(), When the question names a shelf title, keep that book's hits first., _hit(), Regression tests for Ask ranking helpers — LIVE living-deliberately gap., Full title need not appear; a distinctive token like Walden is enough., When the full n-gram is absent, matching content tokens still rank., style' / 'story' / 'civil' are title tokens, not book names. (+15 more)

### Community 38 - "test_models.py"
Cohesion: 0.21
Nodes (4): ADR-004 — SQLite replaces Postgres, Consequences, Context, Decision

### Community 39 - "v2 target — product.md §8 (markdown this WP; not in the snapshot yet)"
Cohesion: 0.09
Nodes (13): _connect_never_called(), Red tests for `homelib_rag.index` — see specs/indexing.md.  Unit tests (the defa, Undo whatever a test left in the lazy embedder singleton.      The unit tests ab, A constant name lets two concurrent runs delete each other's database.      Guar, Point `index.py`'s `_connect()` at the throwaway test database for one test., _restore_embedder_singleton(), _seeded_db(), test_search_lexical_empty_query_raises() (+5 more)

### Community 40 - "bump_index_revision"
Cohesion: 0.17
Nodes (27): Any, Exception, _catalog_returning(), _entry(), _llm_response(), Behavioural tests for `homelib_rag.roadmap` — see specs/roadmap.md.  No live Pos, The client's 400-token default is sized for answers; a multi-step     roadmap's, First call malformed, repair call valid: a valid `RoadmapResponse` is     return (+19 more)

### Community 41 - "write_report"
Cohesion: 0.18
Nodes (20): Path, _arm_metrics(), _four_arms(), Tests for evals/retrieval_eval.py — the retrieval-arm bake-off.  Every test here, test_load_questions_budget_spreads_across_books_instead_of_truncating(), test_load_questions_default_budget_takes_every_row(), test_load_questions_skips_blank_lines(), test_models_allow_extra_fields() (+12 more)

### Community 42 - "answer.py"
Cohesion: 0.14
Nodes (33): Connection, MonkeyPatch, Path, _load_matrix(), _MatrixCache, SQLite twin of `homelib_rag.agent.search_catalog`: subject overlap when     `sub, _reset_caches_for_tests(), WP04 SQLite index tests — FTS5 + cached NumPy matrix. (+25 more)

### Community 43 - "retrieval_eval.py"
Cohesion: 0.15
Nodes (29): MonkeyPatch, Path, API tests for observatory + Coffee Table routes (WP07/WP10)., Audit S03: GET /v1/progress restores the principal's last-read row., Compose mounts a pipeline-seeded DB that never ran store.seed().      After HOME, WP10 live feedback path: POST /v1/feedback updates query_log (UI→API→DB)., WP10: demo_traffic.py --n 40 leaves Observatory with ≥5 non-empty chart ids., The server-side contract the client fix (H3) relies on: a minted     `X-Demo-Ses (+21 more)

### Community 44 - "parse_txt"
Cohesion: 0.10
Nodes (32): judge(), JudgeParseError, JudgeScore, LLM-as-judge scoring for answer-synthesis prompt variants — see specs/evals-llm., One judged case. `suggested_score` is the judge's own overall rating and     is, A compact `name:type,...` description of what the judge must return.      Derive, The judge system prompt as it will actually be sent, for `variant`.      `str.re, Score one answered case, with exactly one bounded repair retry.      Raises `Jud (+24 more)

### Community 45 - "parse_epub"
Cohesion: 0.18
Nodes (19): Element, _check_not_zip_bomb(), _element_text(), _localname(), parse_epub(), EPUB format handler — see specs/formats.md.  Block granularity: each `h1`-`h6`,, Extract a `BookDoc` from an EPUB file., _build_epub_bytes() (+11 more)

### Community 46 - "ground_truth.py"
Cohesion: 0.09
Nodes (25): `/health` must not wait for an in-flight Ask's LLM call — that was the     compo, test_book_titles_for_boost_sqlite_and_failure(), test_build_default_deps_catalog_search_skips_shelf_on_list_failure(), test_ground_hits_for_ask_tolerates_lexical_failure(), test_health_returns_while_ask_llm_is_still_running(), Request, RuntimeError, build_inprocess_client() (+17 more)

### Community 47 - "test_rerank.py"
Cohesion: 0.12
Nodes (22): _call_llm(), _clean_questions(), _client(), _echoes_opening(), _is_self_referential(), main(), _model_name(), _normalize_words() (+14 more)

### Community 48 - "test_v2_routes.py"
Cohesion: 0.12
Nodes (23): _load_json_line(), make_block_id(), Compute a `Block.block_id`.      Stable across runs and processes: same `(book_i, Deserialize from `to_jsonl` output.          Raises `ValueError` naming the offe, test_parse_pdf_native_text_page_provenance_and_offsets(), _make_block(), _make_book_doc(), _make_provenance() (+15 more)

### Community 49 - "Handoff — Zoomcamp checklist + plan v2.1 verification"
Cohesion: 0.12
Nodes (28): Path, Path, _is_poem_byline(), _markdown_heading(), parse_txt(), _plaintext_heading(), TXT/Markdown format handler — see specs/formats.md.  Heading inference: a Markdo, True for short all-caps attributions that look like author bylines. (+20 more)

### Community 50 - "test_inprocess_bridge.py"
Cohesion: 0.09
Nodes (21): _base_deps(), _missing_block(), _missing_book_block(), Block, Behavioural tests for `apps/api` — see specs/api.md.  No live Postgres, no live, Regression: uncached Groq `/models` probes made solo `/health` 1.2-1.9s     and, SQLite creates the file on first connect, so a never-seeded clone has a     reac, Placeholder home for the drift-guard assertion — the real, spec-named     test l (+13 more)

### Community 51 - "Extension points"
Cohesion: 0.07
Nodes (29): Contract-drift guard, `DELETE /v1/playlists/current/items/{item_id}`, Endpoints — live v1 (OpenAPI snapshot), Error and degradation behavior, `GET /health`, `GET /v1/areas` / `POST /v1/areas`, `GET /v1/audio/capabilities`, `GET /v1/blocks/{id}` (+21 more)

### Community 52 - "sqlite_deps.py"
Cohesion: 0.13
Nodes (25): Namespace, Path, _judge_metrics(), load_questions(), _machine_snapshot(), main(), _mean(), _parse_args() (+17 more)

### Community 53 - "3. Proposed SQLite tables"
Cohesion: 0.18
Nodes (19): Exception, GroundTruthRow, One `question -> chunk_id` ground-truth pair., _answer_one(), AnsweredCase, One question answered under one prompt variant., Answer one question, retrying once, then recording the failure honestly.      `a, Answer every question in `questions` under `variant`'s system prompt.      Alway (+11 more)

### Community 54 - "parse_djvu"
Cohesion: 0.12
Nodes (39): Client, Path, MonkeyPatch, Path, fetch_one(), FetchOutcome, load_manifest(), main() (+31 more)

### Community 55 - "Data model and schemas"
Cohesion: 0.18
Nodes (10): A model swap does not fix it either (2026-08-31), ADR-003 — Answer prompt: keep the incumbent, on a null result, Baseline, Consequences, Context, Correction: these measurements are less stable than either of us claimed, Decision, The winner is flagged unproven, and that is the point (+2 more)

### Community 56 - "Decision log"
Cohesion: 0.09
Nodes (54): ApiClientError, ApiUnavailableError, Raised for a 4xx/5xx response from the API.      ``detail`` carries the API's er, Raised when the API cannot be reached at all (timeout/connection)., _cast_vote(), _enqueue_mentor_path(), _enqueue_roadmap_path(), main() (+46 more)

### Community 57 - "Local development"
Cohesion: 0.12
Nodes (17): _hit(), The `query_log` row for a cache hit has `cache_hit=True` — captured     via the, Audit S01: same question with different k must not reuse the cache., Audit S01: rewrite flag is part of cache identity even before rewrite runs., The `rerank` span wraps the real cross-encoder call inside the     production re, APP_MODE=demo: asking the SAME question twice calls the LLM once —     the secon, A pre-seeded cache entry for the exact key this request would compute     is ign, test_cache_hit_is_logged_and_flagged() (+9 more)

### Community 58 - "HomeLib v2 — reviewer handoff"
Cohesion: 0.07
Nodes (36): CrossEncoder, MonkeyPatch, _CountingFakeCrossEncoder, _CountingFakeEmbedder, _hit(), C9 speed confirmation: the embedder and cross-encoder load once per process — se, Two `_embed_query` calls construct the sentence embedder once; two     `rerank`, test_models_load_once_per_process() (+28 more)

### Community 59 - "Debugging and troubleshooting"
Cohesion: 0.14
Nodes (26): Any, Client, Path, _doc_to_entry(), fetch_catalog_entries(), _fetch_page(), main(), Open Library catalog fetcher — see specs/corpus.md.  Pulls curated subject slice (+18 more)

### Community 60 - "Retrieval pipeline"
Cohesion: 0.11
Nodes (18): 1. Sources examined, 2. Entities mined from the HTML, 3. Proposed SQLite tables, 4. HTML → table map, 5. Mockup-only entities (not in the HTML), 6. Contradictions (CONFUSION — do not silently pick), 7. WP02 red-test hooks, 8. Out of scope this PR / paid-tier must not be created this week (+10 more)

### Community 61 - "roadmap.py"
Cohesion: 0.11
Nodes (43): Any, Block, MonkeyPatch, Path, Connection, datetime, Path, demo_llm_daily_limit() (+35 more)

### Community 62 - "HomeLib — improved product and build plan v2"
Cohesion: 0.16
Nodes (14): _decode_djvu_string(), djvu_available(), _djvutxt_version(), _extract_page_texts(), _first_quoted_string(), _iter_top_level_forms(), DJVU format handler — see specs/formats.md.  Extracts the hidden text layer via, Yield each top-level parenthesized S-expression in `text`, in order. (+6 more)

### Community 63 - "SyncASGITransport"
Cohesion: 0.09
Nodes (39): Any, Connection, Namespace, Path, Retriever, ArmMetrics, _connect(), _coverage_lines() (+31 more)

### Community 64 - "12.3 Work packages"
Cohesion: 0.09
Nodes (37): Connection, Connection, Path, Edition / runtime flags from the environment.  `APP_MODE` and timeout defaults., read_app_mode(), read_llm_max_output_tokens(), read_llm_timeout_seconds(), APP_MODE / demo-timeout config skeleton (WP00).  Behaviour: the process can read (+29 more)

### Community 65 - "homelib — submission checklist"
Cohesion: 0.06
Nodes (68): Connection, Embedder, float64, Namespace, NDArray, Path, ndarray, Path (+60 more)

### Community 66 - "Stakeholder picky review + wiki/mermaid handoff — 2026-09-05"
Cohesion: 0.13
Nodes (14): Assessment, Cache, sessions and reader continuity, Current cohort features versus HomeLib, Evaluation and answer reliability, HomeLib — detailed issues and Zoomcamp 2026 alignment, Issues and closure criteria, Learning and discovery workflows, Recommended implementation order (+6 more)

### Community 67 - "HomeLib v2.1 — final merged execution plan (capstone rebuild + product)"
Cohesion: 0.09
Nodes (39): cache_key(), lookup(), _normalize_question(), AskResponse, Connection, Demo-only answer cache — C4b (specs/monitoring.md "Demo answer cache").  Read-th, Whitespace-collapsed, case-folded — "Does it Jump?" and "does it     jump?  " mu, `None` on a miss. Raises on a genuinely broken store (bad JSON, no     `answer_c (+31 more)

### Community 68 - "Architecture overview"
Cohesion: 0.13
Nodes (15): API endpoint map, Catalog and rights, Core entities, Corpus (ported from v1), Data model and schemas, Entity relationship diagram, Identity, Index and embedding revision (+7 more)

### Community 69 - "prompt_hash"
Cohesion: 0.13
Nodes (15): Answer prompt and rewrite (supplementary), Chunk ID stability for eval ground truth, Decision log, HomelibClient: InProcess vs Http, Hybrid search: BM25/FTS5 + vector + RRF vs alternatives, Ingest: dlt ELT shape, staging → canonical, idempotency, Licence — owner decision, recorded not fixed, Observability: Observatory vs Grafana (+7 more)

### Community 70 - "QueryOutcome"
Cohesion: 0.17
Nodes (20): Connection, Connection, Path, judge_recent_rows(), JudgedRow, Online judge on live traffic — core logic behind `scripts/judge_recent.py`.  C6, One row this run actually scored and wrote back., Judge up to `n` of the most recent unjudged, answer-logged rows.      `client` i (+12 more)

### Community 71 - "test_index_sqlite_dispatch.py"
Cohesion: 0.25
Nodes (29): get_deps(), FastAPI dependency. `apps/api/tests/test_api.py` overrides this     wholesale vi, AddPlaylistItemRequest, AudioCapabilities, OkResponse, PatchPlaylistItem, PatchPlaylistItemsRequest, PlaylistAcceptRequest (+21 more)

### Community 72 - "5. Signature product experience"
Cohesion: 0.13
Nodes (14): Coverage floor (90%), Data / ingest, Debugging and troubleshooting, dlt / SQLite connection hygiene, Eval regression gate, Forgejo CI lanes, Getting help from logs, Infrastructure (+6 more)

### Community 73 - "test_cloud_files.py"
Cohesion: 0.14
Nodes (14): Arm 1: Lexical (FTS5 / BM25), Arm 2: Vector (semantic), Degradation matrix, `degraded` flags contract, Evaluation, `Hit` shape (shared contract), Pipeline overview, Related pages (+6 more)

### Community 74 - "ADR-002 — Catalog source: Open Library, and three rejections"
Cohesion: 0.13
Nodes (14): 0. Executive decision, 10. Security, privacy and reliability, 11. Capstone rubric plan, 13. Cut order, 16. Final definition of done, 17. Authoritative implementation references, 1. Product problem, 2.1 Primary users (+6 more)

### Community 75 - "ADR-003 — Answer prompt: keep the incumbent, on a null result"
Cohesion: 0.15
Nodes (12): 0. Review verdict on the consolidated plan (adopted, with these corrections), 1. Owner actions (Pavlo) — GitHub + Streamlit at the VERY END (owner decision 2026-09-01), 2. Safety track (unchanged, binding), 3. Executor operating rules (binding, restored from v1), 4. What v2 ports from verified v1 (do not rewrite the database-agnostic 60%), 5. Work packages = product doc §12.3 (WP00–WP11), with these verification teeth added, 6. Rubric target (product doc §11): 21 core + 2 cloud = 23 before discretionary extras + 9 peer reviews. Never trade a scored criterion for polish. Cut order and never-cut list: product doc §13, with the correction that the HTML prototype is first to cut., 7. Restored guards (apply exactly as v1) (+4 more)

### Community 76 - "test_mentor.py"
Cohesion: 0.15
Nodes (13): 12.3 Work packages, WP00 — Freeze, fallback and canary, WP01 — Contracts and acceptance tests, WP02 — SQLite and principals, WP03 — Ingestion and rights, WP04 — Retrieval and evaluation, WP05 — Lawful connectors, WP06 — Mentor and artifacts (+5 more)

### Community 77 - "homelib"
Cohesion: 0.10
Nodes (24): Connection, Path, Connection, ReadableSpan, SpanExporter, SpanExportResult, TracerProvider, _db() (+16 more)

### Community 78 - "test_coffee_table.py"
Cohesion: 0.19
Nodes (11): _ground_hits_for_ask(), Merge lexical candidates, promote overlap, boost named shelf titles.      Scene, _content_tokens(), merge_unique_hits(), promote_query_overlap(), promote_verbatim_phrase(), Reciprocal Rank Fusion over the lexical and vector search arms — see specs/hybri, Keep exact body matches ahead of semantic/reranker approximations. (+3 more)

### Community 79 - "test_app_doors.py"
Cohesion: 0.17
Nodes (12): 5.10 Book-to-audio and Memory Sphere, 5.11 Forbidden Stacks, 5.1 Information architecture, 5.2 Library Crossroads and rotating room, 5.3 Explore flow, 5.4 Wing and shelf screen, 5.5 Mentor Journal, 5.6 Coffee Table (+4 more)

### Community 80 - "Submission runbook — LLM Zoomcamp 2026"
Cohesion: 0.18
Nodes (10): 1. Kaggle "15K+ Books Across 100+ Categories" — banned in any form, 2. Google Books API directly — unusable, 3. UCSD Goodreads Book Graph — unusable, ADR-002 — Catalog source: Open Library, and three rejections, Consequences, Context, Decision, Notes on sourcing (+2 more)

### Community 81 - "test_openapi_snapshot.py"
Cohesion: 0.13
Nodes (23): Any, Block, BookSummary, Connection, Path, _block_from_row(), open_store(), SQLite-backed helpers for FastAPI when HOMELIB_SQLITE_PATH is set (P0 wire). (+15 more)

### Community 82 - "cold_clone_drill.sh"
Cohesion: 0.10
Nodes (34): BookSummary, Citation, RoadmapStep, Inventory questions often get answer=\"\" — that must not render blank., Server forgot the session (TTL sweep): the client remints on the 401,     the fr, _SessionFake, test_ask_answer_body_refuses_when_llm_returns_empty(), test_ensure_demo_session_is_a_noop_that_clears_in_selfhosted() (+26 more)

### Community 83 - "test_repo_hygiene.py"
Cohesion: 0.12
Nodes (26): blocks_resource(), catalog_resource(), chunk_embeddings_resource(), chunks_resource(), _embed_batch(), embed_texts(), _ensure_ivfflat_index(), _get_model() (+18 more)

### Community 84 - "ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off"
Cohesion: 0.20
Nodes (7): Streamlit Community Cloud edition: the files Cloud reads and the seed it needs., `streamlit_app.py` is a shim over `apps/ui/app.py`, not a second UI., Cloud resolves from uv.lock; GPU torch wheels would blow its disk/RSS., `.python-version` (uv, pyenv, Cloud reviewers) agrees with pyproject., test_cloud_entrypoint_runs_the_same_ui_main(), test_python_version_file_matches_requires_python(), test_uv_lock_pins_cpu_torch_index()

### Community 85 - "Decision"
Cohesion: 0.08
Nodes (36): AskResponse, HomelibClient, HttpClient, HTTP client for the homelib public API.  This is the ONLY module under ``apps/ui, Selfhosted edition — FastAPI over HTTP with per-call timeouts., TokenUsage, MonkeyPatch, client() (+28 more)

### Community 86 - "Repo structure"
Cohesion: 0.12
Nodes (23): Any, MonkeyPatch, Behavioural tests for `homelib_rag.answer` — see specs/answer.md.  No live Postg, The prompt sent to the LLM must carry the book's authors, not just its     title, `_TIMEOUT_SECONDS` (module constant) is read from `LLM_TIMEOUT_SECONDS`     at i, Bounds worst-case CPU generation time — a runaway completion should     not turn, LIVE: Groq quoted the prompt header; trust only the same author in body text., A blank `LLM_API_KEY` (empty Cloud secret) must construct like an absent     one (+15 more)

### Community 87 - "write_ground_truth"
Cohesion: 0.10
Nodes (26): build_rotunda_html(), _json_for_script(), The Crossroads rotunda — the rotating room of doors (specs/rotunda.md).  Pure mo, JSON that is safe inside an inline `<script>`.      Every `<` becomes the JSON e, Return the rotunda fragment that `app.py` renders with `st.html`.      `active`, Rotunda: pure-string behaviour of the rotating room (specs/rotunda.md).  No scre, Streamlit renders the fragment through DOMPurify with SAFE_FOR_XML, which     re, Mockup language (gold bloom, teal seal, motes) must stay inside #hl-rotunda (+18 more)

### Community 88 - "spec: answer — `homelib_rag.answer`"
Cohesion: 0.20
Nodes (9): ADR-010 — Single repo until public; paid tier after, Consequences, Context, Decision, Obsidian (post-public-publish, contract-first — product §15), Post-public-publish / paid tier (same Forgejo repo later — not another git remote), Product ladder, Public app this week (+1 more)

### Community 89 - "spec: audio — capabilities and one lawful preview"
Cohesion: 0.09
Nodes (31): Exception, answer(), is_passage_abstention(), True when ``answer`` is an honest refusal rather than a factual claim., Synthesize an `AskResponse` for `question` from already-retrieved `hits`.      N, For each citation in a non-degraded response, `quote` is a substring     of the, The client raises a connection error; `answer()` returns a degraded     `AskResp, A citation to a source absent from `hits` never reaches the caller as     trustw (+23 more)

### Community 90 - "spec: chunking — `homelib_core.chunk`"
Cohesion: 0.11
Nodes (16): Apps, Branch model, Docker and CI, Documentation map, Packages, Related pages, Repo structure, Specs vs code vs tests vs data (+8 more)

### Community 91 - "spec: connectors — lawful catalog federation (“Forbidden Stacks”)"
Cohesion: 0.10
Nodes (17): MonkeyPatch, Crossroads doors rendered through Streamlit's own test harness.  `streamlit.test, The rotunda and the door heading must agree. 'Roadmap (v1)' leaked an     intern, `?projection=1` must open projector mode exactly once. Regression for the     tr, `?source=` must be consumed into session state once, not re-added on     every r, The Projection ordinal must be keyed per book, not global (BUG 2): a     stale g, Cloud/local deploy proof: Crossroads caption names the running revision., LIVE: Projection briefly kept Observatory/Ask controls until another rerun. (+9 more)

### Community 92 - "spec: core-models — `homelib_core.models`"
Cohesion: 0.50
Nodes (4): parse_file(), Format dispatcher — see specs/formats.md.  `parse_file` is the single entry poin, Derive a `book_id` slug from a file stem (e.g. `"Moby Dick!" -> "moby-dick"`)., _slugify()

### Community 93 - "spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`"
Cohesion: 0.15
Nodes (12): Data, Development, Evaluation results, homelib, License, Monitoring, Quickstart — Docker Compose, Rubric self-audit (+4 more)

### Community 94 - "spec: ui — `apps/ui` (Streamlit Crossroads)"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: answer — `homelib_rag.answer`, Store dispatch (2026-09-05), Verify

### Community 95 - "User flows"
Cohesion: 0.21
Nodes (22): _book_rights(), _canonical_text(), _chapter_section(), _chunk_in_chapter(), _context_window(), _dedupe_hits_by_block_id(), _exact_hits(), _filter_hits_to_scope() (+14 more)

### Community 96 - "_is_substantial"
Cohesion: 0.09
Nodes (28): Block, Connection, _block_from_pg_row(), _connect(), _dsn(), get_block(), get_book_block(), Explicit function-calling agent loop — see specs/agent-tools.md.  A hand-rolled (+20 more)

### Community 97 - "Per-book breakdown"
Cohesion: 0.25
Nodes (9): _make_step(), RoadmapStep, test_resolve_prerequisite_titles_uses_titles_not_integers(), test_roadmap_steps_render_in_order(), RoadmapStep, Roadmap steps sorted by their declared ``order``., Map each step's ``order`` to the titles of its prerequisite steps., resolve_prerequisite_titles() (+1 more)

### Community 98 - "parse_file"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error behavior, Invariants, Named red tests (write before the code), Public interface, Purpose, spec: core-models — `homelib_core.models`, Verify

### Community 99 - "sqlite_only_smoke.sh"
Cohesion: 0.22
Nodes (8): Banned sources (binding), Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`, Verify

### Community 100 - "spec: agent-tools — `homelib_rag.agent`"
Cohesion: 0.17
Nodes (9): Chunking experiment, Agent — hand-rolled loop, not LangGraph, Chunking — 1200/200 vs 600 vs 2000, Dual corpus — shelf full-text vs catalog metadata, Embedder — open MiniLM vs paid, Hybrid vs hybrid_rerank, Ingest — dlt, not Kestra, Query rewrite — OFF (+1 more)

### Community 101 - "spec: coffee-table — persistent playlist (product §5.6)"
Cohesion: 0.33
Nodes (5): Addendum 2026-09-05 — what is true on the tip path, ADR-005 — Observatory replaces Grafana, Consequences, Context, Decision

### Community 102 - "spec: eval-gate — `evals/gate.py`"
Cohesion: 0.25
Nodes (8): Coffee Table playlist (spec-level), Cold start / demo session, Demo reset, Ingest pipeline run, Related pages, Scene anchor open, Search → cited answer, User flows

### Community 103 - "spec: evals-llm — `evals/llm_eval.py` + `evals/judge.py`"
Cohesion: 0.17
Nodes (6): _FakeConnection, _FakeCursor, Seed the fixture book/blocks/chunks/embeddings using the SAME embedder     `sear, Records every `execute()` call; replays one queued `fetchall()` result     per c, _seed(), _test_db_dsn()

### Community 104 - "spec: evals-retrieval — `evals/ground_truth.py` + `evals/retrieval_eval.py`"
Cohesion: 0.14
Nodes (36): Any, Connection, DltResource, LoadInfo, Path, Pipeline, _book_id_in_clause(), _default_db_path() (+28 more)

### Community 105 - "spec: formats — `homelib_core.formats` + `homelib_core.normalize`"
Cohesion: 0.10
Nodes (20): get_trace(), C5 (specs/monitoring.md "Tracing"): the span tree for one `/v1/ask`     request', Tracer, _demo_principal_id(), enforce_demo_llm_quota(), HTTP gate for the shared Cloud demo's per-principal daily LLM cap., Resolve the demo principal, or None when the cap does not apply.      Missing /, 401 on a demo host when the visitor has no valid session (cache hits too). (+12 more)

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
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: ingestion — `apps/ingest/pipeline.py` (dlt), SQLite seed CLI (2026-09-05), Verify

### Community 112 - "spec: rerank — `homelib_rag.rerank`"
Cohesion: 0.15
Nodes (19): _fuse_hits(), _hit(), Full-text search over the ingested book shelf (RRF hybrid search)., search_shelf(), test_search_shelf_delegates_to_hybrid_search(), Hit, Shared retrieval hit model — see specs/indexing.md.  `Hit` is defined once, here, _default_retrieve() (+11 more)

### Community 113 - "spec: rewrite — `homelib_rag.rewrite`"
Cohesion: 0.25
Nodes (8): 7.1 One service layer, two clients, 7.2 Provider contract, 7.3 Other interchangeability seams, 7.4 SQLite, 7.5 Embeddings, 7.6 Ingestion, 7.7 RAG and agent flow, 7. Technical architecture

### Community 114 - "spec: roadmap — `homelib_rag.roadmap`"
Cohesion: 0.22
Nodes (9): Agent (Mentor only), Citation precision (N=1 live smoke, 2026-09-07, Groq `openai/gpt-oss-20b`), Error taxonomy (one example each), Eval gate, EVAL.md — Track E interview artifact, Generation, Golden set honesty, Prompt-injection probes (3) (+1 more)

### Community 115 - "spec: rotunda — Library Crossroads doors (product §5.2)"
Cohesion: 0.12
Nodes (23): _FakeCursor, _patch_connect(), MonkeyPatch, `/health` reports booleans only about the LLM — no substring of the     configur, LIVE: Ask abstained while Shelf scene search opened the woods passage., Scripted cursor for exercising `main._connect()` production helpers., test_book_titles_for_boost_uses_default_list_books(), test_build_default_deps_catalog_search_merges_shelf() (+15 more)

### Community 116 - "spec: scene-search — within-book exact/keyword/semantic/smart/ask"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: provider — `LLMProvider` seam, Verify

### Community 117 - "CLAUDE.md — HomeLib"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: rerank — `homelib_rag.rerank`, Verify

### Community 118 - "rerank.py"
Cohesion: 0.13
Nodes (34): MonkeyPatch, Path, _install_fake_baseline(), _no_db(), Tests for evals/judge.py and evals/llm_eval.py — see specs/evals-llm.md.  Nothin, A variant that drops the JSON/verbatim-quote instructions would score     0 for, Budget is a parameter with a documented default, not a magic number., Repo convention: every Pydantic model tolerates unexpected keys. (+26 more)

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
Cohesion: 0.16
Nodes (11): _clear_overrides(), Any, Every test gets a fresh tracer provider, built lazily on next     `get_tracer()`, P0 Cloud bug: inventory Q cached as passage refuse under arm=hybrid must     not, `HOMELIB_LOG_ANSWERS` unset (the default): a real /v1/ask call, with a     real, `HOMELIB_LOG_ANSWERS=1` plus a real SQLite store: the question and     answer AR, _reset_tracer(), test_answer_log_off_by_default() (+3 more)

### Community 123 - "spec: observatory — in-app monitoring (replaces Grafana)"
Cohesion: 0.12
Nodes (15): Guards on the gates themselves.  A config file that looks like a guarantee but i, A branch push plus an open PR must not fire two runs of the same commit.      Wi, An unpinned context window fails silently, which is the worst kind.      Ollama, UI image only COPY'd apps/ + packages/; theme must be copied explicitly.      St, Coffee Table / playlists 503 when the API container lacks the SQLite path., The UI process renders READ_PORT into link text and gates the Official     viewe, Hostexecutor lane TMPDIR is shared and can vanish mid-job.      PR #18 run 87 fa, Hygiene (string-match): the freshness short-circuit must not fire on an     untr (+7 more)

### Community 124 - "spec: principals — demo sessions and local-user identity"
Cohesion: 0.25
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
Cohesion: 0.28
Nodes (9): One `rrf_k` value's metrics from the hybrid arm — see `run_rrf_k_sweep`., Replace the section starting at `heading` (up to the next `## `     heading or E, Upsert the "RRF k sweep" table into `path`, leaving the rest of the     report (, _replace_or_append_section(), RrfSweepPoint, write_rrf_k_sweep_section(), _sweep_points(), test_write_rrf_k_sweep_section_refuses_empty_points() (+1 more)

### Community 134 - "ADR-005 — Observatory replaces Grafana"
Cohesion: 0.21
Nodes (12): Path, _graph_refresh_script(), Homelib refreshes on the pushed protected ref — main, and only main.      The re, Execute the graph-refresh step script in a scratch repo with a stub graphify., Behavioural: a push to main rebuilds, commits and pushes the graph.      Until 2, Behavioural: the committed graph never carries the runner's workdir.      graphi, Behavioural: a push to a recreated `v2` neither rebuilds nor pushes.      A seco, _run_graph_refresh() (+4 more)

### Community 135 - "ADR-007 — Licence (provisional)"
Cohesion: 0.33
Nodes (5): Packaging invariants.  These are cheap to assert and expensive to discover later, PEP 561: without this file, installed type hints are invisible to mypy.      hom, The documented surface must be importable from the package root., test_package_ships_py_typed_marker(), test_public_names_are_exported()

### Community 136 - "ADR-009 — Audio deferred"
Cohesion: 0.26
Nodes (13): MonkeyPatch, Path, Direct unit tests for `apps.api.sqlite_deps.sqlite_get_book_block`.  Companion t, Migrate `db` (idempotent) and insert `book_id` with one block per text,     dens, Unknown book, and ordinal past the last block, both miss.      The function's ow, Regression: migrate-on-every-open held SQLite locks under Ask and made     `/hea, _seed_book_blocks(), sqlite_env() (+5 more)

### Community 137 - "Design — how the magic-library look reaches the product"
Cohesion: 0.33
Nodes (6): 14. Acceptance journeys, Journey A — public reviewer, Journey B — manual playlist, Journey C — scene search, Journey D — home projector, Journey E — degraded operation

### Community 138 - "_compose"
Cohesion: 0.33
Nodes (6): 15. Post-capstone roadmap, Obsidian integration design, Phase 1 — home product hardening, Phase 2 — persistent cloud trial, Phase 3 — native Apple companion, Phase 4 — richer lawful federation

### Community 139 - "_gate_steps"
Cohesion: 0.14
Nodes (14): BookMetrics, _per_book(), QueryOutcome, What one arm actually returned for one ground-truth question., True when the arm that ran is not the arm that was asked for., One book's slice of an arm's score., Run one query through one arm, recording what actually happened.      A retrieva, hit-rate@k and MRR@k over `outcomes`, via `evals.metrics`.      Both mappings ar (+6 more)

### Community 140 - "ADR-004 — SQLite replaces Postgres"
Cohesion: 0.14
Nodes (14): 1. Project intent, 2. Architecture & schema (v2 — on `main` since the 2026-09-06 collapse), 3. How to run locally, 4. Plan 2.1 / Zoomcamp checklist matrix, 5. Wiki map, 6. What to verify in review, 7. Known gaps / improvements (priority), 8. Current git state (+6 more)

### Community 141 - "ADR-006 — Editions and hosting"
Cohesion: 0.50
Nodes (4): _book_metadata(), _dsn(), `book_id -> (title, authors)` for every id in `book_ids`.      Test seam: monkey, test_book_metadata_empty_list_returns_empty_dict()

### Community 142 - "ADR-008 — Rights gate (unknown fails closed)"
Cohesion: 0.60
Nodes (4): main(), _parse_args(), _print_result(), Demo CLI: `POST /v1/ask` against a running homelib API — see specs/api.md.  Usag

### Community 143 - "Crossroads and doors"
Cohesion: 0.60
Nodes (4): main(), _parse_args(), _print_result(), Demo CLI: `POST /v1/roadmap` against a running homelib API — see specs/api.md.

### Community 144 - "HomeLib v2 — Developer Wiki"
Cohesion: 0.22
Nodes (7): Any, _normalize_openapi(), Contract-drift guard — see specs/api.md.  Asserts the generated OpenAPI schema (, Reduce a full OpenAPI document to the slice specs/api.md's     contract-drift gu, A cheap independent check that the snapshot itself is not stale: every     endpo, test_openapi_snapshot_matches(), test_snapshot_covers_every_endpoint_in_api_md()

### Community 145 - "12. Delivery plan"
Cohesion: 0.42
Nodes (10): _db(), Path, WP07 Coffee Table + progress named red tests — specs/coffee-table.md., test_acceptance_required_before_queued(), test_independent_read_listen_progress(), test_manual_survives_regeneration(), test_no_silent_reinsert_of_completed_or_removed(), test_remove_keeps_resource() (+2 more)

### Community 146 - "6. Data and rights model"
Cohesion: 0.16
Nodes (14): MonkeyPatch, Mentor door tool-use caption — `streamlit.testing.v1.AppTest`, same harness as `, A complete intake is the Mentor door's whole product: area, wing,     proposed p, Preset chips seed a path locally — no mentor_intake call required., A Mentor response whose `tool_calls` is non-empty renders a caption     naming t, An empty `tool_calls` (e.g. abstention, or an LLM-unreachable degrade)     rende, Blank Goal + Propose path must not silently no-op.      BrokenMentor.har showed, _seeded_mentor_response() (+6 more)

### Community 147 - "9. Evaluation and monitoring"
Cohesion: 0.12
Nodes (16): APP_MODE behaviour, Canonical commands, Common debug commands, Compose profiles, Demo smoke (Sep 2 gate per evidence addendum), Environment, First-time setup, iPad / AirPlay / Speak Screen (+8 more)

### Community 148 - "_all_job_commands"
Cohesion: 0.13
Nodes (15): _llm_json(), A fabricated quote not present in the cited chunk's text causes a     degraded f, Groq `json_validate_failed` must not stick on the first attempt when a     plain, The guard rail must not have been loosened into uselessness.      Whitespace-ins, Ungrounded claim + empty citations must degrade — never silent accept., Valid JSON with no answer is still an unusable generation, not success., Every Citation.chunk_id in a non-degraded response corresponds to one     of the, test_a_paraphrase_is_still_rejected_after_whitespace_normalisation() (+7 more)

### Community 149 - "pre-push"
Cohesion: 0.17
Nodes (11): Cost estimate (C1), Data contracts (field-level), Demo answer cache (C4b), Error/degradation behavior, Named red tests (write before the code), Online judge (C6), Public interface, Purpose (+3 more)

### Community 150 - "homelib"
Cohesion: 1.00
Nodes (3): homelib, homelib-core, homelib-rag

### Community 151 - "__init__.py"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: progress — reading and listening positions, Verify

### Community 152 - "__init__.py"
Cohesion: 0.33
Nodes (8): MonkeyPatch, _demo_http_client(), Shelf scene hits must offer an in-UI open-passage control in demo mode.  Cloud d, Two hits sharing open_anchor must not raise StreamlitDuplicateElementKey., _stub_shelf_apis(), test_demo_shelf_scene_hit_offers_open_this_passage(), test_shelf_scene_duplicate_open_anchor_uses_distinct_widget_keys(), _walden_block()

### Community 153 - "__init__.py"
Cohesion: 0.17
Nodes (12): Architecture overview, Edition topology (who talks to what), Editions at a glance, High-level system diagram, Home topology (self-hosted), Ingestion, LLM ([`specs/provider.md`](../../specs/provider.md)), Related pages (+4 more)

### Community 154 - "__init__.py"
Cohesion: 0.17
Nodes (12): Degradation tests, Documentation improvements, Eval before default changes, Import boundaries, Improving the system, One-test-per-finding, Performance improvement ideas (recorded headroom), Related pages (+4 more)

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

### Community 159 - "README.md"
Cohesion: 0.14
Nodes (13): 10. Provenance and rights contract, 11. Numbers, 12. Models and providers, 1. What this project is built on, 2. At a glance, 3. The Shelf: Project Gutenberg, 4. The Catalog: Open Library Search API, 5. Banned sources and why (+5 more)

### Community 161 - "llm_eval.md"
Cohesion: 0.32
Nodes (7): _call_llm(), _client(), _model_name(), LLM query rewriter — see specs/rewrite.md.  Asks an LLM to turn a user's natural, Internal typed shape the LLM is asked to produce.      Not exposed publicly — `r, Call the configured LLM and return its raw response content.      Raises on any, RewriteResult

### Community 162 - "_default_retrieve"
Cohesion: 0.24
Nodes (8): API_PORT, fail(), GRAFANA_PORT, OLLAMA_PORT, POSTGRES_PORT, cold_clone_drill.sh script, step(), UI_PORT

### Community 171 - "test_ui_dockerfile_pins_pythonpath_so_apps_imports_resolve"
Cohesion: 0.27
Nodes (4): Crossroads and doors, Door map, How a door opens, Monitoring and feedback

### Community 172 - "test_streamlit_theme_pins_parchment_gold_from_mockups"
Cohesion: 0.03
Nodes (86): _imported_modules(), _make_book(), BookSummary, Behavioural tests for apps/ui/view_model.py.  These drive the pure helper functi, Named red from specs/client.md — alias of the AST walk above., Crossroads → Ask (Wing) → Mentor → Roadmap → Coffee Table → Projection., The door grid and the dispatch table are the same set — no unreachable     rende, Ask refuse / Mentor abstain must surface provider URLs, not blank. (+78 more)

### Community 175 - "test_ci_pytest_forces_workspace_basetemp"
Cohesion: 0.16
Nodes (14): Raise `CitationValidationError` unless every citation is genuine.      Two check, _validate_citations(), _hit(), Groq has returned `citations: [1]` — keep the answer when objects remain., The model picks a passage; the code supplies the id.      Asking a 7B model to e, A number nobody offered, quoting text nobody showed, is a fabrication., The model is good at copying text and bad at bookkeeping.      Observed live: as, test_a_quote_from_a_different_passage_is_reattributed_not_discarded() (+6 more)

### Community 177 - "test_gitleaks_allowlists_never_exempt_whole_files"
Cohesion: 0.33
Nodes (6): FIXES gap LLM Zoomcamp 2026, HomeLib vs LLM Zoomcamp 2026 — coverage gap report, Part 1 — What the 2026 cohort teaches and where HomeLib shows it, Part 3 — Corrections to `docs/course-map.md`, Table 1 — Module → techniques taught → homework asks, Table 2 — Course topic → module → HomeLib status

### Community 178 - "test_drill_asserts_seed_counts_via_health"
Cohesion: 0.24
Nodes (9): Path, Guards on the public snapshot itself.  This repo is developed on a private Forge, The final review found mutually contradictory pending/live Cloud claims., No tracked, reviewer-facing doc may name the private Forgejo host,     its SSH p, `docs/handoffs/` becomes untracked in this same PR, so no tracked doc     may st, test_no_tracked_doc_links_to_handoffs(), test_public_docs_have_no_internal_hosts(), test_submission_docs_name_the_live_demo_without_old_cloud_placeholders() (+1 more)

### Community 179 - "test_drill_verifies_monitoring_via_observatory_not_grafana_panel_count"
Cohesion: 0.17
Nodes (10): Level, RoadmapResponse, build_roadmap(), Agent-tool wrapper over `homelib_rag.roadmap.build_roadmap`, with the     defaul, An `OpenAICompatibleClient` that substitutes the system prompt.      `answer()`, _VariantClient, default_llm_client(), OpenAIClient (+2 more)

### Community 180 - "test_specs_ui_door_list_matches_crossroads_doors"
Cohesion: 0.20
Nodes (9): ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off, Consequences, Context, Decision, Evidence, Query rewrite: measured, and rejected, v2 SQLite re-measurement (2026-09-03), Verification (+1 more)

### Community 181 - "test_no_dotenv_file_is_tracked"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error/degradation behavior, Live provider notes, Named red tests, Public interface, Purpose, spec: connectors — lawful catalog federation (“Forbidden Stacks”), Verify

### Community 182 - "test_ci_graph_guard_job_exists"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error/degradation behavior, Named tests (all present), Public interface, Purpose, spec: ui — `apps/ui` (Streamlit Crossroads), The doors, Verify

### Community 183 - "test_ci_graph_refresh_pushes_to_current_protected_branch"
Cohesion: 0.20
Nodes (9): Binding invariants, Chunking experiment (2026-09-06), Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: chunking — `homelib_core.chunk` (+1 more)

### Community 184 - "test_ci_graph_refresh_commits_the_bootstrap_graph"
Cohesion: 0.25
Nodes (7): APP_MODE, HOMELIB_SQLITE_PATH, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT_SECONDS, sqlite_only_smoke.sh script

### Community 185 - "test_graphifyignore_excludes_generated_and_data_paths"
Cohesion: 0.29
Nodes (7): _compose(), `.env.example` ships `APP_MODE=demo` for the Community Cloud path. The     api s, A blank `.env` `LLM_API_KEY=` used to become `ollama` via `:-ollama`,     which, Hygiene (string/structure match, not behavioural). The api service reads     `/d, test_compose_api_passes_groq_and_does_not_coerce_blank_llm_key_to_ollama(), test_compose_api_pins_selfhosted_like_ui(), test_compose_ingest_can_write_sqlite_seed()

### Community 186 - "test_just_ci_includes_the_secret_scan"
Cohesion: 0.22
Nodes (8): Arm actually used, `hybrid`, `hybrid_rerank`, `lexical`, Per-book breakdown, Retrieval arm eval, RRF k sweep, `vector`

### Community 187 - "__init__.py"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error/degradation behavior, Named red tests, On-device Listen in Projection (iPadOS), Public interface, Purpose, spec: audio — capabilities and one lawful preview, Verify

### Community 188 - "__init__.py"
Cohesion: 0.67
Nodes (3): Partition `rows` into (scoreable, drifted) against the live index.      A row wh, split_on_index(), test_ground_truth_row_chunk_id_exists_in_fixture_index()

### Community 189 - "__init__.py"
Cohesion: 0.40
Nodes (5): _gate_steps(), The scan is a CI step, not just a file sitting in the repo., PR scans must not hang on full history; checkout stays deep for main.      Quick, test_ci_gitleaks_scopes_pr_history_but_keeps_full_checkout(), test_gitleaks_runs_in_ci()

### Community 190 - "__init__.py"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: agent-tools — `homelib_rag.agent`, Verify

### Community 191 - "test_specs_ui_door_list_matches_crossroads_doors"
Cohesion: 0.50
Nodes (4): _all_job_commands(), Every `run:` command in the workflow, keyed by job name., Whatever the hook defers must actually be enforced somewhere.      The fast loca, test_some_ci_job_runs_the_full_suite_the_hook_skips()

### Community 193 - "test_ci_graph_guard_job_exists"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: projection — projector reading mode (product §5.9), Verify

### Community 194 - "Path"
Cohesion: 0.33
Nodes (5): Cloud runtime (showcase URL), If something is red at the deadline, Open it as a stranger, Submission — LLM Zoomcamp 2026, What is submitted

### Community 195 - "demo_traffic.py"
Cohesion: 0.25
Nodes (7): Guards on the licence swap itself (ADR-007).  The repo used to ship an unfilled, LICENSE must be the PolyForm Noncommercial 1.0.0 text, not Apache., LICENSE-docs.md must exist and declare CC BY-NC-SA 4.0., Every pyproject.toml must declare PolyForm-Noncommercial-1.0.0.      None of the, test_docs_licence_is_cc_by_nc_sa(), test_license_is_polyform_noncommercial(), test_no_pyproject_declares_apache()

### Community 202 - "Connection"
Cohesion: 0.24
Nodes (11): _degraded_reason_code(), _degraded_response(), _is_json_validate_failure(), _is_rate_limit_failure(), _is_uncited_failure(), Groq JSON mode sometimes 400s with `json_validate_failed` and an empty     `fail, Stable short code for UI / Observatory — not the verbose log line., A client exception is not the same as the model being unreachable. (+3 more)

### Community 204 - "SentenceTransformer"
Cohesion: 0.29
Nodes (6): AGENTS.md — HomeLib, Module map, Read-first order (token discipline), Skill routing, Standing rules, What this is

### Community 221 - "Extension points"
Cohesion: 0.29
Nodes (7): Editions and entitlements, Extension points, New API routes (v2 §8), New corpus connectors, New document formats, New retrieval arms or fusion, Post-publish commercial tier

### Community 222 - "ADR-006 — Editions and hosting"
Cohesion: 0.40
Nodes (4): ADR-006 — Editions and hosting, Consequences, Context, Decision

### Community 223 - "Path"
Cohesion: 0.29
Nodes (6): CLAUDE.md — HomeLib, Module map, Read-first order (token discipline), Skill routing, Standing rules, What this is

### Community 230 - "ADR-009 — Audio deferred"
Cohesion: 0.40
Nodes (4): ADR-009 — Audio deferred, Consequences, Context, Decision

### Community 234 - "ADR-008 — Rights gate (unknown fails closed)"
Cohesion: 0.50
Nodes (4): ADR-008 — Rights gate (unknown fails closed), Consequences, Context, Decision

### Community 239 - "HomeLib v2 — Developer Wiki"
Cohesion: 0.18
Nodes (8): Course-module map, How we run each piece, Build evidence log, Plan addendum — post-merge corrections (2026-09-01), HomeLib v2 — Developer Wiki, Implementation status (v2 branch stack), Pages, Quick links

### Community 259 - "Path"
Cohesion: 0.43
Nodes (5): _doc(), docs/data-sources.md must agree with the pinned artefacts it describes., test_data_sources_doc_cites_only_existing_paths(), test_data_sources_doc_matches_manifest_and_catalog(), test_data_sources_doc_names_the_dataset_and_the_api()

### Community 261 - "test_gap_report.py"
Cohesion: 0.33
Nodes (6): _fixes_items(), The 2026 gap report is a promise list: every numbered item in its "FIXES gap LLM, Behavioural: no numbered FIXES item may still carry a `**TODO**`; each     must, The report is only useful if a reviewer can find it from the two     documents t, test_gap_report_is_linked_from_readme_and_course_map(), test_gap_report_items_are_all_resolved()

### Community 263 - "ADR-007 — Licence (provisional)"
Cohesion: 0.40
Nodes (4): ADR-007 — Licence (provisional), Consequences, Context, Decision

### Community 264 - "Design — how the magic-library look reaches the product"
Cohesion: 0.40
Nodes (4): Design — how the magic-library look reaches the product, Path from mockup to screen, Skills and gates, What is not built, and why

## Knowledge Gaps
- **591 isolated node(s):** `ui-entrypoint.sh script`, `API_PORT`, `UI_PORT`, `GRAFANA_PORT`, `POSTGRES_PORT` (+586 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **100 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Universal in-memory book representation — see specs/core-models.md.  One data mo` connect `test_index.py` to `ApiClient`, `LLMResponse`, `test_pipeline.py`, `test_gate.py`, `test_rewrite.py`, `test_format_pdf.py`, `decision-log.md`, `InProcessClient`, `sqlite_pipeline.py`, `test_sqlite_ingest.py`, `sqlite.py`, `test_format_djvu.py`, `chunk_book`, `sqlite_index.py`, `chunk.py`, `bump_index_revision`, `parse_epub`, `test_rerank.py`, `test_v2_routes.py`, `Handoff — Zoomcamp checklist + plan v2.1 verification`, `test_inprocess_bridge.py`, `Debugging and troubleshooting`, `roadmap.py`, `HomeLib — improved product and build plan v2`, `homelib — submission checklist`, `test_openapi_snapshot.py`, `test_repo_hygiene.py`, `spec: core-models — `homelib_core.models``, `_is_substantial`, `spec: evals-retrieval — `evals/ground_truth.py` + `evals/retrieval_eval.py``?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Why does `A single ranked retrieval result from one search arm or rerank pass.` connect `_is_substantial` to `v2_routes.py`, `LLMResponse`, `test_pipeline.py`, `sqlite_pipeline.py`, `test_format_djvu.py`, `pipeline.py`, `test_fetch_catalog.py`, `sqlite_index.py`, `test_rotunda.py`, `write_report`, `test_inprocess_bridge.py`, `sqlite_deps.py`, `HomeLib v2 — reviewer handoff`, `roadmap.py`, `SyncASGITransport`, `test_coffee_table.py`, `Repo structure`, `User flows`, `spec: rerank — `homelib_rag.rerank``, `rerank.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `AppMode` connect `cold_clone_drill.sh` to `12.3 Work packages`, `spec: formats — `homelib_core.formats` + `homelib_core.normalize``, `test_streamlit_theme_pins_parchment_gold_from_mockups`, `homelib`, `test_pipeline.py`, `coffee_table.py`, `roadmap.py`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 69 inferred relationships involving `connect()` (e.g. with `_db()` and `_db()`) actually correct?**
  _`connect()` has 69 INFERRED edges - model-reasoned connections that need verification._
- **Are the 60 inferred relationships involving `migrate()` (e.g. with `_db()` and `_db()`) actually correct?**
  _`migrate()` has 60 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `LLMResponse` (e.g. with `_CountingClient` and `_FakeConnection`) actually correct?**
  _`LLMResponse` has 22 INFERRED edges - model-reasoned connections that need verification._
- **What connects `homelib applications: api, ui, ingest.`, `FastAPI service — the single contract every consumer talks through.`, `HTTP gate for the shared Cloud demo's per-principal daily LLM cap.` to the rest of the system?**
  _1461 weakly-connected nodes found - possible documentation gaps or missing edges._