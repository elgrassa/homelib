# HomeLib — detailed issues and Zoomcamp 2026 alignment

Reviewed 2026-09-09. Targets: [public demo](https://homelib.streamlit.app/), public source, local repository, committed evaluation artifacts, and official course materials. This report supplements [the live audit](cloud-audit-2026-09-09.md), which contains exact prompts, observations, timings and trace IDs.

## Assessment

Course scope: exclusively [LLM Zoomcamp 2026](https://github.com/DataTalksClub/llm-zoomcamp/tree/main/cohorts/2026), including its modules, homework, workshop and linked capstone guidelines. Requirements from the 2024 and 2025 cohorts are excluded. Product issues are distinguished from course-coverage gaps; not every homework technique is a capstone requirement.

HomeLib demonstrates a working cited RAG application. Its largest gaps are incomplete reading/learning workflows, unreliable Mentor outcomes, a defective evaluation gate, and inconsistent release/evaluation evidence. Missing course-brand frameworks are not the problem.

### Status as of 2026-09-09 (audit stack)

| ID | Status |
|---|---|
| E01, E03 | **Closed on Forgejo tip** (named-column retrieval parse + production faithfulness). |
| E02, E04 | **Shipped in stack** (`--from-run` + CI archive `evals.gate` step). Treat E04 “wired” as proven only after that CI step is green. |
| E05–E09, R06 | **Docs reconciled** in `EVAL.md`, `docs/course-map.md`, `docs/evidence.md` (30 vs 10; passage 0.638 vs book 0.906; cosine = chunk overlap; citation N=1; chunk 6/18 / 73 q). |
| S01–S03, W01–W04, S06/S07/W07/W08 | **Shipped in stacked code PRs** (cache, resume, accept, mentor taxonomy, scene/copy). |
| R01, R03–R05, R07–R08 | **Owner verification** — Cloud redeploy/build id, Observatory populate, judged relevance, cost percentiles, cold-clone at submission SHA, real narrow viewport. Not claimed done from this stack. |
| E07 | Separate research pass if pursued (human multi-label GT). |

Evidence labels: **Live** = observed in this audit; **Source** = implementation inspected, not a reproduced Cloud failure; **Recorded** = repository measurements or historical checks; **Unverified** = acceptance evidence still required. P1 means fix before claiming the affected workflow or quality gate is reliable; P2 means material product/evidence gap; P3 means polish or optional scope. No P0 outage was established. A source finding may already differ from the deployed app.

## Issues and closure criteria

### Evaluation and answer reliability

| ID | Priority / evidence | Issue and impact | Acceptance criterion |
|---|---|---|---|
| E01 | P1 / Source, reproduced parser | `justfile:138` parses the winner row incorrectly. Captured groups are `235`, `0.638`, `0.906`; the recipe supplies hit rate **235** and MRR **0.906**, whereas the actual hit rate is **0.638** and MRR **0.572**. A regression can receive a false green result. | Read named metrics from structured results; reject rates outside 0–1. A deliberately worse fixture must fail and the current valid fixture must report the actual values. |
| E02 | P1 / Source | The same recipe hard-codes judge faithfulness to **1.9** and reads committed retrieval results. It does not measure current code or parse current judge output. | Distinguish checking an archived report from evaluating current code. Load measured judge results with run identity; demonstrate a lower measured score fails. |
| E03 | P1 / Source | `evals/llm_eval.py::_judge_metrics` gates the bake-off winner rather than the production variant. A challenger can mask deterioration in the variant users receive. | Gate the deployed variant independently; retain challenger rankings as experiment results. A production regression must fail even when a challenger improves. |
| E04 | P2 / Source | The evaluation gate is not wired into Forgejo CI. Unit-test success therefore does not establish retrieval/answer-quality protection. Full evaluation scripts do exist; this is not an absence of evaluation. | Define a repeatable quality-check workflow and budget, attach fresh run provenance, and prove a deliberate quality regression stops that workflow. |
| E05 | P2 / Recorded | Documentation describes 30 questions per prompt arm and an inconclusive experiment; the latest `llm_eval.md` has **10 per arm**, names `stepwise` winner, and gives production faithfulness 2.60, relevance 2.90, citation quality 2.30, with 1/10 citation-free answers. Historical repeated runs may justify retaining production, but the current presentation does not explain the differing runs. | Publish separate dated runs, sample IDs, model/provider, prompt and code versions; reconcile the production decision with the latest experiment. Do not treat citation-free answers automatically as hallucinations: legitimate abstentions are included. |
| E06 | P2 / Recorded | Passage retrieval hit@5 is **63.8%**, despite book hit@5 of **90.6%**. The latter is not answer accuracy. Weak book slices include Meditations, Emerson and Franklin. | Report both metrics clearly, inspect misses and alternative valid passages, then evaluate improvements on a held-out set. |
| E07 | P2 / Recorded | Generated questions and one labelled chunk per question do not adequately cover user intents such as inventory, genre recommendations, exact scenes, out-of-scope questions and Mentor planning. Alternative correct passages can count as misses. | Add human-reviewed labels and multiple acceptable evidence blocks where appropriate; report intent-level results, including abstention correctness. |
| E08 | P2 / Recorded | Answer cosine similarity uses the reference chunk, not a curated ideal answer. Citation-precision evidence is tiny; the judge is not calibrated, and the evaluation documentation still contains unfinished probe/example fields. | Label cosine as a semantic-overlap proxy; calibrate a human-reviewed judge subset and measure citation support plus unsupported claims on a meaningful sample. Complete or remove placeholders. |
| E09 | P2 / Recorded | The chunk-size experiment covers 6 of 18 books and 73 questions, with 162 excluded. Different configurations trade hit rate against MRR and token count; this does not establish a universal best chunk size. | State the restricted coverage and selection rule; extend to representative books before making corpus-wide superiority claims. |

### Cache, sessions and reader continuity

| ID | Priority / evidence | Issue and impact | Acceptance criterion |
|---|---|---|---|
| S01 | P1 / Source | `apps/store/answer_cache.py:49` keys on question, arm, model and answer-prompt hash. It omits `k`, rewrite configuration and corpus/index identity. `apps/api/main.py` looks up the cache before rewriting/retrieval. A changed request can receive a previous answer with different retrieval semantics. | Include result-affecting inputs and a corpus/config version in cache identity. Demonstrate changed `k`, rewrite mode and corpus version do not reuse incompatible results. |
| S02 | P2 / Source | Cached responses retain original token counts and log those counts again, although the hit performs no new generation. Aggregated token totals can be mistaken for actual consumption. | Separate actual generated tokens from tokens represented by cached answers or explicitly label the estimate. Cache hits should contribute zero newly generated tokens. |
| S03 | P1 / Live + Source | Saving Walden progress reports success, but leaving Projection and returning opens Acres of Diamonds at Page 1. This establishes broken resume UX, not a proven lost database write. The client has save progress but no corresponding resume/read integration. | Restore the selected book and position after navigation; retrieve saved progress when entering the reader. Explicit passage links should override the previous position deliberately. |
| S04 | P2 / Unverified | Refresh, browser reopen, session expiry and server restart persistence were not validated. A transient Streamlit session alone does not establish returning-user persistence. | Define the intended lifetime, restore an opaque client identity when appropriate, load that identity's saved progress, and test refresh/reopen/expiry behavior. |
| S05 | P2 / Unverified | Cross-user separation of reading progress and Coffee Table was not exercised with two independent browser sessions. | User A's changes must not appear for B; repeat after navigation and refresh. Public-corpus answer caching is a separate concern from user-specific state. |
| S06 | P2 / Live | Scene search returns the correct Walden block, but labels it `T. CAREW`, repeats the same block among five results and previews unrelated text. | Show the actual section/book title, deduplicate by block, and place the matching sentence in the preview. |
| S07 | P2 / Live | A scene opens a roughly 32,600-character block. Projection reaches the correct block but does not establish precise sentence/offset navigation; “Page” labels represent extracted blocks. | Highlight/scroll to the passage, retain a stable offset where supported, and label block/section navigation honestly when source page numbers do not exist. |

### Learning and discovery workflows

| ID | Priority / evidence | Issue and impact | Acceptance criterion |
|---|---|---|---|
| W01 | P1 / Live | Mentor refuses the economics/division-of-labour goal despite Ask retrieving relevant Adam Smith evidence. Another stoicism request succeeds. This is inconsistent behavior; the exact backend failure was not diagnosed. | Reproduce the economics request with traces, distinguish retrieval, parsing, round-budget and validation failures, and return an evidence-supported plan or an actionable explanation. |
| W02 | P2 / Source + Live | Several Mentor failure paths collapse into a generic insufficient-sources message. A user cannot tell a genuine corpus gap from a generation/validation failure. | Preserve a safe failure category and useful next action; keep detailed technical context in traces. |
| W03 | P2 / Live | Generated Mentor and Roadmap plans have no visible accept/save action or path into Coffee Table/reading. Users receive a plan but cannot continue it as a persistent workflow. | Accept a plan, save ordered items for the current user, open an available text, and show a catalog destination for metadata-only works. |
| W04 | P2 / Live | Roadmap recommendations lack direct book/catalog links. Coffee Table supports adding and retaining a queued item but lacks visible read/resume, status and reorder controls. | Connect recommendations to available destinations and support the intended queue lifecycle. Validate remove as well; it was not exercised here. |
| W05 | P2 / Live | Ask's romance request returns inventory and a no-title/author-match explanation, whereas Discover finds romance catalog records. Safe fallback works, but it does not satisfy the recommendation intent. | Route or link the user to filtered catalog discovery; distinguish metadata recommendations from recommendations justified by full text. |
| W06 | P2 / Live + Unverified | No tool-use caption appeared for the successful Mentor run. That does not prove the agent is absent: context is preloaded and calls can be optional. A live tool-calling demonstration remains missing. | Capture one genuine tool-using request with calls, rounds and grounded output; document which door is agentic. Ask intentionally remains a single-shot RAG path. |
| W07 | P3 / Live | Plans start numbering at 0. Mentor duplicates Area/Wing text and cuts a quotation mid-word. | Use user-facing numbering from 1; remove duplication and truncate at sensible boundaries with access to the complete source. |
| W08 | P3 / Live | Official-preview copy promises an internal two-page reader while the deployed view directs users to external publisher pages. | Make the copy match available behavior; verify publisher destinations before claiming they work. |

### Release, monitoring and acceptance evidence

| ID | Priority / evidence | Issue and impact | Acceptance criterion |
|---|---|---|---|
| R01 | P1 / Live + Source | Cloud behavior differs from the current public UI: large leading rotunda and missing starters versus body-first layout and collapsed navigation in source. Exact deployed SHA is unknown. | Expose a build identifier and verify the owner-deployed revision against source. Recheck existing UI fixes on that revision. |
| R02 | P2 / Live | Feedback disables its controls, but no durable acknowledgement appeared and no matching telemetry increment was verified. | Show a clear submitted state and demonstrate one stored vote appears in the relevant monitoring aggregate without duplication. |
| R03 | P2 / Live | Observatory shows nine sections and eight visualization containers, but judged relevance is empty and Vega extent/scale warnings occur. Container count is not proof of five functioning populated charts. | Exercise representative traffic and feedback; verify at least five meaningful populated charts and clean empty-data rendering. |
| R04 | P2 / Source + Live | Judged relevance requires an operator script and answer logging, which is off by default. A trace ID is shown, but a reviewer cannot drill into it in the UI. | Document the optional judge run and demonstrate one joined answer/judgment. Provide a practical trace inspection path; do not describe operator-run judging as automatic continuous monitoring. |
| R05 | P2 / Recorded | Cost/latency evidence mixes isolated Cloud observations and older local measurements. Cached 53 ms and uncached 1,920 ms are not a latency distribution; token estimates are not billed spend. | Publish cache-separated cold/warm measurements, sample size and percentiles; identify provider/model and pricing assumptions. |
| R06 | P2 / Recorded | Course-map and gap-report claims are stale or contradictory: 3 versus 4 prompt variants, 30 versus latest 10 samples, old missing-feature lists followed by completed fixes, and outdated homework assertions. | Publish a single current evidence table with dated historical sections, correct course links and a traceable submission revision. |
| R07 | P2 / Unverified | Prior container/cold-clone checks are historical, not a fresh reproduction of the submission snapshot. Embedding download does not pin an immutable model revision. | Run the documented setup at the chosen commit, record dependencies/data/model revisions, and verify one complete request. |
| R08 | P2 / Unverified | Narrow viewport override did not take effect. Mobile, keyboard/swipe interactions, quota exhaustion, cold-start resource limits and restart recovery remain untested. | Run a real narrow viewport and keyboard pass; separately exercise documented resource/quota recovery. Do not convert untested behavior into a pass or a reported defect. |
| R09 | P3 / Live | Door switches briefly show old content under the new door label, then settle correctly. | Avoid stale-body transitions or provide a clear pending state; confirm with an ordinary interactive recording. |

## User/client session contract

Reader selection and temporary UI state should belong to the user's session. Durable reading progress should be stored against that user's identity and loaded back into the UI. `st.session_state` can support navigation during a Streamlit session; it is not, by itself, a promise of persistence after refresh or reopening.

For an anonymous returning-reader feature, retain an opaque client identifier for the intended lifetime and use it to recover saved book/block/offset state. Choose explicitly whether another tab shares the identity. Test same-session navigation, refresh, reopening, expiry/reset and two independent users. The observed return to Acres of Diamonds is a restoration failure; the audit did not show that the SQLite save itself was lost.

## What works, with the scope of the evidence

- Public anonymous launch and all seven doors.
- Ask answers the Walden author and Adam Smith questions, with citations that resolve to supporting source text.
- Ask abstains on transformer training in Walden without inventing a citation in the tested case.
- Inventory fallback is fast and does not unnecessarily invoke an LLM for the tested catalog request.
- Discover returns two romance works with metadata-only labels and Open Library links; external destinations were not tested.
- Roadmap generates six structured management recommendations; Mentor generates a cited three-step stoicism plan.
- Scene search finds the exact Walden quotation; its reader action reaches the correct block.
- Reader Next and projector mode work. Save progress acknowledges success.
- Coffee Table add survives navigation and a repeated-add attempt leaves one visible row.
- Recorded retrieval evaluation covers four arms and 235 questions with no reported degraded arm. Hybrid reranking improves MRR from hybrid's 0.483 to 0.572, while their hit rates both remain 0.638.
- Source includes dlt ingestion, vector/lexical retrieval, RRF, cross-encoder reranking, rewriting, a tool-calling agent, OpenTelemetry and a SQLite exporter. These must not be reclassified as missing simply because some Cloud evidence is incomplete.

## Zoomcamp project alignment

The [official project criteria](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md) permit RAG, agents or both and explicitly permit alternative tools. SQLite, Groq, Streamlit and dlt are acceptable choices. The prohibited course FAQ corpus is not HomeLib's Gutenberg corpus. The table below assesses HomeLib's evidence, not a guaranteed peer-review score.

| Criterion | HomeLib assessment | Remaining evidence or gap |
|---|---|---|
| Problem description | Present | Keep promises aligned with actual reading/learning workflows. |
| Retrieval flow | Demonstrated live | Preserve cited and out-of-scope examples at the submission revision. |
| Retrieval evaluation | Four measured approaches | Repair gate; make passage versus book metrics explicit. |
| LLM evaluation | Four prompt arms and a second similarity method | Reconcile samples, winner and production choice; calibrate judge. |
| Interface | Streamlit and FastAPI | Resolve deployed-source drift and incomplete continuation flows. |
| Automated ingestion | dlt implementation and recorded checks | Reproduce on the submitted snapshot. |
| Monitoring | Feedback, logging and dashboard implemented | Verify vote persistence and five populated charts. |
| Containerization | Docker/Compose artifacts and historical evidence | Repeat a clean startup at the chosen commit. |
| Reproducibility | Extensive setup/evidence docs | Remove stale claims and pin run/model identities. |
| Hybrid / reranking / rewriting | All implemented and evaluated; rewriting remains off by measured choice | Explain the tradeoff; do not promise the rewriting point is guaranteed. |
| Cloud | Public deployment works | Publish and verify its revision. |
| Submission / peers | Owner actions remain | Record the final commit and complete the required peer reviews. |

The root submission link currently leads to the 2025 cohort project page. The 2026 platform could not be verified during this audit, so this report does not assert a 2026 deadline.

## Current cohort features versus HomeLib

The comparison below uses only the [2026 cohort](https://github.com/DataTalksClub/llm-zoomcamp/tree/main/cohorts/2026). Its README links the shared root capstone guidelines, which is why those guidelines are included in the project assessment. Older cohorts supply no additional requirements.

| Current material | HomeLib coverage | Gap or distinction |
|---|---|---|
| [01 Agentic RAG](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/cohorts/2026/01-agentic-rag/homework.md): search, context, token usage and function-calling loops | Explicit agent/tool loop on Mentor; normal RAG on Ask; token accounting | Live tool-using Mentor evidence needed. No requirement to replace the explicit loop with ToyAIKit. |
| [02 Vector Search](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/cohorts/2026/02-vector-search/homework.md): embeddings, cosine search and fusion | MiniLM, normalized SQLite vectors, pgvector path, lexical/vector/hybrid comparisons | HomeLib's Torch runtime differs from the homework ONNX runtime. Lightweight ONNX is an optional resource optimization, not a missing capstone criterion. |
| [03 Orchestration](https://github.com/DataTalksClub/llm-zoomcamp/tree/main/cohorts/2026/03-orchestration): Kestra, context and agent/workflow patterns | dlt covers HomeLib's ingestion pipeline | Does not establish full Kestra/multi-agent exercise coverage. Label it an architectural alternative; a valid capstone can omit unnecessary orchestration machinery. |
| [dlt workshop](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/cohorts/2026/workshops/dlt.md) | dlt ingestion and idempotent loading | The workshop's surrounding DuckDB/marimo/agent observability exercises are not all demonstrated by a dlt pipeline. Homework exists; blanket “no homework” language should be removed. |
| [04 Evaluation](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/cohorts/2026/04-evaluation/homework.md): generated questions, labels, hit rate/MRR and fusion sweeps | Four arms, 235 questions, book metrics and RRF sweep; judge and cosine experiments | Canonical homework exists. Repair the gate and separate curriculum exercise coverage from measured application quality. |
| [05 Monitoring](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/cohorts/2026/05-monitoring/homework.md): spans, token/cost attributes, timing and SQLite export | OpenTelemetry/custom exporter, query logs and Observatory | Demonstrate end-to-end span/feedback data and correct cache accounting; Grafana is not necessary for the SQLite demo. |
| [06 Best Practices](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/cohorts/2026/06-best-practices/README.md) | RRF plus separate cross-encoder reranking; rewriting experiment | Material is marked optional and uses older recordings. Elasticsearch/LangChain adoption is unnecessary; explain fusion versus reranking accurately. |
| Project example | API/UI/store/ingestion/evaluation/deployment architecture | Similar architecture alone does not validate a final release; use reproducible evidence. |

Missing audiobook/listen completion, Obsidian integration, broader format samples, incremental-ingestion acceptance and multilingual evaluation are product-backlog items. They are not automatically Zoomcamp blockers. Public-demo upload restrictions are intentional scope, not evidence that ingestion is absent.

## Recommended implementation order

1. Repair E01–E03 and add focused behavioral regression checks. Establish trustworthy measurements before making quality claims.
2. Resolve R01, identify the intended public build, and recheck existing fixes there. Deployment remains an owner action.
3. Fix S01–S05: compatible cache identity, truthful accounting, reader restoration and client/session acceptance.
4. Diagnose W01–W02, then connect plans to saved queues and reading through W03–W04.
5. Fix scene presentation, feedback acknowledgement and monitoring evidence.
6. Reconcile evaluation/course docs and run the submission-snapshot acceptance pass.

## Validation limits

The preceding live audit's focused UI/client suite passed **40 tests**. It was not a full CI run and was not rerun after concurrent tracked edits to answer/retrieval code appeared. This extension reproduced the gate's regular-expression captures without invoking its history-writing gate, inspected source and result artifacts, and checked official course pages. No application code was changed, no issue/PR was posted and no deployment was performed. Current uncommitted application edits are outside this report's validated snapshot.
