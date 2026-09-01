# HomeLib v2 mockups — UX source of truth

Owner-attached stills for WP08/WP09. Binary images are allowed in this PR. Do not invent new art. The standalone HTML prototype is first in the cut order (`docs/plan-v2.md` §0.5 / product §13) and is kept here as a reference artifact, not as a shipped UI.

Audio/voice in the mentor still is **Coming soon** (ADR-009): schema may reserve columns; the capstone does not ship TTS/STT.

Apple Foundation Models in the topology diagram are later/optional. This week's Mac-home preferred runtime is LM Studio; Ollama is the reviewer Compose runtime. The diagram is a home-topology metaphor, not a capstone-week requirement to ship Apple FM.

Near-identical ChatGPT exports were byte-identical (same MD5); one file is kept per distinct frame.

| File | Journey |
|---|---|
| `00-home-topology.png` | Home topology: iPad/phone browser → Streamlit on a home Mac ↔ SQLite + FTS/vector ↔ model; Streamlit → projector. Metaphor only — see ADR-006. |
| `01-library-crossroads-wing.jpg` | Library Crossroads / AI Engineering wing bookshelves (RAG, Agents, Evaluation, LLM Systems, AI Careers). Deduped three identical exports. |
| `02-projection-reader.jpg` | Projection / two-page reader (chapter 3 Evaluation Loops, citations `[1]`/`[2]`, provenance sidebar). Deduped two identical exports. |
| `03-coffee-table-path.jpg` | Coffee Table / AI Engineering path (five stages). Deduped two identical exports. |
| `04-explore-rotunda-query.jpg` | Explore rotunda: query opens the Agents wing. Deduped two identical exports. |
| `05-rotunda-doors.jpg` | Rotunda “infinite academic library” doors (RAG / Agents / Evaluation / Vector Search / Monitoring / Systems). Deduped three identical exports. |
| `06-crossroads-rag-doors.jpg` | Library Crossroads doors with RAG as the focal door (chunking / embeddings / RAG / reranking / citations / agentic RAG). |
| `07-mentor-session-voice.jpg` | Mentorship Session (voice + text, citations, live transcript). Voice is Coming soon — ADR-009. Deduped two identical exports. |
| `homelib-magic-library-standalone.html` | Cut-first HTML discovery prototype (rotating doors + topic search). sha256 `693888a9d320b1479d7adf6eb103ce56db9eb805894cbfbc66f5a3d6dc678869`. Schema draft: `specs/data-model.md`. |
