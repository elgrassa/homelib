# spec: agent-tools — `homelib_rag.agent`

**Implemented by:** WP-14 · **Consumed by:** `apps/api` (`/v1/ask`, `/v1/roadmap`), `roadmap.py`, `answer.py`, `mentor.py` (`run_agent`, Mentor path only, since 2026-09-06).
**v2 tool allowlist** (product §7.7, `specs/provider.md`): `search_library`,
`get_block`, `get_resource`, `propose_playlist`, `build_path`. v1 names below
remain live until WP06. Mutating tools create **proposals**.

## Purpose

An explicit function-calling loop over an OpenAI-compatible chat-completions
endpoint (Ollama `/v1` by default; a cloud endpoint is a drop-in override).
No LangChain: course module M1 teaches the loop itself, and a hand-rolled
loop keeps every tool call inspectable. The LLM chooses among four typed
tools; the loop drives the request→tool→result cycle and returns control once
the model produces a final answer with no further tool calls, or a bound is
hit.

## Public interface

```python
def search_shelf(query: str, k: int = 5) -> list[Hit]                       # Hit: specs/indexing.md
def search_catalog(query: str, subjects: list[str] | None = None) -> list[CatalogEntry]   # specs/core-models.md
# Dispatches to homelib_rag.sqlite_index.search_catalog when HOMELIB_SQLITE_PATH is set
# (ADR-004) — inside the function, so Deps.catalog_search, build_roadmap and
# _TOOL_FUNCTIONS all follow. run_agent's OWN default tool table still binds
# get_block to Postgres directly; it is on the Mentor request path since
# 2026-09-06 (homelib_rag.mentor.mentor_intake, POST /v1/mentor/intake) via
# its `tools=`/`tool_schemas=` injection seam, wired to Deps.get_block et al.
# so the loop stays store-safe — Ask (/v1/ask) stays single-shot and never
# calls run_agent (tests/test_repo_hygiene.py::test_run_agent_is_only_on_the_mentor_path).
def build_roadmap(interests: list[str], level: Level, goal: str) -> RoadmapResponse       # specs/api.md, specs/roadmap.md
def get_block(block_id: str) -> Block                                        # specs/core-models.md

TOOL_SCHEMAS: list[dict]          # the `tools=` payload sent to the chat endpoint

class ToolCallRecord(BaseModel):
    round: int
    tool_name: str
    arguments: dict
    result_summary: str            # truncated repr, never the raw stack trace
    error: str | None

class AgentResult(BaseModel):
    final_message: str
    tool_calls: list[ToolCallRecord]
    rounds_used: int
    degraded: bool

def run_agent(
    messages: list[ChatMessage],
    *,
    max_rounds: int = 6,
    client: OpenAICompatibleClient,
    tools: Mapping[str, Callable[..., Any]] | None = None,      # default: this module's _TOOL_FUNCTIONS
    tool_schemas: list[dict] | None = None,                     # default: this module's TOOL_SCHEMAS
    max_tokens: int = 400,
) -> AgentResult
```

## Data contracts (field-level)

`Hit` — defined in `specs/indexing.md`; not redefined here.
`CatalogEntry`, `Block` — defined in `specs/core-models.md`; not redefined here.
`RoadmapResponse` — defined in `specs/api.md`; not redefined here.

```
ChatMessage    role: "system"|"user"|"assistant"|"tool"
               content: str
               tool_calls: list[dict]|None      # assistant turns requesting tools
               tool_call_id: str|None            # tool-role reply correlation

ToolCallRecord round: int                        # 0-based agent round the call happened in
               tool_name: str
               arguments: dict                   # parsed JSON arguments as sent by the model
               result_summary: str                # bounded-length success summary
               error: str|None                    # set iff the tool raised or was unknown
```

`tools=` JSON-schema shape sent to the endpoint, one entry per tool
(OpenAI function-calling shape, verbatim for `search_shelf`):

```json
{
  "type": "function",
  "function": {
    "name": "search_shelf",
    "description": "Full-text search over the ingested book shelf.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string"},
        "k": {"type": "integer", "default": 5}
      },
      "required": ["query"]
    }
  }
}
```

The other three tools follow the same shape with their own `parameters`.

## Error and degradation behavior

- **Termination conditions:** the loop ends when (a) the model returns an
  assistant message with no `tool_calls` (`degraded=False`), or (b)
  `rounds_used == max_rounds` is reached without a final message
  (`degraded=True`, `final_message` is a synthesized "reached the round
  limit" notice — never a truncated silent cutoff).
- **Unknown tool requested:** the call is *not* dispatched. A `tool`-role
  message `"unknown tool: <name>"` is appended so the model can self-correct,
  and the round counts against `max_rounds`. If the model requests the same
  unknown tool name twice in a row, the loop terminates early with
  `degraded=True` rather than looping indefinitely.
- **Tool raises:** the exception is caught at the dispatch site, recorded in
  `ToolCallRecord.error` (message only, no stack trace, no secret material),
  and a compact `tool`-role error message is fed back to the model. The loop
  continues to the next round; a single tool failure never crashes the
  request.
- **Endpoint unreachable:** the client raises `LLMUnreachableError`, which
  propagates out of `run_agent` uncaught. The API layer (`specs/api.md`
  degradation contract) is the place this becomes a `200 degraded: true`
  response — `run_agent` itself does not swallow connectivity failures.

## Named red tests

- `test_tool_dispatch_scripted_llm` — a scripted fake LLM (no network) issues
  `search_shelf` then `search_catalog` then a final answer; assert each real
  Python tool function is invoked with the parsed arguments and its result is
  fed back as a `tool`-role message before the next model call.
- `test_max_rounds_terminates_degraded` — a fake LLM that always requests
  another tool call; assert the loop stops at exactly `max_rounds`,
  `degraded is True`, and no unbounded loop occurs.
- `test_unknown_tool_name_repaired_then_terminated` — a fake LLM requests a
  tool name absent from `TOOL_SCHEMAS` twice consecutively; assert the first
  attempt yields a corrective `tool`-role message and the second ends the
  loop with `degraded is True` without raising.
- `test_tool_exception_is_caught_and_reported` — one tool is monkeypatched to
  raise; assert `ToolCallRecord.error` is set, the loop continues, and no
  exception propagates out of `run_agent`.

## Verify

```
uv run pytest packages/homelib-rag/tests/test_agent.py -v
uv run pytest packages/homelib-rag/tests/test_agent.py -k "scripted_llm or max_rounds or unknown_tool or tool_exception" -v
uv run mypy --strict packages/homelib-rag/src/homelib_rag/agent.py
```
