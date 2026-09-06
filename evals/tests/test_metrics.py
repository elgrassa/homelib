"""Tests for evals/metrics.py — hand-computed against the metric definitions.

Reimplemented independently of any retrieval/index code; the hand-computed
tests below pin the implementation to the published definitions in
specs/evals-retrieval.md, not to itself.
"""

import pytest

from evals.metrics import (
    GroundTruth,
    GroundTruthBooks,
    RankedBooks,
    RankedResults,
    hit_rate_at_k,
    hit_rate_book,
    mrr_at_k,
)


def test_hit_rate_hand_computed() -> None:
    # Three queries, top-5 rankings, one relevant chunk id each:
    #   q1: relevant "c1" at rank 1 -> hit
    #   q2: relevant "c2" at rank 4 -> hit (4 <= k=5)
    #   q3: relevant "c3" absent    -> miss
    # hit-rate@5 = (1 + 1 + 0) / 3 = 2/3
    results: RankedResults = {
        "q1": ["c1", "x", "y", "z", "w"],
        "q2": ["a", "b", "c", "c2", "e"],
        "q3": ["p", "q", "r", "s", "t"],
    }
    relevant: GroundTruth = {"q1": ["c1"], "q2": ["c2"], "q3": ["c3"]}

    assert hit_rate_at_k(results, relevant, k=5) == pytest.approx(2 / 3)


def test_mrr_hand_computed() -> None:
    # Same toy case as test_hit_rate_hand_computed:
    #   q1: rank 1 -> 1/1 = 1.0
    #   q2: rank 4 -> 1/4 = 0.25
    #   q3: absent -> 0.0
    # MRR@5 = (1/1 + 1/4 + 0) / 3 = 1.25 / 3 = 0.41666...
    # Note this genuinely differs from hit-rate@5 (2/3 = 0.6667) on the same
    # data: MRR discounts the rank-4 hit, hit-rate does not.
    results: RankedResults = {
        "q1": ["c1", "x", "y", "z", "w"],
        "q2": ["a", "b", "c", "c2", "e"],
        "q3": ["p", "q", "r", "s", "t"],
    }
    relevant: GroundTruth = {"q1": ["c1"], "q2": ["c2"], "q3": ["c3"]}

    expected = (1 / 1 + 1 / 4 + 0) / 3
    assert mrr_at_k(results, relevant, k=5) == pytest.approx(expected)
    assert mrr_at_k(results, relevant, k=5) != pytest.approx(hit_rate_at_k(results, relevant, k=5))


def test_hit_rate_book_counts_same_book_hit() -> None:
    # q1: the top-5 chunk ranking is entirely WRONG chunk ids, but every one
    #     of them belongs to the same book as the relevant chunk -> book hit,
    #     even though chunk-level hit_rate_at_k would score this a total miss.
    # q2: top-5 books never include the relevant book -> book miss.
    # q3: the relevant book appears, but only at rank 4 -> still a hit at
    #     k=5 (hit-rate does not discount by rank, unlike MRR).
    book_results: RankedBooks = {
        "q1": ["book-a", "book-a", "book-a", "book-a", "book-a"],
        "q2": ["book-x", "book-y", "book-z", "book-w", "book-v"],
        "q3": ["book-x", "book-y", "book-z", "book-b", "book-w"],
    }
    relevant_books: GroundTruthBooks = {"q1": ["book-a"], "q2": ["book-b"], "q3": ["book-b"]}

    # Chunk-level hit-rate on the SAME q1 ranking is 0.0: none of the ranked
    # chunk ids equal the relevant chunk id "c1", even though they share its
    # book. This is the exact gap hit_rate_book exists to surface.
    chunk_results: RankedResults = {"q1": ["x1", "x2", "x3", "x4", "x5"]}
    chunk_relevant: GroundTruth = {"q1": ["c1"]}
    assert hit_rate_at_k(chunk_results, chunk_relevant, k=5) == pytest.approx(0.0)

    assert hit_rate_book(book_results, relevant_books, k=5) == pytest.approx(2 / 3)


def test_hit_rate_book_matches_hit_rate_at_k_on_the_same_id_space() -> None:
    # hit_rate_book is hit_rate_at_k over book ids rather than chunk ids —
    # pin that it is not a silently different computation.
    results: RankedBooks = {"q1": ["book-a", "book-b"], "q2": ["book-c"]}
    relevant: GroundTruthBooks = {"q1": ["book-a"], "q2": ["book-d"]}

    assert hit_rate_book(results, relevant, k=5) == pytest.approx(
        hit_rate_at_k(results, relevant, k=5)
    )


def test_hit_rate_and_mrr_agree_when_relevant_always_rank_one() -> None:
    results: RankedResults = {
        "q1": ["c1", "x"],
        "q2": ["c2", "y", "z"],
        "q3": ["c3"],
    }
    relevant: GroundTruth = {"q1": ["c1"], "q2": ["c2"], "q3": ["c3"]}

    assert hit_rate_at_k(results, relevant, k=5) == pytest.approx(1.0)
    assert mrr_at_k(results, relevant, k=5) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Edge cases. Each `_case_*` helper is exercised both as its own pytest test
