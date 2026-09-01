# spec: rights — fail-closed gate before index and audio

**Implemented by:** WP03 (index gate), WP05 (connector normalization).
**ADR-008.** Product §6.2. **Consumed by:** ingest, scene search, ask, audio.

## Purpose

Unknown or ambiguous rights must not put full text into RAG. Metadata may
still be searchable as metadata. The UI explains a restriction; it does not
silently drop the row.

## Public interface

```python
class RightsStatus(StrEnum):
    PUBLIC_DOMAIN = "public_domain"
    LICENSED_BUNDLE = "licensed_bundle"     # seed corpus with recorded licence
    METADATA_ONLY = "metadata_only"
    UNKNOWN = "unknown"                     # fail closed for full text
    FORBIDDEN = "forbidden"                 # banned source; never store full text

class RightsManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    source_url: str
    title: str
    author: str
    edition: str | None
    retrieved_at: datetime
    content_hash: str
    license: str
    license_url: str | None
    rights_status: RightsStatus
    decision_basis: str
    can_index_text: bool
    can_generate_audio: bool
    can_bundle_demo: bool
```

## Data contracts (field-level)

Unknown ⇒ `can_index_text=false`, `can_generate_audio=false`. Metadata-only
rows may appear in Discover (`GET /v1/resources?source=discover`).

Banned sources (grep-enforced, carry v1 Kaggle test; WP03 extends names):
Kaggle, Google Books, Goodreads, Anna’s Archive, Sci-Hub, LibGen,
DataTalks.Club course FAQ corpus.

Dedup (product §6.3): DOI → ISBN → provider mapping → title+author+year;
ambiguous editions **never** merge; attributions survive a merge.

## Error/degradation behavior

- `UNKNOWN` / `FORBIDDEN` full text offered to the indexer → skip + log;
  `test_unknown_rights_fail_closed`; `test_metadata_only_never_indexed`.
- Ask/search that would retrieve a non-indexable row cannot see its chunks.
- Audio generate when `can_generate_audio=false` → **403**.
- Demo ingest of user paths/URLs → **403** (`specs/editions.md`).

## Named red tests

- `test_unknown_rights_fail_closed`.
- `test_metadata_only_never_indexed`.
- `test_ambiguous_editions_never_merge` (WP05).

## Verify

```
uv run pytest -k 'rights or metadata_only_never or banned' -v
```
