"""Tests for LLM response parsing (no actual API calls)."""

from reddit_network.aggregator import SubredditStat
from reddit_network.llm_filter import _fallback, _parse_response


def _make_stat(name: str, commenter_count: int = 5, total_activity: int = 20) -> SubredditStat:
    return SubredditStat(
        name=name,
        commenter_count=commenter_count,
        total_activity=total_activity,
        avg_score=10.0,
    )


class TestParseResponse:
    def test_valid_json(self):
        raw = """[
            {"name": "MachineLearning", "relevance": 9, "reason": "Core ML sub"},
            {"name": "Python", "relevance": 7, "reason": "Primary language"}
        ]"""
        original = [_make_stat("MachineLearning"), _make_stat("Python")]
        result = _parse_response(raw, original, min_relevance=5)
        assert len(result) == 2
        assert result[0].name == "MachineLearning"
        assert result[0].relevance_score == 9

    def test_filters_below_min_relevance(self):
        raw = """[
            {"name": "MachineLearning", "relevance": 9, "reason": "Core"},
            {"name": "hiking", "relevance": 2, "reason": "Unrelated"}
        ]"""
        original = [_make_stat("MachineLearning"), _make_stat("hiking")]
        result = _parse_response(raw, original, min_relevance=5)
        assert len(result) == 1
        assert result[0].name == "MachineLearning"

    def test_handles_markdown_code_fences(self):
        raw = """```json
[{"name": "Python", "relevance": 8, "reason": "Language"}]
```"""
        original = [_make_stat("Python")]
        result = _parse_response(raw, original, min_relevance=5)
        assert len(result) == 1

    def test_invalid_json_returns_fallback(self):
        raw = "This is not JSON at all"
        original = [_make_stat("Python")]
        result = _parse_response(raw, original, min_relevance=5)
        # Fallback returns all with relevance_score = -1
        assert len(result) == 1
        assert result[0].relevance_score == -1

    def test_not_a_list_returns_fallback(self):
        raw = '{"name": "Python", "relevance": 8}'
        original = [_make_stat("Python")]
        result = _parse_response(raw, original, min_relevance=5)
        assert result[0].relevance_score == -1

    def test_preserves_original_stats(self):
        raw = '[{"name": "Python", "relevance": 8, "reason": "Language"}]'
        original = [_make_stat("Python", commenter_count=12, total_activity=45)]
        result = _parse_response(raw, original, min_relevance=5)
        assert result[0].commenter_count == 12
        assert result[0].total_activity == 45

    def test_string_relevance_score_coerced(self):
        raw = '[{"name": "Python", "relevance": "8", "reason": "Language"}]'
        original = [_make_stat("Python")]
        result = _parse_response(raw, original, min_relevance=5)
        assert result[0].relevance_score == 8

    def test_strips_r_prefix_from_llm_names(self):
        raw = '[{"name": "r/Python", "relevance": 8, "reason": "Language"}]'
        original = [_make_stat("Python", commenter_count=7, total_activity=30)]
        result = _parse_response(raw, original, min_relevance=5)
        assert len(result) == 1
        assert result[0].name == "Python"
        assert result[0].commenter_count == 7  # matched back to original

    def test_sorted_by_relevance(self):
        raw = """[
            {"name": "SubA", "relevance": 6, "reason": "ok"},
            {"name": "SubB", "relevance": 9, "reason": "great"}
        ]"""
        original = [_make_stat("SubA"), _make_stat("SubB")]
        result = _parse_response(raw, original, min_relevance=5)
        assert result[0].name == "SubB"


class TestFallback:
    def test_returns_all_unscored(self):
        original = [_make_stat("Python"), _make_stat("Rust")]
        result = _fallback(original)
        assert len(result) == 2
        assert all(s.relevance_score == -1 for s in result)
        assert all("unavailable" in s.reason for s in result)
