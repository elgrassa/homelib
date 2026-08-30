"""Behavioural tests for `homelib_rag.answer` — see specs/answer.md.

No live Postgres, no live LLM: `_book_metadata` is monkeypatched (the DB
seam) and every LLM call goes through a scripted fake `OpenAICompatibleClient`
— never the real `openai` package's network path.
"""

from __future__ import annotations

import json
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
    ) -> LLMResponse:
        self.calls.append({"messages": list(messages), "tools": tools, "format": response_format})
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
    client = _ScriptedClient([_llm_json("It jumps.", [{"chunk_id": "c1", "quote": "fox jumps"}])])

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
        [_llm_json("It flies.", [{"chunk_id": "c1", "quote": "the fox flies away"}])]
    )

    result = answer("does it fly?", hits, client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.citations == []


def test_citation_quote_present_verbatim_in_chunk() -> None:
    """For each citation in a non-degraded response, `quote` is a substring
    of the matching hit's text."""
    hits = [_hit(text="Four score and seven years ago.")]
    client = _ScriptedClient(
        [_llm_json("A famous opening.", [{"chunk_id": "c1", "quote": "seven years ago"}])]
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
    """A citation to a chunk_id absent from `hits` never reaches the caller
    as trustworthy."""
    hits = [_hit(chunk_id="c1")]
    client = _ScriptedClient(
        [_llm_json("Made up.", [{"chunk_id": "chunk-that-does-not-exist", "quote": "anything"}])]
    )

    result = answer("what happened?", hits, client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.citations == []


def test_agent_dispatches_tools_with_scripted_llm_alias() -> None:
    """Sanity: this module's own scripted-client pattern (used across the
    agent-tools/answer/roadmap test suites) never touches the network."""
    hits = [_hit()]
    client = _ScriptedClient([_llm_json("ok", [])])
    result = answer("q", hits, client=client, arm_used="hybrid")
    assert result.answer == "ok"


# ── Author-attribution hardening (the Ford/Roosevelt finding) ──────────────


def test_context_includes_authors_not_just_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """The prompt sent to the LLM must carry the book's authors, not just its
    title — the structural fix for the observed invented-author defect."""
    monkeypatch.setattr(
        "homelib_rag.answer._book_metadata",
        lambda book_ids: {"b1": ("My Life and Work", ["Henry Ford"])},
    )
    hits = [_hit(book_id="b1")]
    client = _ScriptedClient([_llm_json("ok", [])])

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
                                "chunk_id": "c1",
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
    client = _ScriptedClient([_llm_json("ok", [])])

    result = answer("q", [_hit()], client=client, arm_used="hybrid")

    assert result.degraded is True
    assert result.citations == []


def test_answer_degrades_on_malformed_llm_output() -> None:
    bad_response = LLMResponse(
        content="not json at all", usage=LLMUsage(prompt_tokens=1, completion_tokens=1)
    )
    client = _ScriptedClient([bad_response])

    result = answer("q", [_hit()], client=client, arm_used="hybrid")

    assert result.degraded is True


def test_answer_degrades_on_unexpected_exception_from_client() -> None:
    client = _ScriptedClient([RuntimeError("boom")])

    result = answer("q", [_hit()], client=client, arm_used="hybrid")

    assert result.degraded is True


def test_answer_handles_empty_hits() -> None:
    client = _ScriptedClient([_llm_json("I don't have information on that.", [])])

    result = answer("q", [], client=client, arm_used="lexical")

    assert result.degraded is False
    assert result.citations == []


def test_degraded_response_has_zero_tokens_and_empty_citations() -> None:
    result = _degraded_response("hybrid", "some reason")
    assert result.degraded is True
    assert result.citations == []
    assert result.tokens.prompt == 0
    assert result.tokens.completion == 0
    assert result.arm_used == "hybrid"


# ── _validate_citations unit tests ──────────────────────────────────────────


def test_validate_citations_raises_for_unknown_chunk_id() -> None:
    hits = [_hit(chunk_id="c1", text="hello world")]
    bad = [
        Citation(
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
            chunk_id="c1", book_id="b1", book_title="T", section_path=[], page=None, quote="goodbye"
        )
    ]
    with pytest.raises(CitationValidationError):
        _validate_citations(bad, hits)


def test_validate_citations_passes_for_genuine_citation() -> None:
    hits = [_hit(chunk_id="c1", text="hello world")]
    good = [
        Citation(
            chunk_id="c1", book_id="b1", book_title="T", section_path=[], page=None, quote="hello"
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
