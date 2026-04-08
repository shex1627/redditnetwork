"""Shared test fixtures and factory helpers."""

from __future__ import annotations

import time

from reddit_network.reddit_client import CommentInfo, UserActivity, UserProfile


def make_comment(
    author: str = "test_user",
    body: str = "This is a test comment.",
    score: int = 100,
    created_utc: float | None = None,
) -> CommentInfo:
    return CommentInfo(
        author=author,
        body=body,
        score=score,
        created_utc=created_utc or time.time(),
    )


def make_profile(
    username: str = "test_user",
    comment_karma: int = 10000,
    account_age_days: float = 365.0,
    activities: list[tuple[str, int]] | None = None,
) -> UserProfile:
    """Create a UserProfile.

    activities: list of (subreddit_name, score) tuples.
    """
    created_utc = time.time() - (account_age_days * 86400)
    acts = [
        UserActivity(subreddit=sub, score=sc, kind="comment")
        for sub, sc in (activities or [])
    ]
    return UserProfile(
        username=username,
        comment_karma=comment_karma,
        created_utc=created_utc,
        activities=acts,
    )
