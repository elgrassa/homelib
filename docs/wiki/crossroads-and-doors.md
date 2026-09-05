# Crossroads and doors

The Crossroads is the UI's only navigation: one Streamlit page, a door grid (and, since PR-D, the rotunda above it), and one renderer per door. The door set lives in one place — `CROSSROADS_DOORS` in `apps/ui/view_model.py` — and `DOOR_RENDERERS` in `apps/ui/app.py` must cover it exactly (`test_every_door_has_a_renderer_and_vice_versa`). Every door talks to the API through `HomelibClient`; none imports a store.

## Door map

```mermaid
flowchart LR
    X((Crossroads<br/>st.session_state door)) --> Ask
    X --> Mentor
    X --> Roadmap
    X --> CT[Coffee Table]
    X --> Shelf
    X --> Obs[Observatory]
    X --> Proj[Projection]

    Ask -->|client.ask| A1[POST /v1/ask]
    Ask -->|expand citation| A2[GET /v1/blocks/id]
    Ask -->|thumbs| A3[POST /v1/feedback]
    Mentor -->|client.mentor_intake| M1[POST /v1/mentor/intake]
    Roadmap -->|client.build_roadmap| R1[POST /v1/roadmap]
    CT -->|client.get_playlist / add_playlist_item| C1[GET,POST /v1/playlists/current…]
    CT -->|client.save_progress| C2[POST /v1/progress]
    Shelf -->|client.list_books| S1[GET /v1/books]
    Obs -->|client.get_observatory| O1[GET /v1/observatory]
    Proj -->|client.get_block| P1[GET /v1/blocks/id]

    classDef door fill:#fffaf0,stroke:#8a5b13,color:#241c16;
    class Ask,Mentor,Roadmap,CT,Shelf,Obs,Proj door;
```

| Door | Renderer | What it proves for the rubric |
|---|---|---|
| Ask | `render_ask_tab` | Retrieval flow + cited answer + feedback (criteria 2, 7) |
| Mentor | `render_mentor_tab` | Agentic intake proposing a path (criterion 12) |
| Roadmap | `render_roadmap_tab` | Catalog tool + ordered steps; unreachable until PR-B wired it |
| Coffee Table | `render_coffee_table_tab` | Persistent per-principal state; demo isolation (`X-Demo-Session`) |
| Shelf | `render_library_tab` | Ingestion readout: books / blocks / chunks / format (criterion 6) |
| Observatory | `render_observatory_tab` | ≥5 charts + feedback on one URL (criterion 7) |
| Projection | `render_projection_tab` | One-page reader with progress save |

## How a door opens

```mermaid
sequenceDiagram
    participant U as Reviewer
    participant R as Rotunda (inline st.html)
    participant S as Streamlit app.py
    participant V as view_model
    U->>R: click side door → room rotates
    U->>R: Enter (a href="?door=Ask", same document)
    R->>S: parent navigation ?door=Ask
    S->>V: door_from_query(params, current, CROSSROADS_DOORS)
    V-->>S: "Ask" (unknown values keep the current door)
    S->>S: session_state["door"] = normalize_door("Ask")
    S->>S: DOOR_RENDERERS["Ask"](client)
    Note over U,S: The static button grid beneath the room does the same<br/>without JavaScript — animation is never the only way in.
```

Rules that keep this honest:

- Adding a door = one tuple entry + one dict entry + a line of copy in `apps/ui/rotunda.py`. The parity test fails on any half-done addition.
- `normalize_door` raises on unknown labels; `door_from_query` never does — a stale `?door=` link keeps the current door.
- The rotunda's HTML fixture (`docs/mockups/`) had six named wings and a regex "search". Neither shipped: the doors are the product's, and retrieval belongs to the Ask door (`specs/rotunda.md`).
