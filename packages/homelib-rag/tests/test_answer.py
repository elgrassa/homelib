"""Behavioural tests for `homelib_rag.answer` — see specs/answer.md.

No live Postgres, no live LLM: `_book_metadata` is monkeypatched (the DB
seam) and every LLM call goes through a scripted fake `OpenAICompatibleClient`
— never the real `openai` package's network path.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, ClassVar

import pytest
from homelib_rag.answer import (
    AskResponse,
    Citation,
    CitationValidationError,
    LLMResponse,
    LLMUnreachableError,
    LLMUsage,
    OpenAIClient,
    TokenUsage,
    _book_metadata,
    _degraded_response,
    _validate_citations,
    answer,
    default_llm_client,
)
from homelib_rag.models import Hit


class _ScriptedClient:
    """A scripted fake `OpenAICompatibleClient`. No network."""

    model = "fake-model"

    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: Any,
        *,
        tools: Any = None,
        response_format: Any = None,
        max_tokens: int = 400,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": list(messages),
                "tools": tools,
                "format": response_format,
                "max_tokens": max_tokens,
            }
        )
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _llm_json(answer_text: str, citations: list[dict[str, Any]]) -> LLMResponse:
    return LLMResponse(
        content=json.dumps({"answer": answer_text, "citations": citations}),
        usage=LLMUsage(prompt_tokens=42, completion_tokens=7),
    )


def _hit(chunk_id: str = "c1", book_id: str = "b1", text: str = "The fox jumps high.") -> Hit:
    return Hit(
        chunk_id=chunk_id,
        book_id=book_id,
        score=1.0,
        rank=1,
        text=text,
        section_path=["Chapter 1"],
        page=12,
    )


@pytest.fixture(autouse=True)
def _stub_book_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default DB seam stub: every test overrides this per-case if it cares
    about the exact metadata, otherwise gets a stable fixed mapping."""
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata",
        lambda book_ids: {bid: ("Test Book", ["Jane Doe"]) for bid in book_ids},
    )


# ── Named red tests ─────────────────────────────────────────────────────────


def test_citations_resolve() -> None:
    """Every Citation.chunk_id in a non-degraded response corresponds to one
    of the input hits' chunk_id values (specs/answer.md)."""
    hits = [_hit()]
    client = _ScriptedClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])

    result = answer("does it jump?", hits, client=client, arm_used="hybrid")

    assert result.degraded is False
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "c1"
    assert result.citations[0].chunk_id in {h.chunk_id for h in hits}


def test_answer_rejects_quote_not_in_chunk() -> None:
    """A fabricated quote not present in the cited chunk's text causes a
    degraded fallback instead of being passed through unchecked."""
    hits = [_hit(text="The fox jumps high.")]
    client = _ScriptedClient(
        [_llm_json("It flies.", [{"passage": 1, "quote": "the fox flies away"}])]
    )

    result = answer("does it fly?", hits, client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.citations == []


def test_citation_quote_present_verbatim_in_chunk() -> None:
    """For each citation in a non-degraded response, `quote` is a substring
    of the matching hit's text."""
    hits = [_hit(text="Four score and seven years ago.")]
    client = _ScriptedClient(
        [_llm_json("A famous opening.", [{"passage": 1, "quote": "seven years ago"}])]
    )

    result = answer("what's the opening line?", hits, client=client, arm_used="lexical")

    assert result.degraded is False
    for citation in result.citations:
        matching = next(h for h in hits if h.chunk_id == citation.chunk_id)
        assert citation.quote in matching.text


def test_llm_unreachable_returns_degraded_200() -> None:
    """The client raises a connection error; `answer()` returns a degraded
    `AskResponse` rather than raising or producing a 500."""
    hits = [_hit()]
    client = _ScriptedClient([LLMUnreachableError("connection refused")])

    result = answer("anything?", hits, client=client, arm_used="vector")

    assert isinstance(result, AskResponse)
    assert result.degraded is True
    assert result.citations == []
    assert result.arm_used == "vector"


def test_hallucinated_citation_triggers_degradation() -> None:
    """A citation to a source absent from `hits` never reaches the caller as
    trustworthy.

    The model no longer names a chunk_id — it names a passage number — so the
    fabrication this guards against is a number that was never offered. The
    old form of this test (an invented chunk_id string) is now unreachable by
    construction, which is the stronger outcome.
    """
    hits = [_hit(chunk_id="c1")]
    client = _ScriptedClient([_llm_json("Made up.", [{"passage": 7, "quote": "anything"}])])

    result = answer("what happened?", hits, client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.citations == []


def test_agent_dispatches_tools_with_scripted_llm_alias() -> None:
    """Sanity: this module's own scripted-client pattern (used across the
    agent-tools/answer/roadmap test suites) never touches the network."""
    hits = [_hit()]
    client = _ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])])
    result = answer("q", hits, client=client, arm_used="hybrid")
    assert result.answer == "ok"
    assert result.degraded is False


