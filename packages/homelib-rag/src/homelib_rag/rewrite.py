"""LLM query rewriter — see specs/rewrite.md.

Asks an LLM to turn a user's natural-language question into a retrieval-
shaped search string (expanded acronyms, dropped filler, explicit key terms)
before it reaches `hybrid_search`. This is net-new code: the prompt, the
typed output contract (`RewriteResult`), and the fail-closed parsing below
are homelib's own, written directly against the `openai` client — not pulled
from LangChain or any retrieval framework's built-in rewriter.

Fail-closed by construction: every failure mode returns the original query
unchanged, never raises, never returns an empty string, never returns a
partially parsed guess. There is no retry — a slow retrieval-quality miss is
preferable to doubling latency on a non-critical rewrite step.
"""

from __future__ import annotations

import logging
import os

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

__all__ = ["rewrite_query"]

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_API_KEY = "ollama"
_DEFAULT_MODEL = "qwen2.5:7b-instruct"

_TIMEOUT_SECONDS = 10.0

# A "rewrite" longer than this is not a retrieval-shaped query anymore — it is
# the model dumping something pathological (a repeated token loop, a stray
# essay). Treated as a failure, same as unparseable output.
_MAX_REWRITE_CHARS = 500

_SYSTEM_PROMPT = (
    "You rewrite a user's question into a short, keyword-rich search query "
    "for a hybrid full-text and vector search engine over a library of books. "
    "Expand acronyms, drop filler words, and keep the core entities and "
    "intent. Respond with ONLY a JSON object of the form "
    '{"rewritten_query": "..."} and no other text.'
)


class RewriteResult(BaseModel):
    """Internal typed shape the LLM is asked to produce.

    Not exposed publicly — `rewrite_query`'s return type is plain `str`.
    """

    model_config = ConfigDict(extra="allow")

    rewritten_query: str


def _client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("LLM_BASE_URL", _DEFAULT_BASE_URL),
        api_key=os.environ.get("LLM_API_KEY", _DEFAULT_API_KEY),
        timeout=_TIMEOUT_SECONDS,
    )


def _model_name() -> str:
    return os.environ.get("LLM_MODEL", _DEFAULT_MODEL)


def _call_llm(q: str) -> str:
    """Call the configured LLM and return its raw response content.

    Raises on any transport/API failure (connection error, timeout, non-2xx
    response) or an empty/missing response body. Never called with a network
    LLM in the unit tests — they monkeypatch this function directly to
    simulate every failure mode.
    """
    response = _client().chat.completions.create(
        model=_model_name(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": q},
        ],
        response_format={"type": "json_object"},
        timeout=_TIMEOUT_SECONDS,
    )
    if not response.choices:
        raise ValueError("empty LLM response: no choices returned")
    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty LLM response content")
    return content


def rewrite_query(q: str) -> str:
    """Ask an LLM to rewrite `q` for retrieval; fall back to `q` on failure.

    Always returns a non-empty `str` usable directly as `hybrid_search`
    input. This function has no exception it lets propagate to the caller —
    `hybrid_search`/`apps/api` never need a try/except around it.
    """
    try:
        return _rewrite_query(q)
    except Exception:
        logger.exception("query rewrite failed unexpectedly; falling back to original query")
        return q


def _rewrite_query(q: str) -> str:
    try:
        raw = _call_llm(q)
    except Exception:
        logger.warning("query rewrite LLM call failed; falling back to original query")
        return q

    try:
        result = RewriteResult.model_validate_json(raw)
    except ValidationError:
        logger.warning("query rewrite returned unparseable output; falling back to original query")
        return q

    rewritten = result.rewritten_query.strip()
    if not rewritten:
        logger.warning("query rewrite returned an empty result; falling back to original query")
        return q
    if len(rewritten) > _MAX_REWRITE_CHARS:
        logger.warning("query rewrite output is absurdly long; falling back to original query")
        return q
    return rewritten
