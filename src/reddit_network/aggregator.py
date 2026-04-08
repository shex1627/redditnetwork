"""Aggregate subreddit frequency map from user activity histories."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from reddit_network.config import MEGA_SUBREDDIT_BLOCKLIST
from reddit_network.reddit_client import UserProfile


@dataclass
class SubredditStat:
    name: str
    commenter_count: int  # how many of the top-N commenters are active here
    total_activity: int  # sum of posts + comments across all tracked users
    avg_score: float  # average score of activity in this subreddit


def aggregate_subreddits(
    profiles: list[UserProfile],
    source_subreddit: str,
    min_commenter_count: int = 2,
    extra_blocklist: set[str] | None = None,
) -> list[SubredditStat]:
    """Build a frequency table of subreddits from user activity.

    Filters out:
    - The source subreddit
    - Mega-subreddits (blocklist)
    - Subreddits with fewer than min_commenter_count unique users
    """
    blocklist = {s.lower() for s in MEGA_SUBREDDIT_BLOCKLIST}
    if extra_blocklist:
        blocklist |= {s.lower() for s in extra_blocklist}
    source_lower = source_subreddit.lower()

    # Track per-subreddit: which users, total items, total score
    # Use lowercase keys for grouping, but remember the display name
    sub_display_name: dict[str, str] = {}  # lowercase -> first-seen casing
    sub_users: dict[str, set[str]] = defaultdict(set)
    sub_activity: dict[str, int] = defaultdict(int)
    sub_total_score: dict[str, float] = defaultdict(float)

    for profile in profiles:
        seen_subs_for_user: set[str] = set()
        for activity in profile.activities:
            sub_lower = activity.subreddit.lower()
            if sub_lower in blocklist or sub_lower == source_lower:
                continue
            if sub_lower not in sub_display_name:
                sub_display_name[sub_lower] = activity.subreddit
            sub_users[sub_lower].add(profile.username)
            sub_activity[sub_lower] += 1
            sub_total_score[sub_lower] += activity.score
            seen_subs_for_user.add(sub_lower)

    results: list[SubredditStat] = []
    for sub_lower, users in sub_users.items():
        count = len(users)
        if count < min_commenter_count:
            continue
        activity_total = sub_activity[sub_lower]
        avg_score = sub_total_score[sub_lower] / activity_total if activity_total else 0
        results.append(
            SubredditStat(
                name=sub_display_name[sub_lower],
                commenter_count=count,
                total_activity=activity_total,
                avg_score=avg_score,
            )
        )

    # Sort by commenter overlap first, then total activity as tiebreaker
    results.sort(key=lambda s: (s.commenter_count, s.total_activity), reverse=True)
    return results
