"""LLM-as-judge scoring for answer-synthesis prompt variants — see specs/evals-llm.md.

Scores one `(question, answer, citations)` triple on three independent 1-5
sub-scores plus the judge's OWN overall rating, and pins the shipped prompt
with a content hash so it cannot drift without the suite noticing.

Two properties this module exists to guarantee:

1. **The judge is told, in its own system prompt, that it is not the model
   being graded.** `NOT_THE_SCORED_MODEL_DISCLAIMER` is the first thing in
   every rendered prompt. Without it an LLM judge reliably rewards answers
   that read like its own output, which would mean the winning prompt
   variant is chosen by stylistic self-recognition rather than by quality —
   the eval would be measuring the judge, not the variants.

2. **`suggested_score` is never recomputed.** The judge's overall rating is
   an independent judgment; the harness may average the sub-scores for
   comparison, but it never writes that average back over the field. An
   answer whose three sub-scores look generous and which is nonetheless
   unusable is exactly the case a mechanical average would erase.

`prompt_hash` is the drift detector: `evals/tests/test_prompt_hash.py` pins
the hash of the currently shipped prompt as a literal, so editing the
template, its version, or the schema shape without deliberately updating
that literal in the same diff turns the suite red.

The LLM seam is `homelib_rag.answer.OpenAICompatibleClient` — the same
protocol `answer.py`, `roadmap.py` and `agent.py` use. Tests script it; no
second client implementation exists in this repo.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from homelib_rag.answer import (
    ChatMessage,
    Citation,
    LLMResponse,
    OpenAICompatibleClient,
    default_llm_client,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "JUDGE_PROMPT_VERSION",
    "JUDGE_SCHEMA_SHAPE",
    "JUDGE_SYSTEM_TEMPLATE",
    "NOT_THE_SCORED_MODEL_DISCLAIMER",
    "UNKNOWN_VARIANT",
    "JudgeParseError",
    "JudgeScore",
    "judge",
    "prompt_hash",
    "render_system_prompt",
]

logger = logging.getLogger(__name__)

UNKNOWN_VARIANT = "unknown"

# Bump whenever the prompt's *intent* changes, not merely its wording — the
# hash already catches wording. This field exists so a report from an older
# run can be told apart from a current one at a glance.
JUDGE_PROMPT_VERSION = "1"

# The initial call plus exactly ONE bounded repair retry. Not tunable: an
# unbounded repair loop against a model that cannot produce the schema burns
# the run's entire time budget on a single case.
_MAX_JUDGE_ATTEMPTS = 2

_MIN_SCORE = 1
_MAX_SCORE = 5


class JudgeParseError(Exception):
    """The judge produced output that could not be parsed into a `JudgeScore`,
    twice — the initial call and its one repair retry.

    Raised rather than returning a neutral default: a case scored 3/5 because
    the judge malfunctioned is indistinguishable in the report from a case
    genuinely judged mediocre, and it moves the variant means. The caller
    excludes the case from `VariantScore.n` instead.
    """


# ── the shape the judge model must return ───────────────────────────────────


class _RawJudgeScore(BaseModel):
    """What the LLM itself is asked to produce.

    Deliberately has no `judge_model` field: that is provenance the harness
    knows and the model does not, so asking for it would only give the model
    something to get wrong.
    """

    model_config = ConfigDict(extra="allow")

    faithfulness: int = Field(ge=_MIN_SCORE, le=_MAX_SCORE)
    relevance: int = Field(ge=_MIN_SCORE, le=_MAX_SCORE)
    citation_quality: int = Field(ge=_MIN_SCORE, le=_MAX_SCORE)
    suggested_score: int = Field(ge=_MIN_SCORE, le=_MAX_SCORE)
    verdict: str


class JudgeScore(BaseModel):
    """One judged case. `suggested_score` is the judge's own overall rating and
    is never derived from the three sub-scores."""

    model_config = ConfigDict(extra="allow")

    faithfulness: int = Field(ge=_MIN_SCORE, le=_MAX_SCORE)
    relevance: int = Field(ge=_MIN_SCORE, le=_MAX_SCORE)
    citation_quality: int = Field(ge=_MIN_SCORE, le=_MAX_SCORE)
    suggested_score: int = Field(ge=_MIN_SCORE, le=_MAX_SCORE)
    verdict: str
    judge_model: str


def _schema_shape(model: type[BaseModel]) -> str:
    """A compact `name:type,...` description of what the judge must return.

    Derived from the model rather than hand-written so that adding, removing,
    or retyping a field the judge is asked for changes `prompt_hash` on its
    own — a hand-maintained string would silently go stale, which is the
    exact failure the hash is here to catch.
    """
    parts = []
    for name, field in model.model_fields.items():
        annotation = field.annotation
        type_name = getattr(annotation, "__name__", str(annotation))
        parts.append(f"{name}:{type_name}")
    return ",".join(parts)


JUDGE_SCHEMA_SHAPE = _schema_shape(_RawJudgeScore)


# ── the prompt ──────────────────────────────────────────────────────────────

# Bias control, per specs/evals-llm.md. First person and explicit: a judge
# that believes it authored the answer grades its own homework. This exact
# string is asserted against the RENDERED prompt in the test suite, so it
# cannot be softened into a vague "be objective" without going red.
NOT_THE_SCORED_MODEL_DISCLAIMER = (
    "I am an independent judge. I am NOT the model whose prompt variant "
    "produced the answer below, and this is a different model invocation "
    "from the one that generated it. I must never rate an answer more "
    "highly because it reads like something I would have written myself."
)

# Built by concatenation rather than an f-string so the JSON example's braces
# need no escaping, and so the disclaimer's own text is part of the hashed
# template — a change to the disclaimer must move `prompt_hash`.
JUDGE_SYSTEM_TEMPLATE = (
    NOT_THE_SCORED_MODEL_DISCLAIMER
    + "\n\n"
    + "I am grading one answer produced by a retrieval-augmented assistant "
    "over a library of books, under the answer-prompt variant named "
    "{variant}. I am given the question, the answer, and the citations the "
    "answer attached. I judge only what is in front of me: I never reward a "
    "claim because I happen to know it is true, and I never penalise one "
    "because I would have phrased it differently.\n\n"
    "I rate each of the following independently, 1 (worst) to 5 (best):\n"
    "- faithfulness: does the answer claim ONLY what its citations support? "
    "An answer that adds correct but uncited facts still scores low here.\n"
    "- relevance: does the answer address the question that was actually "
    "asked, rather than an adjacent one?\n"
    "- citation_quality: are the citations specific and resolvable — a "
    "quote that genuinely carries the claim, with a usable book, section "
    "and page?\n\n"
    "I then give suggested_score: MY OWN overall 1-5 rating of this answer. "
    "It is an independent judgment, not an average of the three sub-scores. "
    "If the answer is unusable as a whole I say 2 even when the sub-scores "
    "look generous, and I say 5 only for an answer I would ship unchanged.\n\n"
    "An empty answer is a failure to answer, not a neutral one: it scores 1 "
    "for faithfulness and 1 for relevance.\n\n"
    "I respond with ONLY a JSON object of the form "
    '{"faithfulness": 1-5, "relevance": 1-5, "citation_quality": 1-5, '
    '"suggested_score": 1-5, "verdict": "one or two sentences"} '
    "and no other text."
)


def prompt_hash(version: str, template: str, schema_shape: str) -> str:
    """`sha256("|".join([version, template, schema_shape]))`, hex-encoded.

    The "|" join is load-bearing: a plain concatenation would hash
    `("ab", "c")` and `("a", "bc")` identically, so a character moved across
    a field boundary would slip past the drift detector.
    """
    joined = "|".join([version, template, schema_shape])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def render_system_prompt(variant: str) -> str:
    """The judge system prompt as it will actually be sent, for `variant`.

    `str.replace` rather than `str.format`: the template embeds a literal
    JSON example, and `format` would demand every one of its braces be
    doubled — turning the one prompt a human must be able to read into
    something they cannot.
    """
    return JUDGE_SYSTEM_TEMPLATE.replace("{variant}", variant)


def _render_case(question: str, answer: str, citations: Sequence[Citation]) -> str:
    lines = [f"Question: {question}", "", "Answer:", answer or "(the assistant returned nothing)"]
    lines.extend(["", "Citations:"])
    if not citations:
        lines.append("(none)")
    for i, citation in enumerate(citations, start=1):
        section = " / ".join(citation.section_path) if citation.section_path else "(no section)"
        page = citation.page if citation.page is not None else "unknown"
        lines.append(
            f"[{i}] book={citation.book_title!r} section={section!r} page={page} "
            f"chunk_id={citation.chunk_id!r}"
        )
        lines.append(f"    quote: {citation.quote!r}")
    return "\n".join(lines)


def _repair_instruction(error: str) -> str:
    return (
        "Your previous reply could not be parsed as the required JSON object. "
        f"The parse error was: {error}\n"
        "Reply again with ONLY the JSON object — no prose, no markdown fence, "
        "no trailing commentary. Every score is an integer from 1 to 5."
    )


def judge(
    question: str,
    answer: str,
    citations: list[Citation],
    *,
    client: OpenAICompatibleClient | None = None,
    variant: str = UNKNOWN_VARIANT,
) -> JudgeScore:
    """Score one answered case, with exactly one bounded repair retry.

    Raises `JudgeParseError` if the judge cannot produce a valid `JudgeScore`
    on either attempt. Transport failures (`LLMUnreachableError`) propagate
    unchanged — an unreachable endpoint is not a badly behaved judge, and the
    caller distinguishes the two in its logs.
    """
    judge_client = client if client is not None else default_llm_client()
    system = ChatMessage(role="system", content=render_system_prompt(variant))
    user = ChatMessage(role="user", content=_render_case(question, answer, citations))

    messages: list[ChatMessage] = [system, user]
    last_error = "no attempt was made"

    for attempt in range(1, _MAX_JUDGE_ATTEMPTS + 1):
        response: LLMResponse = judge_client.chat(messages, response_format={"type": "json_object"})
        raw = response.content or ""
        try:
            parsed = _RawJudgeScore.model_validate_json(raw)
        except ValidationError as exc:
            last_error = str(exc)
            logger.warning(
                "judge output unparseable on attempt %d/%d for variant %r",
                attempt,
                _MAX_JUDGE_ATTEMPTS,
                variant,
            )
            # Echo the bad reply back as the assistant turn so the model can
            # see what it actually produced, then ask for a repair.
            messages = [
                system,
                user,
                ChatMessage(role="assistant", content=raw),
                ChatMessage(role="user", content=_repair_instruction(last_error)),
            ]
            continue

        return JudgeScore(
            faithfulness=parsed.faithfulness,
            relevance=parsed.relevance,
            citation_quality=parsed.citation_quality,
            # Copied through verbatim. Never `mean(sub_scores)` — see module
            # docstring; the harness computing that average elsewhere for
            # comparison is fine, writing it back here is not.
            suggested_score=parsed.suggested_score,
            verdict=parsed.verdict,
            judge_model=judge_client.model,
        )

    raise JudgeParseError(
        f"judge produced unparseable output {_MAX_JUDGE_ATTEMPTS} times for variant "
        f"{variant!r}; last parse error: {last_error}"
    )