# (for isolated failure reporting) and again from `test_metrics_edge_cases`,
# the single named test the WP-12 brief requires to cover all of them.
# ---------------------------------------------------------------------------


def _case_empty_result_list_is_a_miss_not_an_error() -> None:
    results: RankedResults = {"q1": []}
    relevant: GroundTruth = {"q1": ["c1"]}

    assert hit_rate_at_k(results, relevant, k=5) == pytest.approx(0.0)
    assert mrr_at_k(results, relevant, k=5) == pytest.approx(0.0)


def _case_missing_query_in_results_behaves_like_empty_list() -> None:
    results: RankedResults = {}
    relevant: GroundTruth = {"q1": ["c1"]}

    assert hit_rate_at_k(results, relevant, k=5) == pytest.approx(0.0)
    assert mrr_at_k(results, relevant, k=5) == pytest.approx(0.0)


def _case_k_larger_than_the_result_list() -> None:
    # Only 2 results exist; k=10 must not raise or index out of range.
    results: RankedResults = {"q1": ["a", "c1"]}
    relevant: GroundTruth = {"q1": ["c1"]}

    assert hit_rate_at_k(results, relevant, k=10) == pytest.approx(1.0)
    assert mrr_at_k(results, relevant, k=10) == pytest.approx(0.5)  # rank 2


def _case_query_with_no_relevant_item_in_range() -> None:
    # "c1" is present but at rank 4, outside a k=3 window: a miss caused by
    # truncation, distinct from "c1" never appearing in the ranking at all.
    results: RankedResults = {"q1": ["a", "b", "c", "c1", "d"]}
    relevant: GroundTruth = {"q1": ["c1"]}

    assert hit_rate_at_k(results, relevant, k=3) == pytest.approx(0.0)
    assert mrr_at_k(results, relevant, k=3) == pytest.approx(0.0)


def _case_duplicate_ids_in_the_ranking_use_first_occurrence() -> None:
    # "c1" appears twice; the rank used must be the FIRST occurrence (2), not
    # the last (4).
    results: RankedResults = {"q1": ["x", "c1", "y", "c1", "z"]}
    relevant: GroundTruth = {"q1": ["c1"]}

    assert hit_rate_at_k(results, relevant, k=5) == pytest.approx(1.0)
    assert mrr_at_k(results, relevant, k=5) == pytest.approx(0.5)  # rank 2, not rank 4


def _case_multiple_relevant_ids_first_match_wins_for_mrr() -> None:
    results: RankedResults = {"q1": ["a", "b", "c2", "c1"]}
    relevant: GroundTruth = {"q1": ["c1", "c2"]}

    assert hit_rate_at_k(results, relevant, k=4) == pytest.approx(1.0)
    assert mrr_at_k(results, relevant, k=4) == pytest.approx(1 / 3)  # c2 at rank 3


def _case_k_less_or_equal_zero_raises(k: int) -> None:
    results: RankedResults = {"q1": ["c1"]}
    relevant: GroundTruth = {"q1": ["c1"]}

    with pytest.raises(ValueError, match="k must be a positive integer"):
        hit_rate_at_k(results, relevant, k)
    with pytest.raises(ValueError, match="k must be a positive integer"):
        mrr_at_k(results, relevant, k)


def _case_empty_relevant_mapping_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        hit_rate_at_k({}, {}, k=5)
    with pytest.raises(ValueError, match="empty"):
        mrr_at_k({}, {}, k=5)


def test_empty_result_list_is_a_miss_not_an_error() -> None:
    _case_empty_result_list_is_a_miss_not_an_error()


def test_missing_query_in_results_behaves_like_empty_list() -> None:
    _case_missing_query_in_results_behaves_like_empty_list()


def test_k_larger_than_the_result_list() -> None:
    _case_k_larger_than_the_result_list()


def test_query_with_no_relevant_item_in_range() -> None:
    _case_query_with_no_relevant_item_in_range()


def test_duplicate_ids_in_the_ranking_use_first_occurrence() -> None:
    _case_duplicate_ids_in_the_ranking_use_first_occurrence()


def test_multiple_relevant_ids_first_match_wins_for_mrr() -> None:
    _case_multiple_relevant_ids_first_match_wins_for_mrr()


@pytest.mark.parametrize("k", [0, -1, -5])
def test_k_less_or_equal_zero_raises(k: int) -> None:
    _case_k_less_or_equal_zero_raises(k)


def test_empty_relevant_mapping_raises() -> None:
    _case_empty_relevant_mapping_raises()


def test_metrics_edge_cases() -> None:
    """Umbrella test wiring together every edge case named in the WP-12 brief:
    empty result list, k larger than the result list, a query with no
    relevant item in range, duplicate ids in the ranking, and k <= 0 raising.
    """
    _case_empty_result_list_is_a_miss_not_an_error()
    _case_missing_query_in_results_behaves_like_empty_list()
    _case_k_larger_than_the_result_list()
    _case_query_with_no_relevant_item_in_range()
    _case_duplicate_ids_in_the_ranking_use_first_occurrence()
    _case_multiple_relevant_ids_first_match_wins_for_mrr()
    for k in (0, -1, -5):
        _case_k_less_or_equal_zero_raises(k)
    _case_empty_relevant_mapping_raises()