# ── Author-attribution hardening (the Ford/Roosevelt finding) ──────────────


def test_context_includes_authors_not_just_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """The prompt sent to the LLM must carry the book's authors, not just its
    title — the structural fix for the observed invented-author defect."""
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata",
        lambda book_ids: {"b1": ("My Life and Work", ["Henry Ford"])},
    )
    hits = [_hit(book_id="b1")]
    client = _ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])])

    answer("who wrote this?", hits, client=client, arm_used="hybrid")

    sent_prompt = client.calls[0]["messages"][1].content
    assert "Henry Ford" in sent_prompt
    assert "My Life and Work" in sent_prompt


def test_citation_book_title_never_taken_from_model_output() -> None:
    """`Citation.book_title` always comes from `_book_metadata`, never from
    anything the model put in its JSON — there is no field for it in the
    schema the model is asked to fill (`_RawCitation` has no book_title)."""
    hits = [_hit(book_id="b1")]
    client = _ScriptedClient(
        [
            LLMResponse(
                content=json.dumps(
                    {
                        "answer": "ok",
                        "citations": [
                            {
                                "passage": 1,
                                "quote": "fox jumps",
                                "book_title": "A Title The Model Made Up",
                            }
                        ],
                    }
                ),
                usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
            )
        ]
    )

    result = answer("q", hits, client=client, arm_used="hybrid")

    assert result.degraded is False
    assert result.citations[0].book_title == "Test Book"  # from the fixture's stub, not the model


# ── Degradation on metadata/LLM/parse failures ──────────────────────────────


