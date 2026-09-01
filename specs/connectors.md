# spec: connectors — lawful catalog federation (“Forbidden Stacks”)

**Implemented by:** WP05. **Consumed by:** Discover, Mentor catalog tools.
**Product:** §5.11. **Not:** Anna’s Archive, Sci-Hub, LibGen (ADR-008).

## Purpose

Search lawful providers. Show unique-work counts, approximate per-provider
counts marked `~`, and “Open lawful source” when HomeLib must not redistribute.

## Public interface

```python
class ConnectorName(StrEnum):
    OPEN_LIBRARY = "open_library"
    STANDARD_EBOOKS = "standard_ebooks"
    GUTENBERG = "gutenberg"

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

Capstone: live Open Library first (v1 catalog snapshot is the fixture).
Standard Ebooks and Gutenberg may stay fixture-backed if live smoke is late
(cut order). One live smoke per enabled provider **outside CI**.

## Data contracts (field-level)

Timeouts degrade; they do not fail the whole Discover page (v1 lesson:
degraded-200). Unique count is **not** the sum of provider counts
(`test_unique_count_not_provider_sum`). Dedup keeps attributions
(`test_dedup_keeps_attributions`).

CI: no network. Fixtures under `data/` / test dirs only.

## Error/degradation behavior

- Provider timeout → that connector omitted, `degraded: true` on the
  Discover payload, others still shown (`test_timeout_degrades_not_fails`).
- Banned host in a connector URL → refuse to fetch; test grep.
- Paid/proprietary catalogs are out of schema this week (ADR-010).

## Named red tests

- `test_dedup_keeps_attributions`.
- `test_timeout_degrades_not_fails`.
- `test_unique_count_not_provider_sum`.
- `test_ambiguous_editions_never_merge`.

## Verify

```
uv run pytest -k 'connector or dedup_keeps or unique_count_not' -v
```
