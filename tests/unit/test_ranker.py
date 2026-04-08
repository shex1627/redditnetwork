"""Tests for commenter ranking logic."""

from tests.conftest import make_comment, make_profile

from reddit_network.ranker import rank_commenters


class TestRankCommenters:
    def test_higher_score_ranks_first(self):
        comments = [
            make_comment(author="low", score=10, body="short"),
            make_comment(author="high", score=500, body="a" * 1000),
        ]
        profiles = {
            "low": make_profile(username="low", comment_karma=100, account_age_days=30),
            "high": make_profile(
                username="high", comment_karma=50000, account_age_days=2000
            ),
        }
        ranked = rank_commenters(comments, profiles, top_n=2)
        assert ranked[0].username == "high"
        assert ranked[1].username == "low"

    def test_respects_top_n(self):
        comments = [make_comment(author=f"user{i}", score=i) for i in range(10)]
        profiles = {
            f"user{i}": make_profile(username=f"user{i}") for i in range(10)
        }
        ranked = rank_commenters(comments, profiles, top_n=3)
        assert len(ranked) == 3

    def test_skips_missing_profiles(self):
        comments = [
            make_comment(author="found", score=100),
            make_comment(author="missing", score=200),
        ]
        profiles = {"found": make_profile(username="found")}
        ranked = rank_commenters(comments, profiles, top_n=10)
        assert len(ranked) == 1
        assert ranked[0].username == "found"

    def test_deduplicates_same_author(self):
        comments = [
            make_comment(author="alice", score=100, body="first"),
            make_comment(author="alice", score=50, body="second"),
            make_comment(author="bob", score=80, body="only one"),
        ]
        profiles = {
            "alice": make_profile(username="alice"),
            "bob": make_profile(username="bob"),
        }
        ranked = rank_commenters(comments, profiles, top_n=10)
        usernames = [r.username for r in ranked]
        assert usernames.count("alice") == 1

    def test_empty_comments_returns_empty(self):
        ranked = rank_commenters([], {}, top_n=10)
        assert ranked == []

    def test_zero_karma_does_not_crash(self):
        comments = [make_comment(author="newbie", score=1, body="hi")]
        profiles = {
            "newbie": make_profile(
                username="newbie", comment_karma=0, account_age_days=0
            )
        }
        ranked = rank_commenters(comments, profiles, top_n=1)
        assert len(ranked) == 1

    def test_custom_weights(self):
        """When comment_score weight is 1.0 and everything else is 0, pure score wins."""
        comments = [
            make_comment(author="high_score", score=999, body="x"),
            make_comment(author="long_post", score=1, body="x" * 10000),
        ]
        profiles = {
            "high_score": make_profile(
                username="high_score", comment_karma=1, account_age_days=1
            ),
            "long_post": make_profile(
                username="long_post", comment_karma=999999, account_age_days=9999
            ),
        }
        weights = {
            "comment_score": 1.0,
            "comment_length": 0.0,
            "account_age": 0.0,
            "comment_karma": 0.0,
        }
        ranked = rank_commenters(comments, profiles, top_n=2, weights=weights)
        assert ranked[0].username == "high_score"
