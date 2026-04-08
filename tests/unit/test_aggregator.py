"""Tests for subreddit aggregation logic."""

from tests.conftest import make_profile

from reddit_network.aggregator import aggregate_subreddits


class TestAggregateSubreddits:
    def test_basic_aggregation(self):
        profiles = [
            make_profile(
                username="alice",
                activities=[("Python", 10), ("MachineLearning", 20)],
            ),
            make_profile(
                username="bob",
                activities=[("Python", 5), ("Rust", 15)],
            ),
        ]
        result = aggregate_subreddits(profiles, source_subreddit="datascience")

        names = {s.name for s in result}
        # Python has 2 commenters, should appear
        assert "Python" in names
        # Rust has only 1 commenter, should be filtered (min_commenter_count=2)
        assert "Rust" not in names

    def test_source_subreddit_excluded(self):
        profiles = [
            make_profile(
                username="alice",
                activities=[("datascience", 10), ("Python", 5)],
            ),
            make_profile(
                username="bob",
                activities=[("datascience", 20), ("Python", 8)],
            ),
        ]
        result = aggregate_subreddits(profiles, source_subreddit="datascience")
        names = {s.name for s in result}
        assert "datascience" not in names

    def test_mega_subreddits_filtered(self):
        profiles = [
            make_profile(
                username="alice",
                activities=[("AskReddit", 100), ("Python", 5)],
            ),
            make_profile(
                username="bob",
                activities=[("AskReddit", 200), ("Python", 8)],
            ),
        ]
        result = aggregate_subreddits(profiles, source_subreddit="datascience")
        names = {s.name.lower() for s in result}
        assert "askreddit" not in names

    def test_case_insensitive_blocklist(self):
        profiles = [
            make_profile(
                username="alice",
                activities=[("FUNNY", 1), ("Python", 5)],
            ),
            make_profile(
                username="bob",
                activities=[("funny", 2), ("Python", 8)],
            ),
        ]
        result = aggregate_subreddits(profiles, source_subreddit="datascience")
        names = {s.name.lower() for s in result}
        assert "funny" not in names

    def test_min_commenter_count(self):
        profiles = [
            make_profile(
                username="alice",
                activities=[("NicheSubA", 10)],
            ),
            make_profile(
                username="bob",
                activities=[("NicheSubB", 10)],
            ),
        ]
        # Each sub only has 1 commenter, default min is 2
        result = aggregate_subreddits(profiles, source_subreddit="datascience")
        assert len(result) == 0

    def test_min_commenter_count_override(self):
        profiles = [
            make_profile(
                username="alice",
                activities=[("NicheSubA", 10)],
            ),
        ]
        result = aggregate_subreddits(
            profiles, source_subreddit="datascience", min_commenter_count=1
        )
        assert len(result) == 1
        assert result[0].name == "NicheSubA"

    def test_sorted_by_commenter_count(self):
        profiles = [
            make_profile(
                username="alice",
                activities=[("SubA", 1), ("SubB", 1)],
            ),
            make_profile(
                username="bob",
                activities=[("SubA", 1), ("SubB", 1)],
            ),
            make_profile(
                username="carol",
                activities=[("SubA", 1)],
            ),
        ]
        result = aggregate_subreddits(
            profiles, source_subreddit="other", min_commenter_count=2
        )
        assert result[0].name == "SubA"  # 3 commenters
        assert result[1].name == "SubB"  # 2 commenters

    def test_empty_profiles(self):
        result = aggregate_subreddits([], source_subreddit="datascience")
        assert result == []

    def test_activity_counts(self):
        profiles = [
            make_profile(
                username="alice",
                activities=[("Python", 10), ("Python", 20)],
            ),
            make_profile(
                username="bob",
                activities=[("Python", 5)],
            ),
        ]
        result = aggregate_subreddits(
            profiles, source_subreddit="other", min_commenter_count=1
        )
        python_stat = next(s for s in result if s.name == "Python")
        assert python_stat.commenter_count == 2
        assert python_stat.total_activity == 3  # 2 from alice + 1 from bob
