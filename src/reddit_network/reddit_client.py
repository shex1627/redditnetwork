"""PRAW wrapper — fetch posts, comments, and user histories with error isolation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import praw
import prawcore

from reddit_network.config import (
    DEFAULT_COMMENT_FETCH_LIMIT,
    DEFAULT_USER_HISTORY_LIMIT,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PostInfo:
    post_id: str
    title: str
    subreddit: str
    score: int
    num_comments: int
    url: str
    author: str | None = None


@dataclass
class CommentInfo:
    author: str
    body: str
    score: int
    created_utc: float


@dataclass
class UserActivity:
    """A single post or comment by a user."""

    subreddit: str
    score: int
    kind: str  # "comment" or "submission"


@dataclass
class UserProfile:
    username: str
    comment_karma: int
    created_utc: float
    activities: list[UserActivity] = field(default_factory=list)

    @property
    def account_age_days(self) -> float:
        now = datetime.now(timezone.utc).timestamp()
        return (now - self.created_utc) / 86400


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def get_reddit_client() -> praw.Reddit:
    """Create a read-only Reddit client. Only needs client_id + client_secret."""
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )


def fetch_post(reddit: praw.Reddit, post_id: str) -> PostInfo:
    """Fetch metadata for a single post."""
    submission = reddit.submission(id=post_id)
    # Force fetch by accessing an attribute
    _ = submission.title
    author = submission.author.name if submission.author else None
    return PostInfo(
        post_id=submission.id,
        title=submission.title,
        subreddit=submission.subreddit.display_name,
        score=submission.score,
        num_comments=submission.num_comments,
        url=submission.url,
        author=author,
    )


def fetch_top_comments(
    reddit: praw.Reddit,
    post_id: str,
    limit: int = DEFAULT_COMMENT_FETCH_LIMIT,
) -> list[CommentInfo]:
    """Fetch top-level comments sorted by score (top)."""
    submission = reddit.submission(id=post_id)
    submission.comment_sort = "top"
    submission.comments.replace_more(limit=0)  # skip "load more" links

    comments: list[CommentInfo] = []
    for comment in submission.comments[:limit]:
        if isinstance(comment, praw.models.MoreComments):
            continue
        if comment.author is None:
            continue  # deleted
        comments.append(
            CommentInfo(
                author=comment.author.name,
                body=comment.body,
                score=comment.score,
                created_utc=comment.created_utc,
            )
        )
    return comments


def fetch_user_profile(
    reddit: praw.Reddit,
    username: str,
    history_limit: int = DEFAULT_USER_HISTORY_LIMIT,
) -> UserProfile | None:
    """Fetch a user's profile and recent activity.

    Returns None if the user is private, suspended, or otherwise inaccessible.
    Error isolation: one bad user never crashes the pipeline.
    """
    try:
        redditor = reddit.redditor(username)
        # Force-fetch profile data
        comment_karma = redditor.comment_karma
        created_utc = redditor.created_utc
    except (
        prawcore.exceptions.NotFound,
        prawcore.exceptions.Forbidden,
        prawcore.exceptions.BadRequest,
        AttributeError,
    ) as exc:
        logger.warning("Skipping user %s: %s", username, exc)
        return None

    activities: list[UserActivity] = []
    try:
        for item in redditor.new(limit=history_limit):
            kind = (
                "comment"
                if isinstance(item, praw.models.Comment)
                else "submission"
            )
            activities.append(
                UserActivity(
                    subreddit=item.subreddit.display_name,
                    score=item.score,
                    kind=kind,
                )
            )
    except (
        prawcore.exceptions.NotFound,
        prawcore.exceptions.Forbidden,
        prawcore.exceptions.BadRequest,
    ) as exc:
        logger.warning("Could not fetch history for %s: %s", username, exc)
        # Return profile with whatever activities we got so far

    return UserProfile(
        username=username,
        comment_karma=comment_karma,
        created_utc=created_utc,
        activities=activities,
    )
