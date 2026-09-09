"""Regression tests for Ask ranking helpers — LIVE living-deliberately gap."""

from __future__ import annotations

import pytest
from homelib_rag.hybrid import (
    boost_books_named_in_query,
    merge_unique_hits,
    promote_query_overlap,
    promote_verbatim_phrase,
)
from homelib_rag.models import Hit


def _hit(chunk_id: str, text: str, *, book_id: str = "book-a", rank: int = 1) -> Hit:
    return Hit(
        chunk_id=chunk_id,
        book_id=book_id,
        score=0.5,
        rank=rank,
        text=text,
        section_path=["Chapter"],
        page=1,
    )


def test_promote_verbatim_phrase_keeps_exact_body_first() -> None:
    phrase = "I went to the woods because I wished to live deliberately"
    hits = [
        _hit("noise", "Unrelated conclusion paragraph.", rank=1),
        _hit("exact", f"Lead-in. {phrase} More.", rank=2),
    ]
    ordered = promote_verbatim_phrase(phrase, hits)
    assert ordered[0].chunk_id == "exact"


def test_promote_query_overlap_ranks_living_deliberately_passage_first() -> None:
    """Ask questions rarely equal a passage; overlap must still surface it."""
    question = "What does Thoreau say about living deliberately in Walden?"
    hits = [
        _hit("conclusion", "The end of Walden is quiet.", book_id="walden", rank=1),
        _hit(
            "woods",
            "I went to the woods because I wished to live deliberately, "
            "to front only the essential facts of life.",
            book_id="walden",
            rank=2,
        ),
        _hit("other", "Ford discusses pig iron.", book_id="ford", rank=3),
    ]
    ordered = promote_query_overlap(question, hits)
    assert ordered[0].chunk_id == "woods"


def test_boost_books_named_in_query_prefers_walden() -> None:
    hits = [
        _hit("a", "noise", book_id="other", rank=1),
        _hit("b", "woods", book_id="thoreau-walden", rank=2),
    ]
    titles = {
        "thoreau-walden": "Walden, and On The Duty Of Civil Disobedience",
        "other": "My Life and Work",
    }
    ordered = boost_books_named_in_query(
        "What does Thoreau say about living deliberately in Walden?",
        hits,
        titles,
    )
    assert ordered[0].book_id == "thoreau-walden"


def test_merge_unique_hits_preserves_first_chunk() -> None:
    a = [_hit("shared", "first", rank=1), _hit("only-a", "a", rank=2)]
    b = [_hit("shared", "second", rank=1), _hit("only-b", "b", rank=2)]
    merged = merge_unique_hits(a, b, k=3)
    assert [h.chunk_id for h in merged] == ["shared", "only-a", "only-b"]
    assert merged[0].text == "first"


def test_promote_verbatim_phrase_empty_query_is_noop() -> None:
    hits = [_hit("a", "text")]
    assert promote_verbatim_phrase("   ", hits) is hits


def test_promote_query_overlap_short_query_falls_back_to_verbatim() -> None:
    hits = [
        _hit("noise", "zzz", rank=1),
        _hit("exact", "abc def", rank=2),
    ]
    ordered = promote_query_overlap("abc def", hits)
    assert ordered[0].chunk_id == "exact"


def test_boost_books_named_in_query_noop_without_titles() -> None:
    hits = [_hit("a", "text")]
    assert boost_books_named_in_query("Walden", hits, {}) is hits


def test_boost_books_named_in_query_matches_title_token() -> None:
    """Full title need not appear; a distinctive token like Walden is enough."""
    hits = [
        _hit("a", "noise", book_id="other", rank=1),
        _hit("b", "woods", book_id="thoreau-walden", rank=2),
    ]
    titles = {"thoreau-walden": "Walden; Or, Life in the Woods", "other": "My Life and Work"}
    ordered = boost_books_named_in_query("living deliberately in walden", hits, titles)
    assert ordered[0].book_id == "thoreau-walden"


def test_promote_query_overlap_token_prefix_match_without_phrase() -> None:
    """When the full n-gram is absent, matching content tokens still rank."""
    question = "living deliberately deliberately living"
    hits = [
        _hit("noise", "unrelated industrial pig iron notes", rank=1),
        _hit(
            "near",
            "I wished to live and act deliberately among the woods.",
            rank=2,
        ),
    ]
    ordered = promote_query_overlap(question, hits)
    assert ordered[0].chunk_id == "near"


def test_boost_books_named_in_query_returns_input_when_no_title_match() -> None:
    hits = [_hit("a", "noise", book_id="other", rank=1)]
    titles = {"thoreau-walden": "Walden; Or, Life in the Woods"}
    assert boost_books_named_in_query("ford factory pig iron", hits, titles) is hits


def test_boost_books_named_in_query_ignores_generic_title_words() -> None:
    """'style' / 'story' / 'civil' are title tokens, not book names."""
    hits = [
        _hit("ford", "factory", book_id="ford", rank=1),
        _hit("strunk", "usage", book_id="strunk", rank=2),
        _hit("keller", "childhood", book_id="keller", rank=3),
        _hit("walden", "woods", book_id="thoreau-walden", rank=4),
    ]
    titles = {
        "strunk": "The Elements of Style",
        "keller": "The Story of My Life",
        "thoreau-walden": "Walden, and On The Duty Of Civil Disobedience",
        "ford": "My Life and Work",
    }
    original = [h.book_id for h in hits]
    styled = boost_books_named_in_query("what makes a good writing style", hits, titles)
    assert [h.book_id for h in styled] == original

    storied = boost_books_named_in_query("tell me a story about factories", hits, titles)
    assert [h.book_id for h in storied] == original

    civic = boost_books_named_in_query("civil engineering career advice", hits, titles)
    assert [h.book_id for h in civic] == original


def test_boost_books_named_in_query_still_matches_subtitle_bigram() -> None:
    hits = [
        _hit("ford", "factory", book_id="ford", rank=1),
        _hit("walden", "woods", book_id="thoreau-walden", rank=2),
    ]
    titles = {
        "thoreau-walden": "Walden, and On The Duty Of Civil Disobedience",
        "ford": "My Life and Work",
    }
    ordered = boost_books_named_in_query("civil disobedience in practice", hits, titles)
    assert ordered[0].book_id == "thoreau-walden"


def test_hybrid_lazy_search_wrappers_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    from homelib_rag import hybrid as hybrid_mod

    monkeypatch.setattr(
        "homelib_rag.index.search_lexical",
        lambda q, k: [_hit("lex", q, rank=1)],
    )
    monkeypatch.setattr(
        "homelib_rag.index.search_vector",
        lambda q, k: [_hit("vec", q, rank=1)],
    )
    assert hybrid_mod.search_lexical("hello", 3)[0].chunk_id == "lex"
    assert hybrid_mod.search_vector("hello", 3)[0].chunk_id == "vec"


def test_merge_unique_hits_caps_at_k() -> None:
    a = [_hit("1", "a", rank=1), _hit("2", "b", rank=2), _hit("3", "c", rank=3)]
    merged = merge_unique_hits(a, k=2)
    assert [h.chunk_id for h in merged] == ["1", "2"]
    assert [h.rank for h in merged] == [1, 2]
