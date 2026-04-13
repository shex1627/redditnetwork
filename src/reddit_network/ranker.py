"""Rank commenters by static criteria (upvotes, length, karma, account age)."""

from __future__ import annotations

from dataclasses import dataclass

from reddit_network.config import RANKING_WEIGHTS
from reddit_network.reddit_client import CommentInfo, UserProfile


@dataclass
class RankedCommenter:
    username: str
    comment: CommentInfo
    profile: UserProfile
    weighted_score: float


def _normalize(value: float, max_value: float) -> float:
    """Normalize a value to [0, 1]. Handles zero max gracefully."""
    if max_value <= 0:
        return 0.0
    return min(value / max_value, 1.0)


def rank_commenters(
    comments: list[CommentInfo],
    profiles: dict[str, UserProfile],
    top_n: int = 20,
    weights: dict[str, float] | None = None,
) -> list[RankedCommenter]:
    """Score and rank commenters. Returns top N by weighted score.

    Only considers commenters whose profiles were successfully fetched.
    """
    w = weights or RANKING_WEIGHTS

    # Build candidate list — skip anyone whose profile we couldn't fetch
    candidates: list[tuple[CommentInfo, UserProfile]] = []
    for comment in comments:
        profile = profiles.get(comment.author)
        if profile is not None:
            candidates.append((comment, profile))

    if not candidates:
        return []

    # Find maxes for normalization
    max_score = max(abs(c.score) for c, _ in candidates) or 1
    max_length = max(len(c.body) for c, _ in candidates) or 1
    max_age = max(p.account_age_days for _, p in candidates) or 1
    max_karma = max(abs(p.comment_karma) for _, p in candidates) or 1
    max_richness = max(
        len({a.subreddit for a in p.activities}) for _, p in candidates
    ) or 1

    ranked: list[RankedCommenter] = []
    for comment, profile in candidates:
        unique_subs = len({a.subreddit for a in profile.activities})
        weighted = (
            w.get("comment_score", 0) * _normalize(comment.score, max_score)
            + w.get("comment_length", 0) * _normalize(len(comment.body), max_length)
            + w.get("account_age", 0) * _normalize(profile.account_age_days, max_age)
            + w.get("comment_karma", 0) * _normalize(profile.comment_karma, max_karma)
            + w.get("activity_richness", 0) * _normalize(unique_subs, max_richness)
        )
        ranked.append(
            RankedCommenter(
                username=comment.author,
                comment=comment,
                profile=profile,
                weighted_score=weighted,
            )
        )

    ranked.sort(key=lambda r: r.weighted_score, reverse=True)

    # Deduplicate — keep highest-scoring comment per user
    seen: set[str] = set()
    deduped: list[RankedCommenter] = []
    for r in ranked:
        if r.username not in seen:
            seen.add(r.username)
            deduped.append(r)

    return deduped[:top_n]
