"""Red tests for `homelib_rag.rewrite` — see specs/rewrite.md.

`_call_llm` (the only function that talks to an OpenAI-compatible endpoint)
is monkeypatched in every failure/success test below; nothing here reaches a
network LLM. `test_call_llm_*` tests exercise `_call_llm`'s own body against a
duck-typed fake client instead, so the real call/parse code path still gets
executed under test.
"""

from __future__ import annotations

import json

import pytest
from homelib_rag import rewrite as rewrite_module
from homelib_rag.rewrite import rewrite_query

# ── named red tests (per the WP-13 task brief) ──────────────────────────────


def test_rewrite_falls_back_to_original_on_garbage_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rewrite_module, "_call_llm", lambda q: "not json at all")

    result = rewrite_query("what is the meaning of this passage")

    assert result == "what is the meaning of this passage"


def test_rewrite_falls_back_to_original_when_llm_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(q: str) -> str:
        raise ConnectionError("simulated connection failure")

    monkeypatch.setattr(rewrite_module, "_call_llm", _raise)

    result = rewrite_query("how do bees pollinate flowers")

    assert result == "how do bees pollinate flowers"


# ── remaining named red tests from specs/rewrite.md ─────────────────────────


def test_rewrite_returns_original_query_on_unparseable_llm_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rewrite_module, "_call_llm", lambda q: "not json at all")

    result = rewrite_query("what is the meaning of this passage")

    assert result == "what is the meaning of this passage"


def test_rewrite_returns_original_query_when_llm_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(q: str) -> str:
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(rewrite_module, "_call_llm", _raise)

    result = rewrite_query("another question entirely")

    assert result == "another question entirely"


def test_rewrite_returns_original_query_on_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rewrite_module, "_call_llm", lambda q: json.dumps({"rewritten_query": "   "})
    )

    result = rewrite_query("empty rewrite test")

    assert result == "empty rewrite test"


def test_rewrite_returns_rewritten_query_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rewrite_module,
        "_call_llm",
        lambda q: json.dumps({"rewritten_query": "bees pollination flowering plants mechanism"}),
    )

    result = rewrite_query("how do bees do the pollen thing")

    assert result == "bees pollination flowering plants mechanism"


@pytest.mark.parametrize(
    "raw_response",
    [
        "{}",  # missing field
        json.dumps({"rewritten_query": 12345}),  # wrong type
        "null",  # None
        '{"rewritten_query": "truncat',  # truncated JSON
        "",  # empty string
        "   ",  # whitespace only
    ],
)
def test_rewrite_never_raises(monkeypatch: pytest.MonkeyPatch, raw_response: str) -> None:
    monkeypatch.setattr(rewrite_module, "_call_llm", lambda q: raw_response)

    result = rewrite_query("does this raise")

    assert result == "does this raise"


def test_rewrite_does_not_mutate_input_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rewrite_module, "_call_llm", lambda q: "not json")
    q = "original query text"
    q_copy = str(q)

    rewrite_query(q)

    assert q == q_copy


# ── extra behavior from specs/rewrite.md not covered above ──────────────────


def test_rewrite_returns_original_query_on_absurdly_long_rewrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rewrite_module,
        "_call_llm",
        lambda q: json.dumps({"rewritten_query": "x" * 1000}),
    )

    result = rewrite_query("short question")

    assert result == "short question"


def test_rewrite_never_raises_on_unexpected_call_llm_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A totally generic exception from `_call_llm` still degrades to `q`."""

    def _raise(q: str) -> str:
        raise RuntimeError("something nobody enumerated")

    monkeypatch.setattr(rewrite_module, "_call_llm", _raise)

    result = rewrite_query("robustness check")

    assert result == "robustness check"


# ── coverage for `_call_llm` itself, against a duck-typed fake client ───────


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str | None) -> None:
        self.choices = [_FakeChoice(content)] if content is not None else []


class _FakeCompletions:
    def __init__(self, content: str | None) -> None:
        self._content = content

    def create(self, **kwargs: object) -> _FakeCompletion:
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content: str | None) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str | None) -> None:
        self.chat = _FakeChat(content)


def test_call_llm_returns_content_from_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rewrite_module, "_client", lambda: _FakeClient('{"rewritten_query": "x"}'))

    content = rewrite_module._call_llm("q")

    assert content == '{"rewritten_query": "x"}'


def test_call_llm_raises_on_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rewrite_module, "_client", lambda: _FakeClient(None))

    with pytest.raises(ValueError, match="empty"):
        rewrite_module._call_llm("q")


def test_client_and_model_name_use_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    assert rewrite_module._model_name() == "qwen2.5:7b-instruct"
    client = rewrite_module._client()
    assert str(client.base_url) == "http://localhost:11434/v1/"
