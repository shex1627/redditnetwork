"""Tests for URL parsing and config utilities."""

import pytest

from reddit_network.config import parse_post_url


class TestParsePostUrl:
    def test_standard_url(self):
        url = "https://www.reddit.com/r/datascience/comments/abc123/best_practices/"
        assert parse_post_url(url) == "abc123"

    def test_old_reddit(self):
        url = "https://old.reddit.com/r/Python/comments/xyz789/async_tips/"
        assert parse_post_url(url) == "xyz789"

    def test_no_trailing_slash(self):
        url = "https://reddit.com/r/datascience/comments/abc123"
        assert parse_post_url(url) == "abc123"

    def test_with_query_params(self):
        url = "https://www.reddit.com/r/datascience/comments/abc123/title/?sort=top"
        assert parse_post_url(url) == "abc123"

    def test_short_link(self):
        url = "https://redd.it/abc123"
        assert parse_post_url(url) == "abc123"

    def test_no_scheme(self):
        url = "reddit.com/r/Python/comments/abc123/title/"
        assert parse_post_url(url) == "abc123"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            parse_post_url("https://youtube.com/watch?v=123")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            parse_post_url("")
