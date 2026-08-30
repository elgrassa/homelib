"""Tests for `evals.judge.prompt_hash` — the prompt drift detector (specs/evals-llm.md).

`prompt_hash` is the mechanism that makes a silent prompt edit impossible:
the shipped judge prompt's hash is pinned as a literal below, so changing
the template, its version, or the schema shape without deliberately
updating that literal in the SAME diff turns the suite red.

No LLM and no database are involved — `prompt_hash` is a pure function.
"""

from __future__ import annotations

import hashlib

from evals.judge import (
    JUDGE_PROMPT_VERSION,
    JUDGE_SCHEMA_SHAPE,
    JUDGE_SYSTEM_TEMPLATE,
    prompt_hash,
)

# The pinned hash of the CURRENTLY SHIPPED judge prompt. This literal is the
# drift detector: it must only ever change in the same diff as a deliberate
# change to JUDGE_PROMPT_VERSION / JUDGE_SYSTEM_TEMPLATE / JUDGE_SCHEMA_SHAPE.
PINNED_JUDGE_PROMPT_HASH = "cdf1891b3c1d266425c9b9f02ece648b9e9a1e17f01c2fa540790d5d26f31745"


def test_prompt_hash_pinned() -> None:
    assert (
        prompt_hash(JUDGE_PROMPT_VERSION, JUDGE_SYSTEM_TEMPLATE, JUDGE_SCHEMA_SHAPE)
        == PINNED_JUDGE_PROMPT_HASH
    )


def test_prompt_hash_changes_when_template_changes() -> None:
    # One character apart — the smallest edit a careless prompt tweak can be.
    before = prompt_hash("1", "grade the answer", "a:int")
    after = prompt_hash("1", "grade the answers", "a:int")
    assert before != after


def test_prompt_hash_changes_when_version_changes() -> None:
    assert prompt_hash("1", "t", "s") != prompt_hash("2", "t", "s")


def test_prompt_hash_changes_when_schema_shape_changes() -> None:
    assert prompt_hash("1", "t", "a:int") != prompt_hash("1", "t", "a:int,b:int")


def test_prompt_hash_is_the_documented_sha256_of_the_joined_fields() -> None:
    """The spec pins the construction itself, not just "some hash"."""
    expected = hashlib.sha256(b"1|t|s").hexdigest()
    assert prompt_hash("1", "t", "s") == expected


def test_prompt_hash_field_boundaries_are_not_ambiguous() -> None:
    """Moving a character across the separator must not collide.

    A naive `version + template + schema` concatenation would hash ("ab", "c")
    and ("a", "bc") identically; the "|" join is what prevents that.
    """
    assert prompt_hash("1", "ab", "c") != prompt_hash("1", "a", "bc")
