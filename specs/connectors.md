# spec: connectors — lawful catalog federation (“Forbidden Stacks”)

**Implemented by:** WP05 + live Discover slice. **Consumed by:** Discover
(`GET /v1/resources?source=discover`), Shelf UI catalog search.
**Product:** §5.11. **Not:** Anna’s Archive, Sci-Hub, LibGen (ADR-008).
Google Books / Hardcover are **discovery metadata only** — never corpus ingest.

## Purpose

Search lawful providers. Show unique-work counts, approximate per-provider
counts marked `~`, and “Open lawful source” when HomeLib must not redistribute.

## Public interface

```python
class ConnectorName(StrEnum):
    OPEN_LIBRARY = "open_library"
    STANDARD_EBOOKS = "standard_ebooks"
    GUTENBERG = "gutenberg"
    GOOGLE_BOOKS = "google_books"
    HARDCOVER = "hardcover"

class ConnectorHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_key: str                 # stable merge key when unambiguous
    title: str
    authors: list[str]
    provider: ConnectorName
    provider_url: str
    full_text_available: bool
    rights_status: str
    approximate_count_member: bool
```

**Live (default):** Open Library `search.json` + Gutendex (Gutenberg catalog).
Google Books volumes API when `GOOGLE_BOOKS_API_KEY` is set. Hardcover GraphQL
search when `HARDCOVER_API_TOKEN` or `HARDCOVER_API_KEY` is set. Standard
Ebooks stays fixture-backed. **Fixture mode:** `HOMELIB_CONNECTOR_MODE=fixture`
(CI). One live smoke per keyed provider **outside CI**.

Open Library and Google Books always set `full_text_available=False` even when
a preview exists — HomeLib does not treat those APIs as a reading corpus.
Gutenberg may set `full_text_available=True` when Gutendex reports plain text
and `copyright=false` (lawful source link to gutenberg.org, not local ingest).

## Data contracts (field-level)

Timeouts degrade; they do not fail the whole Discover page (v1 lesson:
degraded-200). Unique count is **not** the sum of provider counts
(`test_unique_count_not_provider_sum`). Dedup keeps attributions
(`test_dedup_keeps_attributions`).

CI: no network. Fixtures under `packages/homelib-rag/tests/fixtures/connectors/`.

## Error/degradation behavior

- Provider timeout / HTTP failure → that connector omitted, `degraded: true` on the
  Discover payload, others still shown (`test_timeout_degrades_not_fails`).
- Google Books / Hardcover omitted when API key unset (not an error).
- Banned host in a connector URL → refuse to fetch; test grep.
- Paid/proprietary catalogs beyond these discovery APIs stay out of schema this week (ADR-010).

## Named red tests

- `test_dedup_keeps_attributions`.
- `test_timeout_degrades_not_fails`.
- `test_unique_count_not_provider_sum`.
- `test_ambiguous_editions_never_merge`.
- `test_open_library_live_maps_metadata_only_never_full_text`.
- `test_gutenberg_live_maps_provider_url_and_full_text_when_plain_text`.
- `test_google_books_live_maps_infolink_never_claims_full_text`.
- `test_hardcover_live_maps_slug_url_metadata_only`.

## Verify

```
uv run pytest -k 'connector or dedup_keeps or unique_count_not or live_maps' -v
```

## Live provider notes

- **Identify:** `User-Agent: HomeLib/<version> (<contact>)` — contact from
  `HOMELIB_CONTACT` when set; otherwise repo URL. `fetch_catalog.py`'s UA is
  separate (snapshot ingest).
- **Open Library:** ≤1 req/s unidentified; never bulk-harvest via search.
- **Google Books:** official `volumes?q=` with API key. Discovery/infoLink only —
  still banned for catalog snapshot / corpus redistribution (ADR-002).
- **Hardcover:** `POST https://api.hardcover.app/v1/graphql` with
  `authorization: Bearer <token>`; search query only (no mutations, no review
  ingest into Ask RAG).
- **Fallback:** fixture mode for CI/offline; live timeouts degrade the payload.
