# Graph Report - hostexecutor  (2026-09-09)

## Corpus Check
- 235 files · ~284,398 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 4105 nodes · 8843 edges · 311 communities (199 shown, 112 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 1633 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `70f95567`
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
- _resolve_llm_env
- MonkeyPatch
- Path
- pre-push
- test_passage_number_outside_the_context_with_an_unfindable_quote_is_rejected
- test_quote_matching_ignores_only_whitespace_differences
- test_passage_ordinal_is_not_accepted_as_a_chunk_id
- Any
- Path
- Response
- test_context_prompt_never_shows_a_chunk_id
- test_citation_carries_a_block_id_that_can_be_resolved
- test_factual_answer_with_empty_citations_is_not_trusted
- Connection
- datetime
- Path
- test_gap_report.py
- ADR-007 — Licence (provisional)
- Design — how the magic-library look reaches the product
- Any
- MonkeyPatch
- Path
- test_user_agent.py
- LLM prompt-variant eval
- Documentation licence
- main
- ui-entrypoint.sh
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
1. `connect()` - 95 edges
2. `migrate()` - 87 edges
3. `LLMResponse` - 69 edges
4. `ApiClient` - 57 edges
5. `CatalogEntry` - 56 edges
6. `Hit` - 53 edges
7. `ChatMessage` - 51 edges
8. `GroundTruthRow` - 47 edges
9. `answer()` - 47 edges
10. `LLMUsage` - 46 edges

## Surprising Connections (you probably didn't know these)
- `QueryLogRow` --uses--> `BookDoc`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py
- `QueryLogRow` --uses--> `Chunk`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py
- `Deps` --uses--> `BookDoc`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py
- `Deps` --uses--> `Chunk`  [INFERRED]
  apps/api/main.py → packages/homelib-core/src/homelib_core/models.py
- `_ground_hits_for_ask()` --calls--> `boost_books_named_in_query()`  [INFERRED]
  apps/api/main.py → packages/homelib-rag/src/homelib_rag/hybrid.py

## Import Cycles
- None detected.

## Communities (311 total, 112 thin omitted)

### Community 0 - "v2_routes.py"
Cohesion: 0.17
Nodes (6): SQLite dispatch on homelib_rag.index when HOMELIB_SQLITE_PATH is set., The reviewer-visible symptom: with only SQLite reachable, a grounded     answer, `agent.search_catalog` is bound in three places (API deps, the roadmap     wrapp, _ScriptedClient, test_agent_search_catalog_uses_sqlite_when_path_set(), test_answer_end_to_end_not_degraded_on_sqlite_only_host()

### Community 1 - "test_judge.py"
Cohesion: 0.13
Nodes (14): Exception, For each citation in a non-degraded response, `quote` is a substring     of the, The client raises a connection error; `answer()` returns a degraded     `AskResp, `Citation.book_title` always comes from `_book_metadata`, never from     anythin, Groq `json_validate_failed` must not stick on the first attempt when a     plain, A scripted fake `OpenAICompatibleClient`. No network., The guard rail must not have been loosened into uselessness.      Whitespace-ins, _ScriptedClient (+6 more)

### Community 2 - "test_api.py"
Cohesion: 0.11
Nodes (34): append_history(), Baseline, compare_to_baseline(), _current_git_sha(), _describe(), load_baseline(), MetricSpec, Eval regression gate — see specs/eval-gate.md.  Turns "the eval numbers got wors (+26 more)

### Community 3 - "ApiClient"
Cohesion: 0.13
Nodes (26): AskResponse, answer_shelf_meta(), _book_matches_genre(), _catalog_link_line(), _CatalogLink, _format_book_line(), _genre_from_question(), is_shelf_meta_intent() (+18 more)

### Community 4 - "BaseModel"
Cohesion: 0.09
Nodes (35): _book_titles_for_boost(), _build_default_deps(), _connect(), _default_counts(), _default_db_reachable(), _default_ingest(), _default_list_books(), _default_llm_reachable() (+27 more)

### Community 5 - "ChatMessage"
Cohesion: 0.12
Nodes (19): HomelibClient, FixtureRequest, MockTransport, client(), demo_client(), _inprocess(), WP08 HomelibClient InProcess/Http conformance — specs/client.md named reds., Server forgot our session (restart/TTL): mint once, resend once. (+11 more)

### Community 6 - "test_answer.py"
Cohesion: 0.14
Nodes (51): Path, Connection, MonkeyPatch, Path, MonkeyPatch, test_load_indexed_chunk_ids_reads_sqlite(), main(), connect() (+43 more)

### Community 7 - "test_view_model.py"
Cohesion: 0.04
Nodes (81): _imported_modules(), _make_book(), _make_citation(), _make_step(), BookSummary, Citation, RoadmapStep, Behavioural tests for apps/ui/view_model.py.  These drive the pure helper functi (+73 more)

### Community 8 - "test_fetch_corpus.py"
Cohesion: 0.06
Nodes (33): ApiClient, Block, _extract_detail(), Any, Client, Response, Best-effort extraction of the ``{"detail": str}`` error envelope., Thin synchronous client over the homelib public API. (+25 more)

### Community 9 - "models.py"
Cohesion: 0.06
Nodes (56): MonkeyPatch, BaseHTTPRequestHandler, ParseResult, build_read_article_html(), Clean article HTML for Safari Listen to Page (not Streamlit chrome)., Top-level HTML document Safari Reader / Listen to Page can detect., ReadPage, _api_base() (+48 more)

### Community 10 - "hybrid_search"
Cohesion: 0.07
Nodes (40): _render_official_preview(), MonkeyPatch, Path, build_official_preview_stage_html(), is_allowlisted_official_url(), load_official_preview_books(), normalize_official_language(), normalize_projection_source() (+32 more)

### Community 11 - "test_index.py"
Cohesion: 0.19
Nodes (14): merge_catalog_with_shelf(), _needle_hits_blob(), Bridge shelf titles into catalog candidates for Mentor / Roadmap.  The Open Libr, Return shelf books matching the goal/interests by title, author, or topic., Catalog first, then shelf rows whose title is not already present., shelf_catalog_entries(), Shelf → catalog bridge for Stoicism / Meditations Mentor+Roadmap., test_merge_catalog_with_shelf_appends_new_title() (+6 more)

### Community 12 - "LLMResponse"
Cohesion: 0.07
Nodes (59): Any, AgentResult, _block_from_pg_row(), _connect(), _dsn(), get_block(), get_book_block(), _parse_arguments() (+51 more)

### Community 13 - "connect"
Cohesion: 0.07
Nodes (31): _default_rewriter(), Production query rewrite. Imported lazily — see `_default_retrieve`., _call_llm(), _client(), _model_name(), LLM query rewriter — see specs/rewrite.md.  Asks an LLM to turn a user's natural, Internal typed shape the LLM is asked to produce.      Not exposed publicly — `r, Call the configured LLM and return its raw response content.      Raises on any (+23 more)

### Community 14 - "test_pipeline.py"
Cohesion: 0.12
Nodes (75): Deps, get_health(), post_feedback(), post_ingest(), post_roadmap(), RoadmapResponse, QueryLogRow, Everything an endpoint needs, injected via `Depends(get_deps)`.      Every field (+67 more)

### Community 15 - "test_gate.py"
Cohesion: 0.13
Nodes (22): build_book(), build_snapshot(), _clean_text_path(), main(), Build the committed corpus snapshot — see specs/corpus.md.  Parses every manifes, Path to the boilerplate-stripped text `fetch_corpus.py --fetch` wrote., Parse one manifest entry into a `BookDoc` carrying its manifest metadata.      `, Parse every manifest entry and write the gzipped snapshot. Returns book count. (+14 more)

### Community 16 - "test_rewrite.py"
Cohesion: 0.12
Nodes (21): _is_substantial(), Skip chunks too short, or too table-of-contents-like, to ask about., _fake_chunk(), fixture_chunks(), _load_committed_rows(), _make_book(), Tests for evals/ground_truth.py — see specs/evals-retrieval.md.  No test in this, A tiny synthetic book with enough sentence-delimited text for a few     substant (+13 more)

### Community 17 - "test_format_pdf.py"
Cohesion: 0.09
Nodes (36): PdfReader, _extract_authors(), _extract_title(), _is_likely_scanned(), _ocr_extract(), parse_pdf(), PDF format handler — see specs/formats.md.  Two extraction paths, chosen per doc, Run PyMuPDF's OCR text extraction over every page of `path`.      Raises `Runtim (+28 more)

### Community 18 - "decision-log.md"
Cohesion: 0.11
Nodes (28): float64, Namespace, NDArray, Path, AnswerSimilarityScore, build_reference_lookup(), _cosine(), _default_embed() (+20 more)

### Community 19 - "test_metrics.py"
Cohesion: 0.10
Nodes (40): ChunkId, GroundTruth, GroundTruthBooks, RankedBooks, RankedResults, _first_relevant_rank(), hit_rate_at_k(), hit_rate_book() (+32 more)

### Community 20 - "connectors.py"
Cohesion: 0.05
Nodes (69): Any, Client, Path, MonkeyPatch, Path, Protocol, Behavioural tests for lawful catalog federation — specs/connectors.md.  Fixtures, test_ambiguous_editions_never_merge() (+61 more)

### Community 21 - "coffee_table.py"
Cohesion: 0.16
Nodes (30): Any, Connection, datetime, Row, LookupError, StrEnum, _current_playlist_id(), _now_iso() (+22 more)

### Community 22 - "InProcessClient"
Cohesion: 0.11
Nodes (29): parse_djvu(), Extract a `BookDoc` from a DJVU file via `djvutxt`.      Raises `RuntimeError` (, _attach_page_text(), _build_real_djvu_fixture(), _fake_run(), _FakeWhich, Red-first tests for `homelib_core.formats.djvu` — see specs/formats.md.  Written, `shutil.which` monkeypatched to `None` -> a specific, actionable `RuntimeError`. (+21 more)

### Community 23 - "test_ground_truth.py"
Cohesion: 0.15
Nodes (21): LogCaptureFixture, build_ground_truth(), generate_questions(), load_corpus_chunks(), Recompute every chunk in the committed corpus snapshot.      Deterministic given, Stratified, seeded sample of up to `n` chunks spread across all books.      Chun, One LLM call generating up to `n` specific, retrieval-shaped questions.      Ret, Generate ground-truth rows for `chunks`, one LLM call per chunk.      A chunk th (+13 more)

### Community 24 - "sqlite_pipeline.py"
Cohesion: 0.09
Nodes (30): build_rotunda_html(), door_from_query(), _json_for_script(), The Crossroads rotunda — the rotating room of doors (specs/rotunda.md).  Pure mo, JSON that is safe inside an inline `<script>`.      Every `<` becomes the JSON e, Resolve the door an Enter link asked for.      `?door=X` arrives when the rotund, Return the rotunda fragment that `app.py` renders with `st.html`.      `active`, Rotunda: pure-string behaviour of the rotating room (specs/rotunda.md).  No scre (+22 more)

### Community 25 - "test_sqlite_ingest.py"
Cohesion: 0.13
Nodes (40): expected_chunk_ids_from_snapshot(), manifest_rights_by_book_id(), LoadInfo, run_sqlite_pipeline(), staging_db_path(), _book(), _corpus_counts(), _create_minimal_staging() (+32 more)

### Community 26 - "sqlite.py"
Cohesion: 0.08
Nodes (35): _book(), clean_corpus_tables(), _drop_staging_schemas(), live_database_url(), Tests for apps/ingest/pipeline.py — see specs/ingestion.md named red tests.  Uni, This process's throwaway database — never the application's., Drop dlt's staging dataset (and the `_staging` merge dataset dlt makes     along, Row counts for every canonical table. (+27 more)

### Community 27 - "test_format_djvu.py"
Cohesion: 0.11
Nodes (24): _abstention_response(), _blob_has_goal_tokens(), build_path(), _evidence_blob(), _goal_content_tokens(), _has_on_goal_evidence(), _mentor_tools(), _passage_citations() (+16 more)

### Community 28 - "HttpClient"
Cohesion: 0.12
Nodes (42): Any, Connection, datetime, books_default_rights_status(), compute_index_revision(), create_demo_session(), current_index_revision(), _current_reset_generation() (+34 more)

### Community 29 - "pipeline.py"
Cohesion: 0.16
Nodes (31): hybrid_search(), Search `q`, returning `(hits, mode_used)`.      `mode="lexical"` or `mode="vecto, Exception, MonkeyPatch, _hit(), _raising(), Red tests for `homelib_rag.hybrid` — see specs/hybrid.md.  `search_lexical` and, Symmetric case to the lexical-down test above. (+23 more)

### Community 30 - "chunk_book"
Cohesion: 0.12
Nodes (29): DrawFn, test_sampling_skips_short_chunks(), chunk_book(), Chunk `doc` into retrieval-sized, citation-traceable `Chunk`s.      Chunks never, _build_doc(), _lorem_sentences(), _make_block(), _make_provenance() (+21 more)

### Community 31 - "test_fetch_catalog.py"
Cohesion: 0.15
Nodes (20): Cursor, _connect(), _dsn(), _embed_query(), _first_page(), _load_embedder(), Lexical (Postgres FTS) and vector (pgvector) search arms — see specs/indexing.md, Render an embedding as pgvector's text input format: `[0.1,0.2,...]`.      Retur (+12 more)

### Community 32 - "view_model.py"
Cohesion: 0.13
Nodes (31): Retriever, Rewriter, _make_retrieve(), Build production retrieval closing over one RRF fusion constant.      `_default_, Run one query through one arm, recording what actually happened.      A retrieva, Score one arm over `rows`.      `rewrite=True` routes every question through `ho, Score every arm in `arms` over the same `rows`, in `ARMS` order., Score the `hybrid` arm once per value in `ks`, varying `rrf_k` only.      Every (+23 more)

### Community 33 - "app.py"
Cohesion: 0.14
Nodes (31): Connection, MonkeyPatch, Path, _insert_block(), _insert_book(), _insert_chunk(), _mock_scene_embedder(), WP04 scene-search red tests — see specs/scene-search.md.  Cross-encoder rerank a (+23 more)

### Community 34 - "test_retrieval_eval.py"
Cohesion: 0.07
Nodes (28): Contract-drift guard, `DELETE /v1/playlists/current/items/{item_id}`, Endpoints — live v1 (OpenAPI snapshot), Error and degradation behavior, `GET /health`, `GET /v1/areas` / `POST /v1/areas`, `GET /v1/audio/capabilities`, `GET /v1/blocks/{id}` (+20 more)

### Community 35 - "sqlite_index.py"
Cohesion: 0.09
Nodes (43): float32, book_metadata(), browse_catalog(), catalog_row_count(), _catalog_row_matches_needle(), _connect(), _decode_embedding(), _earliest_matched_token_index() (+35 more)

### Community 36 - "chunk.py"
Cohesion: 0.11
Nodes (22): _atomic_unit_spans(), _chapter_key(), _make_chunk_id(), _pack_indices(), _pack_sentences(), _points_to_spans(), Block-aware, sentence-boundary chunking — see specs/chunking.md.  Turns a `BookD, End offsets partitioning `text` into sentences (last point == len(text)). (+14 more)

### Community 37 - "test_rotunda.py"
Cohesion: 0.19
Nodes (16): MonkeyPatch, Path, build_homelib_client(), True for Cloud/local demo: ``APP_MODE=demo`` and no ``API_URL``.      Compose al, Factory: demo → InProcessClient; else HttpClient(API_URL)., wants_inprocess_client(), Demo-mode HomelibClient factory — APP_MODE=demo selects InProcessClient.  Regres, Community Cloud: GROQ_API_KEY in Secrets must reach os.environ.      OpenAIClien (+8 more)

### Community 38 - "test_models.py"
Cohesion: 0.19
Nodes (4): ADR-004 — SQLite replaces Postgres, Consequences, Context, Decision

### Community 39 - "v2 target — product.md §8 (markdown this WP; not in the snapshot yet)"
Cohesion: 0.09
Nodes (13): _connect_never_called(), Red tests for `homelib_rag.index` — see specs/indexing.md.  Unit tests (the defa, Undo whatever a test left in the lazy embedder singleton.      The unit tests ab, A constant name lets two concurrent runs delete each other's database.      Guar, Point `index.py`'s `_connect()` at the throwaway test database for one test., _restore_embedder_singleton(), _seeded_db(), test_search_lexical_empty_query_raises() (+5 more)

### Community 40 - "bump_index_revision"
Cohesion: 0.10
Nodes (40): _build_prompt(), build_roadmap(), _candidate_line(), _parse_and_validate(), CatalogSearch, Level, Personalized reading roadmap generation — see specs/roadmap.md.  Turns a user's, Parse+validate one LLM roadmap response. Raises `RoadmapParseError`.      Trunca (+32 more)

### Community 41 - "write_report"
Cohesion: 0.15
Nodes (26): Path, One `rrf_k` value's metrics from the hybrid arm — see `run_rrf_k_sweep`., Upsert the "RRF k sweep" table into `path`, leaving the rest of the     report (, RrfSweepPoint, write_rrf_k_sweep_section(), _arm_metrics(), _four_arms(), Tests for evals/retrieval_eval.py — the retrieval-arm bake-off.  Every test here (+18 more)

### Community 42 - "answer.py"
Cohesion: 0.16
Nodes (30): _reset_caches_for_tests(), Connection, MonkeyPatch, Path, WP04 SQLite index tests — FTS5 + cached NumPy matrix., ``money described`` AND-matches nothing if the words never co-occur.      Withou, Ingest stores embeddings as float32 BLOBs; JSON-only decode fully degraded vecto, LIVE: Stoicism interest is not an exact OL subject in the snapshot. (+22 more)

### Community 43 - "retrieval_eval.py"
Cohesion: 0.17
Nodes (26): MonkeyPatch, Path, TestClient, API tests for observatory + Coffee Table routes (WP07/WP10)., Compose mounts a pipeline-seeded DB that never ran store.seed().      After HOME, WP10 live feedback path: POST /v1/feedback updates query_log (UI→API→DB)., WP10: demo_traffic.py --n 40 leaves Observatory with ≥5 non-empty chart ids., The server-side contract the client fix (H3) relies on: a minted     `X-Demo-Ses (+18 more)

### Community 44 - "parse_txt"
Cohesion: 0.04
Nodes (107): Namespace, Path, Exception, MonkeyPatch, Path, _answer_one(), AnsweredCase, _judge_metrics() (+99 more)

### Community 45 - "parse_epub"
Cohesion: 0.18
Nodes (19): Element, _check_not_zip_bomb(), _element_text(), _localname(), parse_epub(), EPUB format handler — see specs/formats.md.  Block granularity: each `h1`-`h6`,, Extract a `BookDoc` from an EPUB file., _build_epub_bytes() (+11 more)

### Community 46 - "ground_truth.py"
Cohesion: 0.10
Nodes (23): get_deps(), FastAPI dependency. `apps/api/tests/test_api.py` overrides this     wholesale vi, `/health` must not wait for an in-flight Ask's LLM call — that was the     compo, test_health_returns_while_ask_llm_is_still_running(), Request, build_inprocess_client(), inflate_seed_if_missing(), _inside_data_dir() (+15 more)

### Community 47 - "test_rerank.py"
Cohesion: 0.12
Nodes (22): _call_llm(), _clean_questions(), _client(), _echoes_opening(), _is_self_referential(), main(), _model_name(), _normalize_words() (+14 more)

### Community 48 - "test_v2_routes.py"
Cohesion: 0.12
Nodes (23): _load_json_line(), make_block_id(), Compute a `Block.block_id`.      Stable across runs and processes: same `(book_i, Deserialize from `to_jsonl` output.          Raises `ValueError` naming the offe, test_parse_pdf_native_text_page_provenance_and_offsets(), _make_block(), _make_book_doc(), _make_provenance() (+15 more)

### Community 49 - "Handoff — Zoomcamp checklist + plan v2.1 verification"
Cohesion: 0.12
Nodes (28): _is_poem_byline(), _markdown_heading(), parse_txt(), _plaintext_heading(), Path, TXT/Markdown format handler — see specs/formats.md.  Heading inference: a Markdo, True for short all-caps attributions that look like author bylines., An all-caps / Title-Case line under 80 chars, followed by a blank line. (+20 more)

### Community 50 - "test_inprocess_bridge.py"
Cohesion: 0.09
Nodes (21): _base_deps(), _missing_block(), _missing_book_block(), Block, Behavioural tests for `apps/api` — see specs/api.md.  No live Postgres, no live, Regression: uncached Groq `/models` probes made solo `/health` 1.2-1.9s     and, SQLite creates the file on first connect, so a never-seeded clone has a     reac, Placeholder home for the drift-guard assertion — the real, spec-named     test l (+13 more)

### Community 51 - "Extension points"
Cohesion: 0.29
Nodes (19): _book_rights(), _canonical_text(), _chapter_section(), _chunk_in_chapter(), _context_window(), _exact_hits(), _filter_hits_to_scope(), _hits_to_scene() (+11 more)

### Community 52 - "sqlite_deps.py"
Cohesion: 0.20
Nodes (11): Edition / runtime flags from the environment.  `APP_MODE` and timeout defaults., read_app_mode(), read_llm_max_output_tokens(), read_llm_timeout_seconds(), APP_MODE / demo-timeout config skeleton (WP00).  Behaviour: the process can read, test_app_mode_defaults_to_selfhosted_when_unset(), test_demo_mode_reads_app_mode_env(), test_llm_max_output_tokens_defaults_to_product_doc() (+3 more)

### Community 53 - "3. Proposed SQLite tables"
Cohesion: 0.17
Nodes (23): Embedder, ndarray, Path, Cosine-similarity-score every answer whose question has a reference.      An ans, One row of a `--save-answers` JSONL file from `evals/llm_eval.py`.      Delibera, SavedAnswer, score_answers(), _chunk() (+15 more)

### Community 54 - "parse_djvu"
Cohesion: 0.12
Nodes (39): Client, Path, MonkeyPatch, Path, fetch_one(), FetchOutcome, load_manifest(), main() (+31 more)

### Community 55 - "Data model and schemas"
Cohesion: 0.18
Nodes (10): A model swap does not fix it either (2026-08-31), ADR-003 — Answer prompt: keep the incumbent, on a null result, Baseline, Consequences, Context, Correction: these measurements are less stable than either of us claimed, Decision, The winner is flagged unproven, and that is the point (+2 more)

### Community 57 - "Local development"
Cohesion: 0.14
Nodes (21): Connection, Embedder, float64, NDArray, build_lexical_index(), build_vector_index(), _default_embed(), _fts_query() (+13 more)

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
Cohesion: 0.12
Nodes (39): Any, Block, MonkeyPatch, Path, Connection, datetime, Path, _base_deps() (+31 more)

### Community 62 - "HomeLib — improved product and build plan v2"
Cohesion: 0.16
Nodes (14): _decode_djvu_string(), djvu_available(), _djvutxt_version(), _extract_page_texts(), _first_quoted_string(), _iter_top_level_forms(), DJVU format handler — see specs/formats.md.  Extracts the hidden text layer via, Yield each top-level parenthesized S-expression in `text`, in order. (+6 more)

### Community 63 - "SyncASGITransport"
Cohesion: 0.09
Nodes (37): Any, Connection, Namespace, Path, ArmMetrics, _connect(), _coverage_lines(), _degradation_section() (+29 more)

### Community 64 - "12.3 Work packages"
Cohesion: 0.16
Nodes (25): Connection, Connection, Path, build_observatory(), ObservatoryChart, ObservatoryPoint, Observatory aggregates from query_log — specs/observatory.md (WP10)., _db() (+17 more)

### Community 65 - "homelib — submission checklist"
Cohesion: 0.14
Nodes (23): ndarray, Path, chunk_corpus(), Re-chunk every book in `docs` with one `(target_chars, overlap)` pair., Mean whitespace-token count of one whole chapter/section, across the     corpus, whole_section_token_baseline(), _build_doc(), _corpus() (+15 more)

### Community 66 - "Stakeholder picky review + wiki/mermaid handoff — 2026-09-05"
Cohesion: 0.09
Nodes (40): _in_memory_tracer_provider(), _llm_json(), _make_deps(), Vector search "raises" (simulated at the retrieve seam): response is     200 wit, ADR-001 (docs/adrs/ADR-001-retrieval-arm.md) measured query rewriting     agains, Passage content Q must still retrieve + cite; shelf-meta must not short-circuit., A scripted fake `OpenAICompatibleClient`. No network., Inventory Ask must list books via list_books — never empty passage refuse. (+32 more)

### Community 67 - "HomeLib v2.1 — final merged execution plan (capstone rebuild + product)"
Cohesion: 0.16
Nodes (22): AskResponse, Connection, AskResponse, Connection, Path, cache_key(), lookup(), _normalize_question() (+14 more)

### Community 68 - "Architecture overview"
Cohesion: 0.13
Nodes (15): API endpoint map, Catalog and rights, Core entities, Corpus (ported from v1), Data model and schemas, Entity relationship diagram, Identity, Index and embedding revision (+7 more)

### Community 69 - "prompt_hash"
Cohesion: 0.13
Nodes (15): Answer prompt and rewrite (supplementary), Chunk ID stability for eval ground truth, Decision log, HomelibClient: InProcess vs Http, Hybrid search: BM25/FTS5 + vector + RRF vs alternatives, Ingest: dlt ELT shape, staging → canonical, idempotency, Licence — owner decision, recorded not fixed, Observability: Observatory vs Grafana (+7 more)

### Community 70 - "QueryOutcome"
Cohesion: 0.19
Nodes (18): Connection, Connection, Path, judge_recent_rows(), Online judge on live traffic — core logic behind `scripts/judge_recent.py`.  C6, Judge up to `n` of the most recent unjudged, answer-logged rows.      `client` i, _unjudged_rows(), _db() (+10 more)

### Community 71 - "test_index_sqlite_dispatch.py"
Cohesion: 0.13
Nodes (23): NamedTuple, ChunkConfigResult, filter_rows_to_available_books(), One `(target_chars, overlap)` config's book-level retrieval scores., An in-memory, brute-force cosine-similarity index over chunk texts., Rows whose `book_id` is present in `docs`, and how many were dropped.      Scori, Score every `(target_chars, overlap)` pair in `configs` over the same `rows`., run_chunk_sweep() (+15 more)

### Community 72 - "5. Signature product experience"
Cohesion: 0.13
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
Cohesion: 0.15
Nodes (21): get_trace(), C5 (specs/monitoring.md "Tracing"): the span tree for one `/v1/ask`     request', Connection, Path, _db(), Behavioural tests for `apps.api.tracing` — C5 (specs/monitoring.md "Tracing")., A span tree exported through `SqliteSpanExporter` reads back via     `read_trace, A span whose parent_span_id names nothing in this batch (e.g. a     partially fl (+13 more)

### Community 78 - "test_coffee_table.py"
Cohesion: 0.09
Nodes (31): _hit(), MonkeyPatch, The `query_log` row for a cache hit has `cache_hit=True` — captured     via the, LIVE: Ask abstained while Shelf scene search opened the woods passage., `/health` reports booleans only about the LLM — no substring of the     configur, The `rerank` span wraps the real cross-encoder call inside the     production re, APP_MODE=demo: asking the SAME question twice calls the LLM once —     the secon, A pre-seeded cache entry for the exact key this request would compute     is ign (+23 more)

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
Cohesion: 0.29
Nodes (7): build_roadmap(), Level, RoadmapResponse, Agent-tool wrapper over `homelib_rag.roadmap.build_roadmap`, with the     defaul, default_llm_client(), Process-wide lazy `OpenAIClient` singleton, built from env vars., test_default_llm_client_is_a_singleton()

### Community 83 - "test_repo_hygiene.py"
Cohesion: 0.11
Nodes (28): blocks_resource(), books_resource(), catalog_resource(), chunk_embeddings_resource(), chunks_resource(), _embed_batch(), embed_texts(), _ensure_ivfflat_index() (+20 more)

### Community 84 - "ADR-001 — Retrieval arm: hybrid + rerank, with query rewrite off"
Cohesion: 0.20
Nodes (7): Streamlit Community Cloud edition: the files Cloud reads and the seed it needs., `streamlit_app.py` is a shim over `apps/ui/app.py`, not a second UI., Cloud resolves from uv.lock; GPU torch wheels would blow its disk/RSS., `.python-version` (uv, pyenv, Cloud reviewers) agrees with pyproject., test_cloud_entrypoint_runs_the_same_ui_main(), test_python_version_file_matches_requires_python(), test_uv_lock_pins_cpu_torch_index()

### Community 85 - "Decision"
Cohesion: 0.10
Nodes (25): TokenUsage, MonkeyPatch, Ask door — empty query vs unreachable, never-blank empty answer., A textual passage refusal gets the same lawful next step as an empty answer., #A1 inventory miss after Groq json_validate: empty degraded body must     still, Shelf miss + Discover payload in session → Open lawful source links., _selfhosted_against_closed_port(), test_ask_empty_answer_renders_catalog_links_from_session() (+17 more)

### Community 86 - "Repo structure"
Cohesion: 0.15
Nodes (21): OpenAIClient, Default `OpenAICompatibleClient`, backed by the `openai` SDK against     an Open, MonkeyPatch, Behavioural tests for `homelib_rag.answer` — see specs/answer.md.  No live Postg, The prompt sent to the LLM must carry the book's authors, not just its     title, `_TIMEOUT_SECONDS` (module constant) is read from `LLM_TIMEOUT_SECONDS`     at i, Bounds worst-case CPU generation time — a runaway completion should     not turn, A blank `LLM_API_KEY` (empty Cloud secret) must construct like an absent     one (+13 more)

### Community 87 - "write_ground_truth"
Cohesion: 0.13
Nodes (20): _build_context_prompt(), _content_tokens(), _fuse(), _hybrid(), promote_query_overlap(), promote_verbatim_phrase(), Reciprocal Rank Fusion over the lexical and vector search arms — see specs/hybri, Lazy re-export so tests can monkeypatch ``hybrid.search_lexical``. (+12 more)

### Community 88 - "spec: answer — `homelib_rag.answer`"
Cohesion: 0.20
Nodes (9): ADR-010 — Single repo until public; paid tier after, Consequences, Context, Decision, Obsidian (post-public-publish, contract-first — product §15), Post-public-publish / paid tier (same Forgejo repo later — not another git remote), Product ladder, Public app this week (+1 more)

### Community 89 - "spec: audio — capabilities and one lawful preview"
Cohesion: 0.08
Nodes (59): Exception, Any, Any, LLMResponse, LLMUsage, Any, The normalized result of one `OpenAICompatibleClient.chat` call., _build_intake_prompt() (+51 more)

### Community 90 - "spec: chunking — `homelib_core.chunk`"
Cohesion: 0.11
Nodes (16): Apps, Branch model, Docker and CI, Documentation map, Packages, Related pages, Repo structure, Specs vs code vs tests vs data (+8 more)

### Community 91 - "spec: connectors — lawful catalog federation (“Forbidden Stacks”)"
Cohesion: 0.10
Nodes (15): MonkeyPatch, Crossroads doors rendered through Streamlit's own test harness.  `streamlit.test, The rotunda and the door heading must agree. 'Roadmap (v1)' leaked an     intern, `?projection=1` must open projector mode exactly once. Regression for the     tr, `?source=` must be consumed into session state once, not re-added on     every r, The Projection ordinal must be keyed per book, not global (BUG 2): a     stale g, LIVE: Projection briefly kept Observatory/Ask controls until another rerun., The rotunda's Enter reloads the page on `?door=X`; the app must open X     and d (+7 more)

### Community 92 - "spec: core-models — `homelib_core.models`"
Cohesion: 0.50
Nodes (4): parse_file(), Format dispatcher — see specs/formats.md.  `parse_file` is the single entry poin, Derive a `book_id` slug from a file stem (e.g. `"Moby Dick!" -> "moby-dick"`)., _slugify()

### Community 93 - "spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`"
Cohesion: 0.16
Nodes (14): Raise `CitationValidationError` unless every citation is genuine.      Two check, _validate_citations(), _hit(), A fabricated quote not present in the cited chunk's text causes a     degraded f, Groq has returned `citations: [1]` — keep the answer when objects remain., Reattribution must not become "accept anything".      If the words appear in non, Valid JSON with no answer is still an unusable generation, not success., test_a_quote_found_in_no_passage_at_all_still_degrades() (+6 more)

### Community 94 - "spec: ui — `apps/ui` (Streamlit Crossroads)"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: answer — `homelib_rag.answer`, Store dispatch (2026-09-05), Verify

### Community 95 - "User flows"
Cohesion: 0.15
Nodes (22): boost_books_named_in_query(), merge_unique_hits(), Concatenate hit lists, keep first occurrence of each chunk_id, cap at k., When the question names a shelf title, keep that book's hits first., _hit(), MonkeyPatch, Regression tests for Ask ranking helpers — LIVE living-deliberately gap., Full title need not appear; a distinctive token like Walden is enough. (+14 more)

### Community 96 - "_is_substantial"
Cohesion: 0.12
Nodes (15): Guards on the gates themselves.  A config file that looks like a guarantee but i, PR #52 run 13657: quick-lane mypy and 45m heavy suite both hit deadline.      Af, Peer-facing shell: parchment/ink/gold tokens from magic-library mockup.      Wit, UI image only COPY'd apps/ + packages/; theme must be copied explicitly.      St, No allowlist may use `paths`.      A `paths` entry exempts every finding in that, The UI process renders READ_PORT into link text and gates the Official     viewe, Hygiene pin (string-match, not behavioural): on the tip path the API     logs as, Indexer excludes: do not confuse with .gitignore — graphify-out/ is committed. (+7 more)

### Community 97 - "Per-book breakdown"
Cohesion: 0.15
Nodes (21): ProgressEvent, delete_playlist_item(), _discover_from_catalog(), _discover_resources(), get_audio_capabilities(), get_observatory(), get_playlist_current(), get_resources() (+13 more)

### Community 98 - "parse_file"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error behavior, Invariants, Named red tests (write before the code), Public interface, Purpose, spec: core-models — `homelib_core.models`, Verify

### Community 99 - "sqlite_only_smoke.sh"
Cohesion: 0.22
Nodes (8): Banned sources (binding), Data contracts (field-level), Error / degradation behavior, Named red tests (write before the code), Public interface, Purpose, spec: corpus — `data/` + `apps/ingest/fetch_corpus.py` + `apps/ingest/fetch_catalog.py`, Verify

### Community 100 - "spec: agent-tools — `homelib_rag.agent`"
Cohesion: 0.09
Nodes (18): Agent (Mentor only), Citation precision (N=1 live smoke, 2026-09-07, Groq `openai/gpt-oss-20b`), Error taxonomy (one example each), Eval gate, EVAL.md — Track E interview artifact, Generation, Golden set honesty, Prompt-injection probes (3) (+10 more)

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
Cohesion: 0.24
Nodes (17): _default_db_path(), _default_manifest_path(), main(), _make_pipeline(), manifest_rights_from_path(), Any, DltResource, Path (+9 more)

### Community 105 - "spec: formats — `homelib_core.formats` + `homelib_core.normalize`"
Cohesion: 0.13
Nodes (13): Connection, Tracer, ReadableSpan, SpanExporter, SpanExportResult, TracerProvider, _build_provider(), get_tracer() (+5 more)

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
Cohesion: 0.12
Nodes (22): _collapse_whitespace(), _degraded_reason_code(), _degraded_response(), _is_json_validate_failure(), _is_rate_limit_failure(), _is_uncited_failure(), Citation-checked answer synthesis — see specs/answer.md.  Synthesizes an `AskRes, The shape the LLM is asked to produce for one citation.      Deliberately has NO (+14 more)

### Community 113 - "spec: rewrite — `homelib_rag.rewrite`"
Cohesion: 0.25
Nodes (8): 7.1 One service layer, two clients, 7.2 Provider contract, 7.3 Other interchangeability seams, 7.4 SQLite, 7.5 Embeddings, 7.6 Ingestion, 7.7 RAG and agent flow, 7. Technical architecture

### Community 114 - "spec: roadmap — `homelib_rag.roadmap`"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: progress — reading and listening positions, Verify

### Community 115 - "spec: rotunda — Library Crossroads doors (product §5.2)"
Cohesion: 0.04
Nodes (42): A. Rubric — the graded criteria (26 points), B. Self-hosted Docker readiness, C. Engineering quality (the "maintainable, extendable" half), Cut order (HTML prototype first), D. Nice to have — extendability, E. Known gaps, stated plainly, F. v2 work packages (WP00–WP11), H. WP00 landing checklist (this PR) (+34 more)

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
Nodes (12): _clear_overrides(), Any, Every test gets a fresh tracer provider, built lazily on next     `get_tracer()`, P0 Cloud bug: inventory Q cached as passage refuse under arm=hybrid must     not, `HOMELIB_LOG_ANSWERS` unset (the default): a real /v1/ask call, with a     real, `HOMELIB_LOG_ANSWERS=1` plus a real SQLite store: the question and     answer AR, _reset_tracer(), test_answer_log_off_by_default() (+4 more)

### Community 123 - "spec: observatory — in-app monitoring (replaces Grafana)"
Cohesion: 0.20
Nodes (10): _FakeCursor, _patch_connect(), Scripted cursor for exercising `main._connect()` production helpers., test_default_counts_returns_table_totals(), test_default_db_reachable_true_when_select_one_succeeds(), test_default_list_books_maps_rows_to_summaries(), test_default_log_query_inserts_monitoring_row(), test_default_log_query_swallows_db_errors() (+2 more)

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
Cohesion: 0.14
Nodes (14): _llm_json(), Any, Sanity: this module's own scripted-client pattern (used across the     agent-too, The model picks a passage; the code supplies the id.      Asking a 7B model to e, The model is good at copying text and bad at bookkeeping.      Observed live: as, Legitimate refuse wording may keep citations=[] without degrading., Every Citation.chunk_id in a non-degraded response corresponds to one     of the, test_a_quote_from_a_different_passage_is_reattributed_not_discarded() (+6 more)

### Community 134 - "ADR-005 — Observatory replaces Grafana"
Cohesion: 0.21
Nodes (12): _graph_refresh_script(), Path, Homelib refreshes on the pushed protected ref — main, and only main.      The re, Execute the graph-refresh step script in a scratch repo with a stub graphify., Behavioural: a push to main rebuilds, commits and pushes the graph.      Until 2, Behavioural: the committed graph never carries the runner's workdir.      graphi, Behavioural: a push to a recreated `v2` neither rebuilds nor pushes.      A seco, _run_graph_refresh() (+4 more)

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
Cohesion: 0.17
Nodes (12): BookMetrics, _per_book(), QueryOutcome, What one arm actually returned for one ground-truth question., True when the arm that ran is not the arm that was asked for., One book's slice of an arm's score., hit-rate@k and MRR@k over `outcomes`, via `evals.metrics`.      Both mappings ar, Book-level hit-rate@k over `outcomes` — see `evals.metrics.hit_rate_book`. (+4 more)

### Community 140 - "ADR-004 — SQLite replaces Postgres"
Cohesion: 0.14
Nodes (14): 1. Project intent, 2. Architecture & schema (v2 — on `main` since the 2026-09-06 collapse), 3. How to run locally, 4. Plan 2.1 / Zoomcamp checklist matrix, 5. Wiki map, 6. What to verify in review, 7. Known gaps / improvements (priority), 8. Current git state (+6 more)

### Community 141 - "ADR-006 — Editions and hosting"
Cohesion: 0.12
Nodes (30): AskResponse, BookSummary, Citation, HttpClient, HTTP client for the homelib public API.  This is the ONLY module under ``apps/ui, Selfhosted edition — FastAPI over HTTP with per-call timeouts., RoadmapStep, Inventory questions often get answer=\"\" — that must not render blank. (+22 more)

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
Nodes (10): Path, _db(), WP07 Coffee Table + progress named red tests — specs/coffee-table.md., test_acceptance_required_before_queued(), test_independent_read_listen_progress(), test_manual_survives_regeneration(), test_no_silent_reinsert_of_completed_or_removed(), test_remove_keeps_resource() (+2 more)

### Community 146 - "6. Data and rights model"
Cohesion: 0.19
Nodes (12): MonkeyPatch, Mentor door tool-use caption — `streamlit.testing.v1.AppTest`, same harness as `, A complete intake is the Mentor door's whole product: area, wing,     proposed p, A Mentor response whose `tool_calls` is non-empty renders a caption     naming t, An empty `tool_calls` (e.g. abstention, or an LLM-unreachable degrade)     rende, Blank Goal + Propose path must not silently no-op.      BrokenMentor.har showed, _seeded_mentor_response(), _selfhosted_against_closed_port() (+4 more)

### Community 147 - "9. Evaluation and monitoring"
Cohesion: 0.12
Nodes (16): APP_MODE behaviour, Canonical commands, Common debug commands, Compose profiles, Demo smoke (Sep 2 gate per evidence addendum), Environment, First-time setup, iPad / AirPlay / Speak Screen (+8 more)

### Community 148 - "_all_job_commands"
Cohesion: 0.23
Nodes (10): build_book_spread_html(), official_book_by_id(), Two-page PDF spread for Official Pottermore preview (display-only).  Served from, Full HTML: open book + text layer + Listen/Reading panel., Official Pottermore two-page book viewer + allowlisted PDF proxy., A render rejection inside showLeaf must not latch busy=true forever —     the fi, test_book_spread_busy_flag_has_finally(), test_book_spread_html_is_two_page_pdfjs_stage() (+2 more)

### Community 149 - "pre-push"
Cohesion: 0.17
Nodes (11): Cost estimate (C1), Data contracts (field-level), Demo answer cache (C4b), Error/degradation behavior, Named red tests (write before the code), Online judge (C6), Public interface, Purpose (+3 more)

### Community 150 - "homelib"
Cohesion: 1.00
Nodes (3): homelib, homelib-core, homelib-rag

### Community 151 - "__init__.py"
Cohesion: 0.24
Nodes (10): Namespace, Path, load_book_docs(), load_ground_truth_rows(), main(), _parse_args(), Every `BookDoc` in the committed corpus snapshot, in file order., Every row of `evals/ground_truth.jsonl`, unsampled, blank lines skipped.      Un (+2 more)

### Community 152 - "__init__.py"
Cohesion: 0.33
Nodes (8): _demo_http_client(), MonkeyPatch, Shelf scene hits must offer an in-UI open-passage control in demo mode.  Cloud d, Two hits sharing open_anchor must not raise StreamlitDuplicateElementKey., _stub_shelf_apis(), test_demo_shelf_scene_hit_offers_open_this_passage(), test_shelf_scene_duplicate_open_anchor_uses_distinct_widget_keys(), _walden_block()

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
Cohesion: 0.24
Nodes (8): API_PORT, fail(), GRAFANA_PORT, OLLAMA_PORT, POSTGRES_PORT, cold_clone_drill.sh script, step(), UI_PORT

### Community 161 - "llm_eval.md"
Cohesion: 0.20
Nodes (8): Course-module map, How we run each piece, FIXES gap LLM Zoomcamp 2026, HomeLib vs LLM Zoomcamp 2026 — coverage gap report, Part 1 — What the 2026 cohort teaches and where HomeLib shows it, Part 3 — Corrections to `docs/course-map.md`, Table 1 — Module → techniques taught → homework asks, Table 2 — Course topic → module → HomeLib status

### Community 162 - "_default_retrieve"
Cohesion: 0.29
Nodes (7): _compose(), `.env.example` ships `APP_MODE=demo` for the Community Cloud path. The     api s, A blank `.env` `LLM_API_KEY=` used to become `ollama` via `:-ollama`,     which, Hygiene (string/structure match, not behavioural). The api service reads     `/d, test_compose_api_passes_groq_and_does_not_coerce_blank_llm_key_to_ollama(), test_compose_api_pins_selfhosted_like_ui(), test_compose_ingest_can_write_sqlite_seed()

### Community 171 - "test_ui_dockerfile_pins_pythonpath_so_apps_imports_resolve"
Cohesion: 0.27
Nodes (4): Crossroads and doors, Door map, How a door opens, Monitoring and feedback

### Community 172 - "test_streamlit_theme_pins_parchment_gold_from_mockups"
Cohesion: 0.40
Nodes (5): _gate_steps(), The scan is a CI step, not just a file sitting in the repo., PR scans must not hang on full history; checkout stays deep for main.      Quick, test_ci_gitleaks_scopes_pr_history_but_keeps_full_checkout(), test_gitleaks_runs_in_ci()

### Community 175 - "test_ci_pytest_forces_workspace_basetemp"
Cohesion: 0.50
Nodes (4): _all_job_commands(), Every `run:` command in the workflow, keyed by job name., Whatever the hook defers must actually be enforced somewhere.      The fast loca, test_some_ci_job_runs_the_full_suite_the_hook_skips()

### Community 177 - "test_gitleaks_allowlists_never_exempt_whole_files"
Cohesion: 0.09
Nodes (50): ApiClientError, ApiUnavailableError, Raised for a 4xx/5xx response from the API.      ``detail`` carries the API's er, Raised when the API cannot be reached at all (timeout/connection)., _cast_vote(), main(), Citation, Client (+42 more)

### Community 178 - "test_drill_asserts_seed_counts_via_health"
Cohesion: 0.24
Nodes (9): Path, Guards on the public snapshot itself.  This repo is developed on a private Forge, The final review found mutually contradictory pending/live Cloud claims., No tracked, reviewer-facing doc may name the private Forgejo host,     its SSH p, `docs/handoffs/` becomes untracked in this same PR, so no tracked doc     may st, test_no_tracked_doc_links_to_handoffs(), test_public_docs_have_no_internal_hosts(), test_submission_docs_name_the_live_demo_without_old_cloud_placeholders() (+1 more)

### Community 179 - "test_drill_verifies_monitoring_via_observatory_not_grafana_panel_count"
Cohesion: 0.31
Nodes (8): demo_llm_daily_limit(), _demo_principal_id(), enforce_demo_llm_quota(), HTTP gate for the shared Cloud demo's per-principal daily LLM cap., Resolve the demo principal, or None when the cap does not apply.      Missing /, 401 on a demo host when the visitor has no valid session (cache hits too)., No-op outside APP_MODE=demo or when SQLite is unset (unit tests).      Count *be, require_demo_session()

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

### Community 185 - "test_graphifyignore_excludes_generated_and_data_paths"
Cohesion: 0.25
Nodes (7): APP_MODE, HOMELIB_SQLITE_PATH, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT_SECONDS, sqlite_only_smoke.sh script

### Community 186 - "test_just_ci_includes_the_secret_scan"
Cohesion: 0.22
Nodes (8): Arm actually used, `hybrid`, `hybrid_rerank`, `lexical`, Per-book breakdown, Retrieval arm eval, RRF k sweep, `vector`

### Community 187 - "__init__.py"
Cohesion: 0.22
Nodes (8): Data contracts (field-level), Error/degradation behavior, Named red tests, On-device Listen in Projection (iPadOS), Public interface, Purpose, spec: audio — capabilities and one lawful preview, Verify

### Community 190 - "__init__.py"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error and degradation behavior, Named red tests, Public interface, Purpose, spec: agent-tools — `homelib_rag.agent`, Verify

### Community 193 - "test_ci_graph_guard_job_exists"
Cohesion: 0.25
Nodes (7): Data contracts (field-level), Error/degradation behavior, Named red tests, Public interface, Purpose, spec: projection — projector reading mode (product §5.9), Verify

### Community 194 - "Path"
Cohesion: 0.33
Nodes (5): Cloud runtime (showcase URL), If something is red at the deadline, Open it as a stranger, Submission — LLM Zoomcamp 2026, What is submitted

### Community 195 - "demo_traffic.py"
Cohesion: 0.25
Nodes (7): Guards on the licence swap itself (ADR-007).  The repo used to ship an unfilled, LICENSE must be the PolyForm Noncommercial 1.0.0 text, not Apache., LICENSE-docs.md must exist and declare CC BY-NC-SA 4.0., Every pyproject.toml must declare PolyForm-Noncommercial-1.0.0.      None of the, test_docs_licence_is_cc_by_nc_sa(), test_license_is_polyform_noncommercial(), test_no_pyproject_declares_apache()

### Community 198 - "Any"
Cohesion: 0.11
Nodes (22): _demo_cache_enabled(), _log_answers_enabled(), _maybe_cache_lookup(), _maybe_cache_store(), _maybe_log_answer(), _maybe_rewrite(), post_ask(), AskResponse (+14 more)

### Community 199 - "AskResponse"
Cohesion: 0.26
Nodes (16): _book_id_in_clause(), _embedding_json_to_blob(), _purge_non_indexable_corpus(), _purge_stale_corpus_rows(), Connection, dlt ingestion into SQLite — WP03; see specs/ingestion.md and ADR-004., Remove canonical rows whose regenerated IDs disappeared from staging., _sync_blocks() (+8 more)

### Community 202 - "Connection"
Cohesion: 0.12
Nodes (17): answer(), _book_metadata(), _dsn(), is_passage_abstention(), True when ``answer`` is an honest refusal rather than a factual claim., `book_id -> (title, authors)` for every id in `book_ids`.      Test seam: monkey, Synthesize an `AskResponse` for `question` from already-retrieved `hits`.      N, A citation to a source absent from `hits` never reaches the caller as     trustw (+9 more)

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

### Community 231 - "_compute_cost_usd"
Cohesion: 0.50
Nodes (4): _compute_cost_usd(), _price_per_1k(), A `LLM_PRICE_PER_1K_*` env var as a float, defaulting to 0.0.      0 is the corr, USD estimate for one `/v1/ask` call from `LLM_PRICE_PER_1K_*` env vars.      Bot

### Community 232 - "get_book_block_endpoint"
Cohesion: 0.50
Nodes (4): get_block_endpoint(), get_book_block_endpoint(), Block, Projection page: one block of ``book_id`` at dense ``ordinal`` (default 0).

### Community 233 - "rights_status_from_manifest"
Cohesion: 0.50
Nodes (4): Resolve manifest rights — explicit `rights_status` only; else fail closed., rights_status_from_manifest(), test_rights_status_rejects_unknown_explicit_value(), test_rights_status_requires_explicit_manifest_field()

### Community 234 - "ADR-008 — Rights gate (unknown fails closed)"
Cohesion: 0.50
Nodes (4): ADR-008 — Rights gate (unknown fails closed), Consequences, Context, Decision

### Community 239 - "HomeLib v2 — Developer Wiki"
Cohesion: 0.50
Nodes (4): HomeLib v2 — Developer Wiki, Implementation status (v2 branch stack), Pages, Quick links

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
- **583 isolated node(s):** `ui-entrypoint.sh script`, `API_PORT`, `UI_PORT`, `GRAFANA_PORT`, `POSTGRES_PORT` (+578 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **112 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Universal in-memory book representation — see specs/core-models.md.  One data mo` connect `test_index.py` to `ApiClient`, `BaseModel`, `LLMResponse`, `test_pipeline.py`, `test_gate.py`, `test_rewrite.py`, `test_format_pdf.py`, `decision-log.md`, `InProcessClient`, `test_sqlite_ingest.py`, `sqlite.py`, `test_format_djvu.py`, `chunk_book`, `sqlite_index.py`, `chunk.py`, `bump_index_revision`, `parse_epub`, `test_rerank.py`, `test_v2_routes.py`, `Handoff — Zoomcamp checklist + plan v2.1 verification`, `test_inprocess_bridge.py`, `3. Proposed SQLite tables`, `Local development`, `Debugging and troubleshooting`, `roadmap.py`, `HomeLib — improved product and build plan v2`, `homelib — submission checklist`, `AskResponse`, `test_openapi_snapshot.py`, `test_repo_hygiene.py`, `spec: audio — capabilities and one lawful preview`, `spec: core-models — `homelib_core.models``?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Why does `A single ranked retrieval result from one search arm or rerank pass.` connect `spec: rerank — `homelib_rag.rerank`` to `v2_routes.py`, `sqlite_index.py`, `BaseModel`, `write_report`, `LLMResponse`, `parse_txt`, `test_inprocess_bridge.py`, `Extension points`, `pipeline.py`, `roadmap.py`, `Repo structure`, `write_ground_truth`, `spec: audio — capabilities and one lawful preview`, `HomeLib v2 — reviewer handoff`, `test_format_djvu.py`, `test_fetch_catalog.py`, `SyncASGITransport`, `User flows`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `connect()` connect `test_answer.py` to `ADR-009 — Audio deferred`, `12. Delivery plan`, `main`, `test_sqlite_ingest.py`, `HttpClient`, `app.py`, `sqlite_index.py`, `answer.py`, `retrieval_eval.py`, `test_inprocess_bridge.py`, `roadmap.py`, `SyncASGITransport`, `12.3 Work packages`, `Stakeholder picky review + wiki/mermaid handoff — 2026-09-05`, `HomeLib v2.1 — final merged execution plan (capstone rebuild + product)`, `QueryOutcome`, `AskResponse`, `homelib`, `test_coffee_table.py`, `test_openapi_snapshot.py`, `spec: audio — capabilities and one lawful preview`, `spec: evals-retrieval — `evals/ground_truth.py` + `evals/retrieval_eval.py``, `spec: indexing — `homelib_rag.index``?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 55 inferred relationships involving `connect()` (e.g. with `_db()` and `_db()`) actually correct?**
  _`connect()` has 55 INFERRED edges - model-reasoned connections that need verification._
- **Are the 54 inferred relationships involving `migrate()` (e.g. with `_db()` and `_db()`) actually correct?**
  _`migrate()` has 54 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `LLMResponse` (e.g. with `_CountingClient` and `_FakeConnection`) actually correct?**
  _`LLMResponse` has 22 INFERRED edges - model-reasoned connections that need verification._
- **What connects `homelib applications: api, ui, ingest.`, `FastAPI service — the single contract every consumer talks through.`, `HTTP gate for the shared Cloud demo's per-principal daily LLM cap.` to the rest of the system?**
  _1419 weakly-connected nodes found - possible documentation gaps or missing edges._