def test_answer_degrades_when_book_metadata_lookup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_book_ids: list[str]) -> dict[str, tuple[str, list[str]]]:
        raise ConnectionError("db down")

    monkeypatch.setattr("homelib_rag.answer._book_metadata", _raise)
    client = _ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])])

    result = answer("q", [_hit()], client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.citations == []


def test_answer_drops_bare_integer_citations_without_full_degrade() -> None:
    """Groq has returned `citations: [1]` — keep the answer when objects remain."""
    hits = [_hit(text="I went to the woods because I wished to live deliberately.")]
    payload = {
        "answer": "Thoreau went to the woods.",
        "citations": [
            1,
            {"passage": 1, "quote": "I went to the woods"},
        ],
    }
    client = _ScriptedClient(
        [
            LLMResponse(
                content=json.dumps(payload), usage=LLMUsage(prompt_tokens=10, completion_tokens=5)
            )
        ]
    )

    result = answer("Who wrote Walden?", hits, client=client, arm_used="hybrid_rerank")

    assert result.degraded is False
    assert result.tokens.prompt == 10
    assert len(result.citations) == 1
    assert "woods" in result.citations[0].quote


def test_answer_degrades_on_unexpected_exception_from_client() -> None:
    client = _ScriptedClient([RuntimeError("boom")])

    result = answer("q", [_hit()], client=client, arm_used="hybrid")

    assert result.degraded is True


def test_answer_handles_empty_hits() -> None:
    client = _ScriptedClient([_llm_json("I don't have information on that.", [])])

    result = answer("q", [], client=client, arm_used="lexical")

    assert result.degraded is False
    assert result.citations == []


def test_degraded_response_preserves_latency_and_tokens_when_provided() -> None:
    result = _degraded_response(
        "hybrid",
        "citation quote 'x' does not appear in any of the passages provided",
        latency_ms=1234,
        tokens=TokenUsage(prompt=100, completion=40),
    )
    assert result.degraded is True
    assert result.degraded_reason == "citation_mismatch"
    assert result.citations == []
    assert result.latency_ms == 1234
    assert result.tokens.prompt == 100
    assert result.tokens.completion == 40
    assert result.arm_used == "hybrid"
    assert "try again" in result.answer.lower()


def test_degraded_response_defaults_zero_usage_without_llm_call() -> None:
    result = _degraded_response("hybrid", "LLM unreachable: boom")
    assert result.degraded is True
    assert result.degraded_reason == "llm_unreachable"
    assert result.latency_ms == 0
    assert result.tokens.prompt == 0
    assert result.tokens.completion == 0


def test_unexpected_llm_error_is_not_labelled_unreachable() -> None:
    """A client exception is not the same as the model being unreachable."""
    result = _degraded_response("hybrid", "unexpected LLM error: ValueError boom")
    assert result.degraded is True
    assert result.degraded_reason != "llm_unreachable"
    assert result.degraded_reason == "degraded"


def test_answer_retries_without_json_format_after_json_validate_failed() -> None:
    """Groq `json_validate_failed` must not stick on the first attempt when a
    plain chat retry can still produce valid JSON (inventory / refuse cases)."""
    hits = [_hit(text="by Henry David Thoreau")]
    client = _ScriptedClient(
        [
            LLMUnreachableError(
                "Error code: 400 - {'error': {'message': \"Failed to validate JSON.\", "
                "'code': 'json_validate_failed', 'failed_generation': ''}}"
            ),
            _llm_json("Henry David Thoreau", [{"passage": 1, "quote": "by Henry David Thoreau"}]),
        ]
    )

    result = answer("Who wrote Walden?", hits, client=client, arm_used="hybrid_rerank")

    assert result.degraded is False
    assert result.answer == "Henry David Thoreau"
    assert len(client.calls) == 2
    assert client.calls[0]["format"] == {"type": "json_object"}
    assert client.calls[1]["format"] is None
    assert client.calls[0]["max_tokens"] == 1200
    assert client.calls[1]["max_tokens"] == 1200


def test_answer_json_validate_failed_twice_returns_empty_degraded_for_ui_refuse() -> None:
    """Persistent Groq JSON-validate failure → degraded with empty answer so
    Ask #A1 (`format_ask_answer_body`) can render refuse + shelf counts."""
    err = LLMUnreachableError(
        "Error code: 400 - {'error': {'code': 'json_validate_failed', 'failed_generation': ''}}"
    )
    client = _ScriptedClient([err, err])

    result = answer("what do you have?", [_hit()], client=client, arm_used="hybrid_rerank")

    assert result.degraded is True
    assert result.answer == ""
    assert result.citations == []
    assert result.tokens.prompt == 0
    assert len(client.calls) == 2


def test_answer_malformed_after_json_retry_returns_empty_degraded() -> None:
    """Retry without response_format that still isn't `_RawAnswer` JSON must
    empty-degrade (not the generic try-again filler) for #A1."""
    client = _ScriptedClient(
        [
            LLMUnreachableError(
                "Error code: 400 - {'error': {'code': 'json_validate_failed', "
                "'failed_generation': 'max completion tokens reached before "
                "generating a valid document'}}"
            ),
            LLMResponse(
                content="not json at all",
                usage=LLMUsage(prompt_tokens=10, completion_tokens=5),
            ),
        ]
    )

    result = answer("what do you have?", [_hit()], client=client, arm_used="hybrid_rerank")

    assert result.degraded is True
    assert result.answer == ""


def test_answer_rate_limit_surfaces_clearer_degraded_message() -> None:
    client = _ScriptedClient(
        [LLMUnreachableError("Error code: 429 - {'error': {'code': 'rate_limit_exceeded'}}")]
    )

    result = answer("q", [_hit()], client=client, arm_used="hybrid")

    assert result.degraded is True
    assert "rate-limited" in result.answer.lower()
    assert result.citations == []


# ── _validate_citations unit tests ──────────────────────────────────────────


def test_validate_citations_raises_for_unknown_chunk_id() -> None:
    hits = [_hit(chunk_id="c1", text="hello world")]
    bad = [
        Citation(
            block_id="blk-1",
            chunk_id="does-not-exist",
            book_id="b1",
            book_title="T",
            section_path=[],
            page=None,
            quote="hello",
        )
    ]
    with pytest.raises(CitationValidationError):
        _validate_citations(bad, hits)


def test_validate_citations_raises_for_non_verbatim_quote() -> None:
    hits = [_hit(chunk_id="c1", text="hello world")]
    bad = [
        Citation(
            block_id="blk-1",
            chunk_id="c1",
            book_id="b1",
            book_title="T",
            section_path=[],
            page=None,
            quote="goodbye",
        )
    ]
    with pytest.raises(CitationValidationError):
        _validate_citations(bad, hits)


def test_validate_citations_passes_for_genuine_citation() -> None:
    hits = [_hit(chunk_id="c1", text="hello world")]
    good = [
        Citation(
            block_id="blk-1",
            chunk_id="c1",
            book_id="b1",
            book_title="T",
            section_path=[],
            page=None,
            quote="hello",
        )
    ]
    _validate_citations(good, hits)  # must not raise


# ── _book_metadata / OpenAIClient / default_llm_client seams ───────────────


def test_book_metadata_empty_list_returns_empty_dict() -> None:
    assert _book_metadata([]) == {}


def test_openai_client_wraps_transport_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient(base_url="http://localhost:1", api_key="x", model="m")

    def _raise(**_kwargs: Any) -> Any:
        raise TimeoutError("no route to host")

    monkeypatch.setattr(client._client.chat.completions, "create", _raise)

    with pytest.raises(LLMUnreachableError):
        client.chat([])


def test_openai_client_raises_on_empty_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient(base_url="http://localhost:1", api_key="x", model="m")

    class _EmptyResponse:
        choices: ClassVar[list[Any]] = []

    monkeypatch.setattr(
        client._client.chat.completions, "create", lambda **_kwargs: _EmptyResponse()
    )

    with pytest.raises(LLMUnreachableError):
        client.chat([])


def test_default_llm_client_is_a_singleton() -> None:
    assert default_llm_client() is default_llm_client()


def test_llm_timeout_seconds_env_var_overrides_default_timeout() -> None:
    """`_TIMEOUT_SECONDS` (module constant) is read from `LLM_TIMEOUT_SECONDS`
    at import time. Measured on the pure-compose stack: CPU-only Ollama
    generates at ~7.4 tok/s, so a real /v1/ask costs ~70s minimum — the old
    hardcoded 30s ceiling timed out on prefill alone, degrading every ask.

    Checked in a fresh subprocess rather than via `importlib.reload` in this
    process: reloading `homelib_rag.answer` here would mint a second
    generation of `LLMUnreachableError` (and every other class this module
    defines) that no longer `isinstance`-matches the one `apps/api/main.py`
    already imported at collection time, silently breaking its
    `except LLMUnreachableError` handlers for the rest of the test run.
    """
    default_run = subprocess.run(
        [
            sys.executable,
            "-c",
            "from homelib_rag.answer import _TIMEOUT_SECONDS; print(_TIMEOUT_SECONDS)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert default_run.stdout.strip() == "300.0"

    overridden_run = subprocess.run(
        [
            sys.executable,
            "-c",
            "from homelib_rag.answer import _TIMEOUT_SECONDS; print(_TIMEOUT_SECONDS)",
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "LLM_TIMEOUT_SECONDS": "12.5"},
    )
    assert overridden_run.stdout.strip() == "12.5"


def test_openai_client_forwards_tools_and_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient(base_url="http://localhost:1", api_key="x", model="m")
    captured: dict[str, Any] = {}

    class _Function:
        name = "lookup"
        arguments = "{}"

    class _ToolCall:
        id = "tc-1"
        type = "function"
        function = _Function()

    class _Message:
        content = "ok"
        tool_calls: ClassVar[list[_ToolCall]] = [_ToolCall()]

    class _Choice:
        message = _Message()

    class _Usage:
        prompt_tokens = 3
        completion_tokens = 4

    class _Response:
        choices: ClassVar[list[_Choice]] = [_Choice()]
        usage = _Usage()

    def _capture(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(client._client.chat.completions, "create", _capture)

    tools = [{"type": "function", "function": {"name": "lookup"}}]
    response_format = {"type": "json_object"}
    response = client.chat([], tools=tools, response_format=response_format)

    assert captured["tools"] == tools
    assert captured["response_format"] == response_format
    assert response.tool_calls is not None
    assert response.tool_calls[0]["function"]["name"] == "lookup"


def test_openai_client_chat_bounds_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bounds worst-case CPU generation time — a runaway completion should
    not turn the (now much longer) timeout into the only backstop. Measured
    answers run ~240 tokens; 400 leaves headroom."""
    client = OpenAIClient(base_url="http://localhost:1", api_key="x", model="m")
    captured: dict[str, Any] = {}

    def _capture(**kwargs: Any) -> Any:
        captured.update(kwargs)
        raise TimeoutError("no route to host")

    monkeypatch.setattr(client._client.chat.completions, "create", _capture)

    with pytest.raises(LLMUnreachableError):
        client.chat([])

    assert captured["max_tokens"] == 400


# ── Live-run regressions: measured against qwen2.5:7b-instruct, 2026-08-30 ──
#
# Every one of these was found by running the real answer path against the
# real corpus. Before the fix, 3 of 3 sampled questions degraded to the
# "I couldn't produce a verified answer" fallback — the headline feature was
# returning nothing usable, while the unit suite was fully green because
# every fake obligingly produced a perfect chunk_id and a byte-exact quote.


def test_citation_is_made_by_passage_number_not_by_chunk_id() -> None:
    """The model picks a passage; the code supplies the id.

    Asking a 7B model to echo a 16-hex chunk_id is asking it to do the one
    thing it is worst at. Observed live: it returned
    `chunk_id='10028766648516879691'` — a plausible-looking id that exists
    nowhere. A small ordinal it can copy reliably, and the mapping back to a
    real chunk_id happens in code, so an invented id has no path in at all.
    """
    hits = [_hit(chunk_id="1bdc21dad28df706", text="The fox jumps high.")]
    client = _ScriptedClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])

    response = answer("q", hits, client=client, arm_used="hybrid")

    assert response.degraded is False
    assert [c.chunk_id for c in response.citations] == ["1bdc21dad28df706"]


def test_passage_number_outside_the_context_with_an_unfindable_quote_is_rejected() -> None:
    """A number nobody offered, quoting text nobody showed, is a fabrication."""
    hits = [_hit()]
    client = _ScriptedClient([_llm_json("It jumps.", [{"passage": 99, "quote": "a badger sings"}])])

    response = answer("q", hits, client=client, arm_used="hybrid")

    assert response.degraded is True
    assert response.citations == []


def test_a_quote_from_a_different_passage_is_reattributed_not_discarded() -> None:
    """The model is good at copying text and bad at bookkeeping.

    Observed live: asked about clear writing, it returned a real, verbatim
    sentence from Taylor on scientific management while citing the passage
    number of an entirely different extract. The words were genuine; the
    label was wrong.

    Binding a citation to the passage the text demonstrably came from is
    stronger attribution than trusting the number the model typed, not
    weaker — it is the same principle that already keeps `book_title` and
    `chunk_id` out of the model's hands. Only a quote found in NO passage is
    a fabrication.
    """
    hits = [
        _hit(chunk_id="c1", text="The fox jumps high."),
        _hit(chunk_id="c2", text="Scientific management must inevitably prevail."),
    ]
    client = _ScriptedClient(
        [_llm_json("It prevails.", [{"passage": 1, "quote": "must inevitably prevail"}])]
    )

    response = answer("q", hits, client=client, arm_used="hybrid")

    assert response.degraded is False
    assert [c.chunk_id for c in response.citations] == ["c2"]


def test_author_metadata_header_quote_rebinds_to_verbatim_author_in_passage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LIVE: Groq quoted the prompt header; trust only the same author in body text."""
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata",
        lambda book_ids: {
            book_id: ("Walden" if book_id == "b1" else "Another Book", ["Henry David Thoreau"])
            for book_id in book_ids
        },
    )
    hits = [_hit(text="Walden, by Henry David Thoreau", book_id="b1")]
    hits[0].block_ids = ["blk-walden"]
    client = _ScriptedClient(
        [
            _llm_json(
                "Henry David Thoreau",
                [{"passage": 1, "quote": "authors=['Henry David Thoreau']"}],
            )
        ]
    )

    response = answer("Who wrote Walden?", hits, client=client, arm_used="hybrid_rerank")

    assert response.degraded is False
    assert len(response.citations) == 1
    assert response.citations[0].quote == "Henry David Thoreau"
    assert response.citations[0].block_id == "blk-walden"
    assert response.citations[0].quote in hits[0].text

    metadata_only_hits = [
        _hit(text="Walden discusses civil disobedience.", book_id="b1"),
        _hit(text="An essay by Henry David Thoreau.", book_id="b2"),
    ]
    metadata_only = answer(
        "Who wrote Walden?",
        metadata_only_hits,
        client=_ScriptedClient(
            [
                _llm_json(
                    "Henry David Thoreau",
                    [{"passage": 1, "quote": "authors=['Henry David Thoreau']"}],
                )
            ]
        ),
        arm_used="hybrid_rerank",
    )
    assert metadata_only.degraded is True
    assert metadata_only.citations == []


def test_a_quote_found_in_no_passage_at_all_still_degrades() -> None:
    """Reattribution must not become "accept anything".

    If the words appear in none of the passages the model was shown, there is
    nothing to bind the citation to and the answer is not grounded.
    """
    hits = [_hit(chunk_id="c1", text="The fox jumps high.")]
    client = _ScriptedClient(
        [_llm_json("A badger.", [{"passage": 1, "quote": "the badger sings at dawn"}])]
    )

    response = answer("q", hits, client=client, arm_used="hybrid")

    assert response.degraded is True
    assert response.citations == []


def test_quote_matching_ignores_only_whitespace_differences() -> None:
    """Book text is hard-wrapped; the model re-flows it.

    The chunk holds "division of labour\\nin this factory"; the model returns
    "division of labour in this factory". Character-for-character that is not
    a substring, but nothing was invented — the difference is a line break
    the typesetter chose. Failing this rejected essentially every real quote.
    """
    hits = [_hit(text="The division of labour\nin this factory system\nis very marked.")]
    client = _ScriptedClient(
        [_llm_json("Marked.", [{"passage": 1, "quote": "division of labour in this factory"}])]
    )

    response = answer("q", hits, client=client, arm_used="hybrid")

    assert response.degraded is False
    assert len(response.citations) == 1


def test_a_paraphrase_is_still_rejected_after_whitespace_normalisation() -> None:
    """The guard rail must not have been loosened into uselessness.

    Whitespace-insensitivity is the smallest change that admits real quotes.
    Anything that alters a word is still a fabricated quote and must degrade.
    """
    hits = [_hit(text="The division of labour in this factory system is very marked.")]
    client = _ScriptedClient(
        [_llm_json("Marked.", [{"passage": 1, "quote": "the splitting up of work is notable"}])]
    )

    response = answer("q", hits, client=client, arm_used="hybrid")

    assert response.degraded is True


def test_passage_ordinal_is_not_accepted_as_a_chunk_id() -> None:
    """An ordinal typed into a `chunk_id` field is never accepted as one.

    This is the shape of the original live defect, reproduced exactly: the
    model, shown `[1] chunk_id='b4e8f2cb74bee0e8' ...`, answered with
    `chunk_id: "1"` — it copied the most salient token on the line, the
    ordinal, not the opaque hex id it was asked for. `_validate_citations`
    rejected it (`citation cites chunk_id '3', which is not in the retrieved
    hits`), so the answer degraded, and /v1/ask returned the honest-but-
    useless fallback for the majority of real questions.

    Two properties are pinned here, and they are the two halves of the fix:

    - the ordinal never becomes a `chunk_id` — no citation carrying `"1"`
      may ever reach a caller, degraded or not. `_validate_citations` stays
      exactly as strict as specs/answer.md requires.
    - a citation made the way the prompt now asks for one — by passage
      number — resolves to the real hex id. That half is what was failing:
      the guard rail was right and the thing it was guarding was
      unanswerable, so every answer degraded.
    """
    hex_id = "b4e8f2cb74bee0e8"
    hits = [_hit(chunk_id=hex_id, text="The fox jumps high.")]

    # The old, defective model output: the ordinal in the chunk_id field.
    ordinal_client = _ScriptedClient(
        [_llm_json("It jumps.", [{"chunk_id": "1", "quote": "fox jumps"}])]
    )
    ordinal_result = answer("does it jump?", hits, client=ordinal_client, arm_used="hybrid")

    assert "1" not in [c.chunk_id for c in ordinal_result.citations]
    assert ordinal_result.citations == []
    assert ordinal_result.degraded is True

    # The output the prompt now asks for, on the same hits: a real citation.
    passage_client = _ScriptedClient(
        [_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])]
    )
    passage_result = answer("does it jump?", hits, client=passage_client, arm_used="hybrid")

    assert passage_result.degraded is False
    assert [c.chunk_id for c in passage_result.citations] == [hex_id]


def test_context_prompt_never_shows_a_chunk_id() -> None:
    """The prompt must not put an identifier in front of the model that it is
    forbidden to use.

    `[1] chunk_id='b4e8f2cb74bee0e8' book=...` showed the model two competing
    identifiers and asked it to cite by neither name reliably. The id is dead
    weight in the context — nothing downstream reads it back, because
    `answer()` maps the passage number to the real chunk itself — and while it
    is on the line it is bait for exactly the defect
    `test_passage_ordinal_is_not_accepted_as_a_chunk_id` covers. Keeping it
    out is cheaper than out-instructing it.
    """
    hits = [_hit(chunk_id="b4e8f2cb74bee0e8")]
    client = _ScriptedClient([_llm_json("ok", [{"passage": 1, "quote": "fox jumps"}])])

    answer("q", hits, client=client, arm_used="hybrid")

    sent_prompt = client.calls[0]["messages"][1].content
    assert "chunk_id" not in sent_prompt
    assert "b4e8f2cb74bee0e8" not in sent_prompt
    assert "[1]" in sent_prompt


def test_citation_carries_a_block_id_that_can_be_resolved() -> None:
    """A citation nobody can open is not a citation.

    Found by the cold-clone drill, which is the only place it could have been:
    every unit test asserted on `chunk_id` and passed, while end to end the
    UI's "show full source block" button and the drill's own resolution check
    both called `/v1/blocks/{chunk_id}` against an endpoint keyed on
    `block_id`. Verified against the live stack — a chunk_id returns 404 and a
    block_id returns 200 — so the feature had never worked.

    `chunks.block_ids` was already being selected by the index query and used
    to derive `page`; it simply never reached the `Hit`.
    """
    hits = [_hit(chunk_id="c1", text="The fox jumps high.")]
    hits[0].block_ids = ["blk-1", "blk-2"]
    client = _ScriptedClient([_llm_json("It jumps.", [{"passage": 1, "quote": "fox jumps"}])])

    response = answer("q", hits, client=client, arm_used="hybrid")

    assert response.degraded is False
    assert response.citations[0].block_id == "blk-1"


def test_openai_client_treats_empty_api_key_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank `LLM_API_KEY` (empty Cloud secret) must construct like an absent
    one — the SDK rejects "" outright, which made every request 500 instead of
    degrading at call time like any other unreachable LLM."""
    from homelib_rag.answer import OpenAIClient

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")
    client = OpenAIClient()
    assert client._client.api_key == "ollama"


def test_openai_client_falls_back_to_groq_when_llm_api_key_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public demo sets one secret. With `LLM_API_KEY` blank or absent and
    `GROQ_API_KEY` present, the client targets Groq's OpenAI-compatible
    endpoint and a Groq model — never the Ollama model name left in `LLM_*`."""
    from homelib_rag.answer import OpenAIClient

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b-instruct")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    client = OpenAIClient()
    assert client.base_url == "https://api.groq.com/openai/v1"
    assert client.model == "openai/gpt-oss-20b"
    assert client._client.api_key == "gsk-test"


def test_openai_client_prefers_a_set_llm_api_key_over_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compose keeps Ollama even when a Groq key is also in the environment."""
    from homelib_rag.answer import OpenAIClient

    monkeypatch.setenv("LLM_API_KEY", "ollama")
    monkeypatch.setenv("LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b-instruct")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    client = OpenAIClient()
    assert client.base_url == "http://ollama:11434/v1"
    assert client.model == "qwen2.5:7b-instruct"
    assert client._client.api_key == "ollama"


def test_factual_answer_with_empty_citations_is_not_trusted() -> None:
    """Ungrounded claim + empty citations must degrade — never silent accept."""
    hits = [_hit()]
    client = _ScriptedClient([_llm_json("A factual claim", [])])

    result = answer("q", hits, client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.citations == []
    assert result.answer != "A factual claim"
    assert result.answer == ""


def test_empty_llm_answer_is_degraded() -> None:
    """Valid JSON with no answer is still an unusable generation, not success."""
    hits = [_hit()]
    client = _ScriptedClient([_llm_json("", [])])

    result = answer("q", hits, client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.answer == ""
    assert result.citations == []


def test_bare_integer_citations_do_not_become_trusted_uncited_answers() -> None:
    """Groq `citations: [1]` must not coerce to [] and trust the claim."""
    hits = [_hit()]
    client = _ScriptedClient(
        [
            LLMResponse(
                content='{"answer": "A factual claim", "citations": [1]}',
                usage=LLMUsage(prompt_tokens=10, completion_tokens=5),
            )
        ]
    )

    result = answer("q", hits, client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.citations == []
    assert result.answer != "A factual claim"


def test_honest_passage_abstention_with_empty_citations_stays_trusted() -> None:
    """Legitimate refuse wording may keep citations=[] without degrading."""
    hits = [_hit()]
    client = _ScriptedClient([_llm_json("None of the provided passages answer this question.", [])])

    result = answer("q", hits, client=client, arm_used="hybrid")

    assert result.degraded is False
    assert result.citations == []
    assert "passages" in result.answer.lower()
