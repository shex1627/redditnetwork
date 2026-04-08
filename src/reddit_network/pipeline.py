"""Orchestrates the full discovery pipeline — shared by CLI and Streamlit."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from reddit_network.aggregator import SubredditStat, aggregate_subreddits
from reddit_network.config import (
    DEFAULT_MIN_RELEVANCE,
    DEFAULT_TOP_N_COMMENTERS,
    parse_post_url,
)
from reddit_network.llm_filter import FilteredSubreddit, filter_subreddits
from reddit_network.ranker import RankedCommenter, rank_commenters
from reddit_network.reddit_client import (
    PostInfo,
    UserProfile,
    fetch_post,
    fetch_top_comments,
    fetch_user_profile,
    get_reddit_client,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float], None]


@dataclass
class DiscoveryResult:
    post: PostInfo
    commenters: list[RankedCommenter]
    raw_subreddits: list[SubredditStat]
    subreddits: list[FilteredSubreddit]
    llm_filtered: bool
    commenters_analyzed: int
    commenters_skipped: int
    warnings: list[str] = field(default_factory=list)


def discover_subreddits(
    post_url: str,
    top_n_commenters: int = DEFAULT_TOP_N_COMMENTERS,
    min_relevance: int = DEFAULT_MIN_RELEVANCE,
    on_progress: ProgressCallback | None = None,
) -> DiscoveryResult:
    """Run the full 5-step discovery pipeline."""

    def progress(msg: str, frac: float) -> None:
        if on_progress:
            on_progress(msg, frac)

    pipeline_start = time.monotonic()

    # --- Step 0: Parse URL ---
    post_id = parse_post_url(post_url)
    logger.info("Parsed post_id=%s from URL: %s", post_id, post_url)
    reddit = get_reddit_client()

    # --- Step 1: Fetch post & comments ---
    progress("Fetching post...", 0.0)
    t0 = time.monotonic()
    post = fetch_post(reddit, post_id)
    logger.info(
        "Fetched post: r/%s — \"%s\" (%d upvotes, %d comments) [%.1fs]",
        post.subreddit, post.title, post.score, post.num_comments,
        time.monotonic() - t0,
    )

    progress("Fetching comments...", 0.10)
    t0 = time.monotonic()
    comments = fetch_top_comments(reddit, post_id)
    logger.info("Fetched %d top-level comments [%.1fs]", len(comments), time.monotonic() - t0)
    if not comments:
        return DiscoveryResult(
            post=post,
            commenters=[],
            raw_subreddits=[],
            subreddits=[],
            llm_filtered=False,
            commenters_analyzed=0,
            commenters_skipped=0,
            warnings=["Post has no comments."],
        )

    # --- Step 2: Fetch user profiles ---
    progress("Fetching user profiles...", 0.20)
    unique_authors = list(dict.fromkeys(c.author for c in comments))
    authors_to_fetch = unique_authors[: top_n_commenters * 2]
    logger.info("Fetching profiles for %d unique authors", len(authors_to_fetch))

    profiles: dict[str, UserProfile] = {}
    skipped = 0
    t0 = time.monotonic()
    for i, author in enumerate(authors_to_fetch):
        frac = 0.20 + 0.40 * (i / len(authors_to_fetch))
        progress(f"Fetching profile {i + 1}/{len(authors_to_fetch)}: u/{author}", frac)

        profile = fetch_user_profile(reddit, author)
        if profile is not None:
            profiles[author] = profile
        else:
            skipped += 1

    logger.info(
        "Profiles fetched: %d ok, %d skipped [%.1fs]",
        len(profiles), skipped, time.monotonic() - t0,
    )

    # --- Step 3: Rank commenters ---
    progress("Ranking commenters...", 0.60)
    ranked = rank_commenters(comments, profiles, top_n=top_n_commenters)
    logger.info("Ranked top %d commenters from %d candidates", len(ranked), len(profiles))

    if not ranked:
        return DiscoveryResult(
            post=post,
            commenters=[],
            raw_subreddits=[],
            subreddits=[],
            llm_filtered=False,
            commenters_analyzed=0,
            commenters_skipped=skipped,
            warnings=["Could not access any user profiles."],
        )

    # --- Step 4: Aggregate subreddits ---
    progress("Aggregating subreddit map...", 0.70)
    ranked_profiles = [r.profile for r in ranked]
    raw_subreddits = aggregate_subreddits(
        profiles=ranked_profiles,
        source_subreddit=post.subreddit,
    )
    logger.info("Aggregated %d unique subreddits (after blocklist + dedup)", len(raw_subreddits))

    # --- Step 5: LLM relevance filter ---
    progress("Filtering by relevance (LLM)...", 0.80)
    t0 = time.monotonic()
    filtered, llm_ok = filter_subreddits(
        subreddits=raw_subreddits,
        post_title=post.title,
        source_subreddit=post.subreddit,
        min_relevance=min_relevance,
    )
    logger.info(
        "LLM filter: %d → %d subreddits (ok=%s) [%.1fs]",
        len(raw_subreddits), len(filtered), llm_ok, time.monotonic() - t0,
    )

    warnings: list[str] = []
    if not llm_ok:
        warnings.append("LLM filtering unavailable — showing unfiltered results.")
    if skipped > 0:
        warnings.append(f"Skipped {skipped} users (private/suspended profiles).")

    elapsed = time.monotonic() - pipeline_start
    logger.info("Pipeline complete in %.1fs", elapsed)
    progress("Done!", 1.0)

    return DiscoveryResult(
        post=post,
        commenters=ranked,
        raw_subreddits=raw_subreddits,
        subreddits=filtered,
        llm_filtered=llm_ok,
        commenters_analyzed=len(ranked),
        commenters_skipped=skipped,
        warnings=warnings,
    )
