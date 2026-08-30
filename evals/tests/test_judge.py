"""Tests for evals/judge.py and evals/llm_eval.py — see specs/evals-llm.md.

Nothing here reaches a live LLM or a live database. Every LLM call is served
by `_ScriptedClient`, which implements the same `OpenAICompatibleClient`
protocol `homelib_rag.answer` defines, and `_book_metadata` is monkeypatched
at its documented test seam. The real `just eval-llm` run is a separate,
one-off invocation against the local model.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from homelib_rag.answer import ChatMessage, Citation, LLMResponse, LLMUnreachableError, LLMUsage
from homelib_rag.models import Hit

from evals.ground_truth import GroundTruthRow
from evals.judge import (
    NOT_THE_SCORED_MODEL_DISCLAIMER,
    JudgeParseError,
    JudgeScore,
    judge,
    render_system_prompt,
)
from evals.llm_eval import (
    DEFAULT_QUESTION_BUDGET,
    PROMPT_VARIANTS,
    AnsweredCase,
    VariantScore,
    run_variant,
    score_variants,
    write_report,
)


class _ScriptedClient:
    """An `OpenAICompatibleClient` that replays canned response bodies.

    Every call is recorded in `self.calls` so a test can assert on what was
    actually SENT to the model — the rendered prompt, not a docstring. When
    the script runs out, the last entry repeats, so "always malformed" is one
    entry rather than an arbitrarily long list.
    """

    def __init__(self, responses: list[str | Exception], *, model: str = "fake/judge") -> None:
        self.model = model
        self._responses = list(responses)
        self.calls: list[list[ChatMessage]] = []

    def chat(
        self,
        messages: Any,
        *,
        tools: Any = None,
        response_format: Any = None,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        scripted = self._responses[index]
        if isinstance(scripted, Exception):
            raise scripted
        return LLMResponse(content=scripted, usage=LLMUsage(prompt_tokens=1, completion_tokens=1))


def _judge_body(
    *,
    faithfulness: int = 4,
    relevance: int = 4,
    citation_quality: int = 4,
    suggested_score: int = 4,
    verdict: str = "Grounded and on topic.",
) -> str:
    return json.dumps(
        {
            "faithfulness": faithfulness,
            "relevance": relevance,
            "citation_quality": citation_quality,
            "suggested_score": suggested_score,
            "verdict": verdict,
        }
    )


def _citation(chunk_id: str = "c1", quote: str = "the assembly line moved") -> Citation:
    return Citation(
        chunk_id=chunk_id,
        book_id="ford-my-life-and-work",
        book_title="My Life and Work",
        section_path=["Chapter 5"],
        page=42,
        quote=quote,
    )


def _system_content(messages: list[ChatMessage]) -> str:
    return next(message.content for message in messages if message.role == "system")


# ── judge prompt: bias control ───────────────────────────────────────────────


def test_judge_prompt_states_it_is_not_the_scoring_model() -> None:
    """Every variant's RENDERED judge system prompt carries the disclaimer.

    Asserted on the text actually sent to the model, for every registered
    variant — a docstring or a comment saying the same thing would not stop
    the judge from grading its own homework.
    """
    # The disclaimer itself must keep saying the two things that matter; a
    # future edit that guts it into a vague "be objective" fails here.
    assert "NOT the model whose prompt variant produced the answer" in (
        NOT_THE_SCORED_MODEL_DISCLAIMER
    )
    assert "different model invocation" in NOT_THE_SCORED_MODEL_DISCLAIMER

    assert PROMPT_VARIANTS, "no prompt variants registered to check"
    for variant in PROMPT_VARIANTS:
        assert NOT_THE_SCORED_MODEL_DISCLAIMER in render_system_prompt(variant)

        client = _ScriptedClient([_judge_body()])
        judge("q?", "a.", [_citation()], client=client, variant=variant)
        sent = _system_content(client.calls[0])
        assert NOT_THE_SCORED_MODEL_DISCLAIMER in sent
        assert variant in sent


# ── judge scoring: independent fields ────────────────────────────────────────


def test_judge_score_sub_scores_and_suggested_score_are_independent_fields() -> None:
    """(5,5,5) sub-scores with suggested_score=2 round-trips unchanged.

    The harness must never overwrite the judge's own overall rating with a
    mechanical average of the sub-scores.
    """
    body = _judge_body(faithfulness=5, relevance=5, citation_quality=5, suggested_score=2)
    score = judge("q?", "a.", [_citation()], client=_ScriptedClient([body]), variant="concise")

    assert (score.faithfulness, score.relevance, score.citation_quality) == (5, 5, 5)
    assert score.suggested_score == 2
    # The mechanical average would be 5.0; the field survives at 2.
    assert score.suggested_score != round(
        (score.faithfulness + score.relevance + score.citation_quality) / 3
    )

    # The same must hold one level up: the aggregate keeps the judge's own
    # rating apart from the sub-score means rather than collapsing them.
    scores = score_variants(
        {"concise": [_answered_case("concise")]}, client=_ScriptedClient([body])
    )
    assert scores[0].mean_faithfulness == 5.0
    assert scores[0].mean_suggested_score == 2.0


def test_judge_records_the_model_that_produced_the_score() -> None:
    client = _ScriptedClient([_judge_body()], model="ollama/qwen2.5:7b-instruct")
    score = judge("q?", "a.", [_citation()], client=client)
    assert score.judge_model == "ollama/qwen2.5:7b-instruct"


def test_judge_rejects_an_out_of_range_sub_score() -> None:
    """A 9/5 is not a lenient judge, it is a malformed response."""
    client = _ScriptedClient([_judge_body(faithfulness=9)])
    with pytest.raises(JudgeParseError):
        judge("q?", "a.", [_citation()], client=client)


# ── judge failure handling ───────────────────────────────────────────────────


def test_judge_parse_failure_retries_once_then_excludes_case() -> None:
    """Exactly one bounded repair retry, then JudgeParseError — and the case
    is dropped from `VariantScore.n` rather than scored as a neutral default.
    """
    client = _ScriptedClient(["not json at all"])
    with pytest.raises(JudgeParseError):
        judge("q?", "a.", [_citation()], client=client)

    assert len(client.calls) == 2, "expected exactly one bounded repair retry"
    repair_prompt = "\n".join(m.content for m in client.calls[1])
    assert "not json at all" in repair_prompt or "parse" in repair_prompt.lower()

    # Two cases, one of which the judge can never parse: n counts 1, and the
    # means are computed over that one case only — never over a filled-in
    # default for the excluded one.
    good = _answered_case("concise", question="answerable?")
    bad = _answered_case("concise", question="unparseable?")
    scoring_client = _ScriptedClient(
        [_judge_body(faithfulness=5, relevance=5, citation_quality=5, suggested_score=5)]
    )
    broken = _PerQuestionClient(
        {
            "answerable?": _judge_body(
                faithfulness=5, relevance=5, citation_quality=5, suggested_score=5
            ),
            "unparseable?": "{{{ not json",
        },
        model=scoring_client.model,
    )
    scores = score_variants({"concise": [good, bad]}, client=broken)

    assert scores[0].n == 1
    assert scores[0].mean_faithfulness == 5.0
    assert scores[0].mean_suggested_score == 5.0


def test_judge_repair_retry_can_succeed() -> None:
    """The retry exists to recover, not just to burn a call."""
    client = _ScriptedClient(["```not json```", _judge_body(suggested_score=3)])
    score = judge("q?", "a.", [_citation()], client=client)
    assert score.suggested_score == 3
    assert len(client.calls) == 2


def test_judge_unreachable_llm_is_excluded_not_scored_as_zero() -> None:
    client = _ScriptedClient([LLMUnreachableError("connection refused")])
    scores = score_variants({"concise": [_answered_case("concise")]}, client=client)
    assert scores[0].n == 0


# ── prompt variants ──────────────────────────────────────────────────────────


def test_at_least_three_variants_registered() -> None:
    assert len(PROMPT_VARIANTS) >= 3
    assert all(prompt.strip() for prompt in PROMPT_VARIANTS.values())
    # Three names pointing at the same text is one variant with three labels.
    assert len(set(PROMPT_VARIANTS.values())) == len(PROMPT_VARIANTS)


def test_every_variant_still_asks_for_the_json_contract_answer_py_parses() -> None:
    """A variant that drops the JSON/verbatim-quote instructions would score
    0 for reasons that have nothing to do with prompt quality.

    The citation field names are DERIVED from `_RawCitation` rather than
    hardcoded, because hardcoding them is how this test failed to do its job:
    production moved citations from `chunk_id` to `passage` after the model
    was caught inventing 16-hex ids, every variant here kept asking for
    `chunk_id`, and nothing failed loudly. The answers simply all degraded, so
    all three arms scored identically at the floor — a bake-off that produces
    a tidy table and measures nothing. Deriving the names means the next
    schema change breaks this test instead of silently flattening the eval.
    """
    from homelib_rag.answer import _RawCitation

    for name, prompt in PROMPT_VARIANTS.items():
        for field in _RawCitation.model_fields:
            assert f"`{field}`" in prompt, (
                f"variant {name!r} never mentions `{field}`, which answer.py requires"
            )
        assert "citations" in prompt
        assert "JSON" in prompt


# ── run_variant ──────────────────────────────────────────────────────────────


def _hit(chunk_id: str = "c1", text: str = "the assembly line moved past the men") -> Hit:
    return Hit(
        chunk_id=chunk_id,
        book_id="ford-my-life-and-work",
        score=0.9,
        rank=1,
        text=text,
        section_path=["Chapter 5"],
        page=42,
    )


def _answered_case(variant: str, *, question: str = "q?", answer: str = "a.") -> AnsweredCase:
    return AnsweredCase(
        question=question,
        variant=variant,
        answer=answer,
        citations=[_citation()],
        latency_ms=10,
    )


class _PerQuestionClient:
    """Scripted client keyed on which question appears in the user message."""

    def __init__(self, bodies: dict[str, str], *, model: str = "fake/judge") -> None:
        self.model = model
        self._bodies = bodies
        self.calls: list[list[ChatMessage]] = []

    def chat(self, messages: Any, *, tools: Any = None, response_format: Any = None) -> LLMResponse:
        self.calls.append(list(messages))
        joined = "\n".join(m.content for m in messages)
        for key, body in self._bodies.items():
            if key in joined:
                return LLMResponse(
                    content=body, usage=LLMUsage(prompt_tokens=1, completion_tokens=1)
                )
        raise AssertionError(f"no scripted body matched: {joined[:200]!r}")


@pytest.fixture
def _no_db(monkeypatch: pytest.MonkeyPatch) -> None:
    from homelib_rag import answer as answer_mod

    monkeypatch.setattr(
        answer_mod,
        "_book_metadata",
        lambda book_ids: {"ford-my-life-and-work": ("My Life and Work", ["Henry Ford"])},
    )


def test_run_variant_sends_the_variant_prompt_not_the_production_default(
    _no_db: None,
) -> None:
    hit = _hit()
    body = json.dumps(
        {"answer": "It moved past the men.", "citations": [{"passage": 1, "quote": "moved"}]}
    )
    client = _ScriptedClient([body])
    rows = [GroundTruthRow(question="how?", chunk_id="c1", book_id="ford-my-life-and-work")]

    cases = run_variant("stepwise", rows, client=client, retrieve=lambda q, k: [hit])

    assert _system_content(client.calls[0]) == PROMPT_VARIANTS["stepwise"]
    assert cases[0].variant == "stepwise"
    assert cases[0].answer == "It moved past the men."
    assert cases[0].citations[0].chunk_id == "c1"


def test_run_variant_records_an_empty_answer_after_a_repeated_failure(_no_db: None) -> None:
    """A failed case is kept with `answer=""` so the judge scores the failure
    on its merits — dropping it would hide the failure from the report."""
    client = _ScriptedClient([LLMUnreachableError("connection refused")])
    rows = [GroundTruthRow(question="how?", chunk_id="c1", book_id="ford-my-life-and-work")]

    cases = run_variant("concise", rows, client=client, retrieve=lambda q, k: [_hit()])

    assert len(cases) == 1
    assert cases[0].answer == ""
    assert cases[0].citations == []
    assert len(client.calls) == 2, "expected exactly one retry before giving up"


def test_run_variant_survives_a_retrieval_failure(_no_db: None) -> None:
    def _boom(q: str, k: int) -> list[Hit]:
        raise RuntimeError("postgres is down")

    client = _ScriptedClient([_judge_body()])
    rows = [GroundTruthRow(question="how?", chunk_id="c1", book_id="ford-my-life-and-work")]

    cases = run_variant("concise", rows, client=client, retrieve=_boom)

    assert cases[0].answer == ""


def test_run_variant_honours_the_question_budget(_no_db: None) -> None:
    body = json.dumps({"answer": "ok", "citations": []})
    client = _ScriptedClient([body])
    rows = [
        GroundTruthRow(question=f"q{i}?", chunk_id="c1", book_id="ford-my-life-and-work")
        for i in range(5)
    ]

    cases = run_variant("concise", rows[:2], client=client, retrieve=lambda q, k: [_hit()])
    assert len(cases) == 2


def test_default_question_budget_is_within_the_documented_live_run_bound() -> None:
    """Budget is a parameter with a documented default, not a magic number."""
    assert 30 <= DEFAULT_QUESTION_BUDGET <= 50


# ── write_report ─────────────────────────────────────────────────────────────


def _variant_score(variant: str, *, n: int, suggested: float) -> VariantScore:
    return VariantScore(
        variant=variant,
        n=n,
        mean_faithfulness=4.0,
        mean_relevance=4.0,
        mean_citation_quality=4.0,
        mean_suggested_score=suggested,
    )


def test_write_report_marks_the_winner_by_the_judges_own_overall_score(tmp_path: Path) -> None:
    path = tmp_path / "llm_eval.md"
    write_report(
        [
            _variant_score("concise", n=10, suggested=3.5),
            _variant_score("cited_first", n=10, suggested=4.4),
            _variant_score("stepwise", n=10, suggested=4.1),
        ],
        path,
    )
    report = path.read_text(encoding="utf-8")
    assert "cited_first" in report
    assert "Winner" in report
    assert "concise" in report and "stepwise" in report


def test_write_report_refuses_to_mark_a_winner_when_a_variant_has_zero_cases(
    tmp_path: Path,
) -> None:
    path = tmp_path / "llm_eval.md"
    write_report(
        [
            _variant_score("concise", n=10, suggested=3.5),
            _variant_score("cited_first", n=0, suggested=0.0),
            _variant_score("stepwise", n=10, suggested=4.1),
        ],
        path,
    )
    report = path.read_text(encoding="utf-8")
    assert "Winner:" not in report
    assert "cited_first" in report
    assert "no winner" in report.lower()


def test_write_report_refuses_a_winner_with_fewer_than_three_variants(tmp_path: Path) -> None:
    path = tmp_path / "llm_eval.md"
    write_report([_variant_score("concise", n=10, suggested=4.0)], path)
    assert "Winner:" not in path.read_text(encoding="utf-8")


# ── score_variants ───────────────────────────────────────────────────────────


def test_score_variants_returns_one_row_per_variant_including_empty_ones() -> None:
    client = _ScriptedClient([_judge_body()])
    scores = score_variants({"concise": [_answered_case("concise")], "stepwise": []}, client=client)
    by_variant = {score.variant: score for score in scores}
    assert by_variant["stepwise"].n == 0
    assert by_variant["stepwise"].mean_faithfulness == 0.0
    assert by_variant["concise"].n == 1


def test_judge_score_model_allows_extra_fields() -> None:
    """Repo convention: every Pydantic model tolerates unexpected keys."""
    score = JudgeScore.model_validate(
        {
            "faithfulness": 4,
            "relevance": 4,
            "citation_quality": 4,
            "suggested_score": 4,
            "verdict": "fine",
            "judge_model": "m",
            "confidence": "high",
        }
    )
    assert score.confidence == "high"


def test_judge_renders_an_empty_citation_list_explicitly() -> None:
    """An answer with no citations must reach the judge as "(none)", not as a
    missing section the judge can read as "citations were not shown to me"."""
    client = _ScriptedClient([_judge_body(faithfulness=1, relevance=1)])
    judge("q?", "", [], client=client, variant="concise")
    user = next(m.content for m in client.calls[0] if m.role == "user")
    assert "(none)" in user
    assert "(the assistant returned nothing)" in user


def test_run_variant_rejects_an_unknown_variant() -> None:
    with pytest.raises(KeyError):
        run_variant("no_such_variant", [], client=_ScriptedClient([_judge_body()]))


def test_default_retrieve_keeps_the_original_ranking_when_rerank_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from homelib_rag import hybrid as hybrid_mod
    from homelib_rag import rerank as rerank_mod

    from evals.llm_eval import _default_retrieve

    hits = [_hit()]
    monkeypatch.setattr(hybrid_mod, "hybrid_search", lambda q, k, *, mode: (hits, "hybrid"))
    monkeypatch.setattr(rerank_mod, "rerank", lambda q, h: None)
    assert _default_retrieve("how?", 5) == hits

    monkeypatch.setattr(hybrid_mod, "hybrid_search", lambda q, k, *, mode: ([], "hybrid"))
    assert _default_retrieve("how?", 5) == []


# ── ground-truth selection ───────────────────────────────────────────────────


def _write_ground_truth(path: Path, rows: list[tuple[str, str]]) -> None:
    path.write_text(
        "\n".join(
            json.dumps({"question": q, "chunk_id": f"c{i}", "book_id": b})
            for i, (q, b) in enumerate(rows)
        )
        + "\n",
        encoding="utf-8",
    )


def test_load_questions_spreads_across_books_and_honours_the_budget(tmp_path: Path) -> None:
    """Taking the first N lines would sample one book; round-robin must not."""
    from evals.llm_eval import load_questions

    path = tmp_path / "ground_truth.jsonl"
    _write_ground_truth(
        path, [(f"q{i}?", "book-a") for i in range(10)] + [(f"r{i}?", "book-b") for i in range(10)]
    )

    picked = load_questions(path, budget=4)

    assert len(picked) == 4
    assert {row.book_id for row in picked} == {"book-a", "book-b"}


def test_load_questions_returns_everything_when_the_budget_exceeds_the_file(
    tmp_path: Path,
) -> None:
    from evals.llm_eval import load_questions

    path = tmp_path / "ground_truth.jsonl"
    _write_ground_truth(path, [("q?", "book-a"), ("r?", "book-b")])
    assert len(load_questions(path, budget=99)) == 2


# ── main() ───────────────────────────────────────────────────────────────────


def _install_fake_baseline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, floor: float) -> Path:
    from evals import llm_eval

    baseline_path = tmp_path / "eval-baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "metrics": {"judge.mean_faithfulness": floor, "hybrid_rerank.hit_rate_at_5": 0.7},
                "specs": {
                    "judge.mean_faithfulness": {
                        "key": "judge.mean_faithfulness",
                        "direction": "higher_is_better",
                        "margin": 0.15,
                    },
                    "hybrid_rerank.hit_rate_at_5": {
                        "key": "hybrid_rerank.hit_rate_at_5",
                        "direction": "higher_is_better",
                        "margin": 0.03,
                    },
                },
                "notes": {
                    "judge.mean_faithfulness": "fixture floor",
                    "hybrid_rerank.hit_rate_at_5": "fixture floor owned by the retrieval eval",
                },
            }
        ),
        encoding="utf-8",
    )
    history_path = tmp_path / "history.jsonl"
    monkeypatch.setattr(llm_eval, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(llm_eval, "HISTORY_PATH", history_path)
    return history_path


def _stub_run(monkeypatch: pytest.MonkeyPatch, scores: list[VariantScore]) -> None:
    from evals import llm_eval

    monkeypatch.setattr(
        llm_eval,
        "load_questions",
        lambda *a, **kw: [GroundTruthRow(question="q?", chunk_id="c1", book_id="b")],
    )
    monkeypatch.setattr(
        llm_eval, "run_variant", lambda variant, questions, **kw: [_answered_case(variant)]
    )
    monkeypatch.setattr(llm_eval, "score_variants", lambda cases, **kw: scores)


def test_main_writes_a_report_and_passes_the_judge_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from evals.llm_eval import main

    history = _install_fake_baseline(monkeypatch, tmp_path, floor=3.8)
    _stub_run(
        monkeypatch,
        [
            _variant_score("concise", n=5, suggested=3.9),
            _variant_score("cited_first", n=5, suggested=4.4),
            _variant_score("stepwise", n=5, suggested=4.0),
        ],
    )
    report = tmp_path / "llm_eval.md"

    assert main(["--report", str(report)]) == 0
    assert "Winner: `cited_first`" in report.read_text(encoding="utf-8")
    # Exactly one history line, and only the judge.* metric — the retrieval
    # floors belong to the retrieval eval and must not be reported missing.
    lines = history.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["metrics"] == {"judge.mean_faithfulness": 4.0}
    assert json.loads(lines[0])["regressions"] == []


def test_main_fails_the_gate_when_judge_faithfulness_regresses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from evals.llm_eval import main

    history = _install_fake_baseline(monkeypatch, tmp_path, floor=4.9)
    _stub_run(
        monkeypatch,
        [
            _variant_score("concise", n=5, suggested=3.9),
            _variant_score("cited_first", n=5, suggested=4.4),
            _variant_score("stepwise", n=5, suggested=4.0),
        ],
    )

    assert main(["--report", str(tmp_path / "llm_eval.md")]) == 1
    # The failing run is still recorded — history is a record of every attempt.
    assert json.loads(history.read_text(encoding="utf-8").strip())["regressions"] == [
        "judge.mean_faithfulness"
    ]


def test_main_refuses_and_exits_nonzero_when_an_arm_scored_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from evals.llm_eval import main

    history = _install_fake_baseline(monkeypatch, tmp_path, floor=3.8)
    _stub_run(
        monkeypatch,
        [
            _variant_score("concise", n=5, suggested=4.5),
            _variant_score("cited_first", n=0, suggested=0.0),
            _variant_score("stepwise", n=5, suggested=4.0),
        ],
    )
    report = tmp_path / "llm_eval.md"

    assert main(["--report", str(report)]) == 1
    assert "Winner:" not in report.read_text(encoding="utf-8")
    # No winner means no measurement, so nothing is written to the audit trail
    # that a later run could mistake for a real judge score.
    assert not history.exists()


def test_main_can_restrict_to_a_single_variant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from evals import llm_eval

    _install_fake_baseline(monkeypatch, tmp_path, floor=3.8)
    seen: list[str] = []
    monkeypatch.setattr(
        llm_eval,
        "load_questions",
        lambda *a, **kw: [GroundTruthRow(question="q?", chunk_id="c1", book_id="b")],
    )

    def _record(variant: str, questions: list[GroundTruthRow], **kw: object) -> list[AnsweredCase]:
        seen.append(variant)
        return [_answered_case(variant)]

    monkeypatch.setattr(llm_eval, "run_variant", _record)
    monkeypatch.setattr(
        llm_eval,
        "score_variants",
        lambda cases, **kw: [_variant_score("concise", n=5, suggested=4.0)],
    )

    # One arm cannot crown a winner, so the exit code is 1 by design.
    assert llm_eval.main(["--variant", "concise", "--report", str(tmp_path / "r.md")]) == 1
    assert seen == ["concise"]


def test_report_flags_a_winner_that_declined_most_often() -> None:
    """A variant can win by answering less, and the report must say so.

    `degraded=False, citations=[]` is a legitimate reply, but it counts as a
    success. With a judge scoring everything near 2/5 there is little room to
    punish reticence, so the arm that hedges most can top the table while
    being worse at the job. The ranking is not wrong here, it is
    uninterpretable — and the report has to say which.
    """
    scores = [
        VariantScore(
            variant="hedger",
            n=10,
            mean_faithfulness=3.0,
            mean_relevance=3.0,
            mean_citation_quality=3.0,
            mean_suggested_score=3.0,
            n_answered=10,
            n_ungrounded=8,
        ),
        VariantScore(
            variant="committer",
            n=10,
            mean_faithfulness=2.0,
            mean_relevance=2.0,
            mean_citation_quality=2.0,
            mean_suggested_score=2.0,
            n_answered=10,
            n_ungrounded=1,
        ),
        VariantScore(
            variant="third",
            n=10,
            mean_faithfulness=2.0,
            mean_relevance=2.0,
            mean_citation_quality=2.0,
            mean_suggested_score=1.5,
            n_answered=10,
            n_ungrounded=0,
        ),
    ]
    path = Path(tempfile.mkdtemp()) / "llm_eval.md"

    write_report(scores, path)
    body = path.read_text()

    assert "Winner: `hedger`" in body
    assert "unproven" in body
    assert "8/10" in body


def test_report_does_not_flag_a_winner_that_grounded_its_answers() -> None:
    """The caveat must not fire on every winner, or it says nothing."""
    scores = [
        VariantScore(
            variant="good",
            n=10,
            mean_faithfulness=3.0,
            mean_relevance=3.0,
            mean_citation_quality=3.0,
            mean_suggested_score=3.0,
            n_answered=10,
            n_ungrounded=0,
        ),
        VariantScore(
            variant="worse",
            n=10,
            mean_faithfulness=2.0,
            mean_relevance=2.0,
            mean_citation_quality=2.0,
            mean_suggested_score=2.0,
            n_answered=10,
            n_ungrounded=5,
        ),
        VariantScore(
            variant="third",
            n=10,
            mean_faithfulness=2.0,
            mean_relevance=2.0,
            mean_citation_quality=2.0,
            mean_suggested_score=1.5,
            n_answered=10,
            n_ungrounded=2,
        ),
    ]
    path = Path(tempfile.mkdtemp()) / "llm_eval.md"

    write_report(scores, path)

    assert "unproven" not in path.read_text()
