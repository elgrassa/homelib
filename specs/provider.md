# spec: provider — `LLMProvider` seam

**Implemented by:** WP06 (generation paths); health wiring may land earlier.
**Consumed by:** ask, mentor intake, paths, rewrite, agent tools, `/health`.
**Product:** §7.2. v1 `OpenAICompatibleClient` is the incumbent implementation.

## Purpose

Cloud, LM Studio, Ollama and a future Apple adapter share one application-level
contract. Feature detection (`supports_tools`, `supports_structured_output`)
is explicit so a demo cloud model that cannot tool-call degrades to a
non-tool path instead of hanging or inventing function-call JSON.

## Public interface

```python
class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage]
    max_tokens: int
    timeout_seconds: float
    tools: list[ToolSchema] | None = None
    response_schema: type[BaseModel] | None = None   # structured output, if supported

class GenerationDelta(BaseModel):
    text: str
    done: bool

class GenerationResult(BaseModel):
    text: str
    tool_calls: list[ToolCall] | None
    tokens_prompt: int
    tokens_completion: int
    raw_json: dict | None            # provider payload; never mixed into public API models

class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str                    # "managed"|"openai_compatible"|"apple_future"
    model: str
    reachable: bool                  # never key material, never redacted-but-present key

class LLMProvider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...
    def stream(self, request: GenerationRequest) -> Iterator[GenerationDelta]: ...
    def health(self) -> ProviderHealth: ...
    def supports_tools(self) -> bool: ...
    def supports_structured_output(self) -> bool: ...
```

Implementations:

- `ManagedCloudProvider` — public demo; app-owner key in secrets only.
- `OpenAICompatibleProvider` — LM Studio, Ollama, BYOK (`LLM_BASE_URL`).
- `AppleFoundationProvider` — reserved, disabled, Coming soon (ADR-006).

Keys live only in environment / Streamlit secrets. `/health` and Observatory
see `ProviderHealth` booleans.

## Data contracts (field-level)

```
supports_tools               bool   # if False, agent loop must not send tools=
supports_structured_output   bool   # if False, parse text → Pydantic; one bounded repair
raw_json                     dict   # vendor body; public request models extra="forbid"
max_tokens                   int    # answers 400; paths/roadmap 1600 (v1 truncation lesson)
timeout_seconds              float  # Compose default 300; demo cloud may use 90
```

Tool allowlist (product §7.7): `search_library`, `get_block`, `get_resource`,
`propose_playlist`, `build_path`. Arguments are typed. Mutating tools create
**proposals** until the user confirms (Coffee Table / path accept).

v1 tool names (`search_shelf`, `search_catalog`, `build_roadmap`, `get_block`)
remain the live implementation until WP06; the allowlist above is the v2
target. Do not ship both under the same OpenAPI operation.

## Error/degradation behavior

- Unreachable provider → `health().reachable is False`; `/v1/ask` and
  intake return **200** + `degraded: true` (never 500). Search Exact/Keyword/
  Semantic/Smart still work with the LLM offline.
- `supports_tools() is False` → skip the tool loop; retrieve first, then one
  generate call. Do not emit placeholder tool-call JSON.
- `supports_structured_output() is False` → JSON-in-text + one repair, then
  fail-closed (v1 roadmap lesson).
- Timeout / max-tokens overrun → degraded response; never persist placeholder
  output as an accepted artifact.
- Vendor SDK imports live in **one** wrapper module.

## Named red tests

- `test_health_never_leaks_key_material` — body contains no substring of
  `LLM_API_KEY` (port from v1).
- `test_supports_tools_false_skips_tool_payload`.
- `test_unreachable_provider_ask_returns_200_degraded`.
- `test_apple_provider_is_disabled_by_default`.
- `test_search_with_llm_unreachable` — Exact/Keyword still return hits.

## Verify

```
uv run pytest -k 'provider or supports_tools or health_never_leaks' -v
```
