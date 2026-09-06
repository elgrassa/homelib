# spec: audio — capabilities and one lawful preview

**Implemented by:** WP09 preview only. **ADR-009:** full TTS/STT/Silver
Memory are Coming soon. **Consumed by:** `GET /v1/audio/capabilities`.
**ADR-010:** no production audio / licence tables this week.

## Purpose

Tell the client whether a bundled public-domain preview exists. Never imply
generation is available. Apple Speech APIs are not Foundation Models
(product §5.10).

## Public interface

```python
class AudioCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edition: str                    # "demo"|"selfhosted"
    preview_available: bool
    can_generate: bool              # False this week
    reason: str | None              # e.g. "Coming soon (ADR-009)"
    preview_resource_id: str | None
```

`can_generate_audio` on a rights row is independent: even if true on a
public-domain book, generation is still off until post-capstone.

## Data contracts (field-level)

At most one bundled preview asset in the seed. `listen_progress` table and
columns exist (`specs/progress.md`); `POST kind=listen` may persist rows but
no player consumes them this week (ADR-009).

Microphone / STT: not in the public demo.

## Error/degradation behavior

- `POST` generate-audio-style routes must **not exist** this week (no silent
  200). If a stub is added, it returns **501** + Coming soon.
- Capabilities never include file paths or signing keys.

## Named red tests

- `test_audio_capabilities_can_generate_is_false`.
- `test_no_generate_audio_route_in_openapi` — until a later WP; for now
  the live snapshot stays v1 (no audio path). Pin when the route is added.

## Verify

```
uv run pytest -k 'audio_capabilities or can_generate_is_false' -v
```

## On-device Listen in Projection (iPadOS)

- **Shape:** no server TTS. Projection ships a chrome-free stage for **Speak
  Screen**, plus a clean article server on UI `:8502` (`/read/{book_id}`) for
  Safari **Listen to Page**. `GET /v1/audio/capabilities` stays
  `can_generate=False`.
- **Official preview (demo default):** Pottermore Ukrainian HP PDFs are
  iframe/open-link only — speech is Safari Listen to Page on their `bookN/`
  reader, not HomeLib synthesizer.
- **Scope:** shelf text is the public-domain seed; Pottermore is never ingested
  (ADR-008).
