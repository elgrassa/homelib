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

## Planned (not this capstone): on-device Listen in Projection

Recorded 2026-09-05 after the stakeholder review; **not built**, no route, no schema.

- **Shape:** the Projection door gets a "Listen" control that uses the reader's own browser voice (`window.speechSynthesis`, i.e. macOS/iOS/Android built-in TTS) through a small `components.v1.html` block. Nothing is generated or stored server-side; `GET /v1/audio/capabilities` keeps `can_generate=False`.
- **Scope:** public-domain blocks only (the seed corpus). Rights-gated resources never reach the synthesizer (ADR-008 fail-closed).
- **Prerequisite:** Projection must render real block text end to end (today it opens one block). That is the only change that would touch the OpenAPI snapshot, so it is sequenced after the readiness stack.
- **Why deferred:** ADR-009 stands; a voice feature that ships before the doors are green would trade against rubric rows 1–10.
