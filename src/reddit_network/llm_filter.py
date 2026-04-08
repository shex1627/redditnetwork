"""LLM-based relevance filtering — one call to prune irrelevant subreddits."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

from reddit_network.aggregator import SubredditStat
from reddit_network.config import ANTHROPIC_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)


@dataclass
class FilteredSubreddit:
    name: str
    commenter_count: int
    total_activity: int
    relevance_score: int  # 0-10
    reason: str


FILTER_PROMPT = """\
You are a subreddit relevance classifier.

Given a Reddit post titled "{post_title}" from r/{source_subreddit}, \
here are subreddits frequently visited by the top commenters on that post.

For each subreddit, decide if it is related to the topic of the original post.
Return a JSON array of objects with exactly these fields:
- "name": the subreddit name without the "r/" prefix (exactly as given in the list)
- "relevance": an integer 0-10 (10 = highly relevant, 0 = unrelated)
- "reason": a short one-line explanation

Only include subreddits with relevance >= {min_relevance}. \
Remove anything clearly unrelated (personal hobbies, geographic subs, \
general entertainment, meme subs).

Subreddits to evaluate:
{subreddit_list}

Respond with ONLY the JSON array, no other text."""


def filter_subreddits(
    subreddits: list[SubredditStat],
    post_title: str,
    source_subreddit: str,
    min_relevance: int = 5,
) -> tuple[list[FilteredSubreddit], bool]:
    """Filter subreddits by LLM-assessed relevance.

    Returns (filtered_list, llm_succeeded).
    If the LLM call fails, returns all subreddits unscored with llm_succeeded=False.
    """
    if not subreddits:
        return [], True

    if not ANTHROPIC_API_KEY:
        logger.warning("No ANTHROPIC_API_KEY set — skipping LLM filter")
        return _fallback(subreddits), False

    sub_list = "\n".join(
        f"- r/{s.name} (active commenters: {s.commenter_count}, "
        f"total activity: {s.total_activity})"
        for s in subreddits
    )

    prompt = FILTER_PROMPT.format(
        post_title=post_title,
        source_subreddit=source_subreddit,
        min_relevance=min_relevance,
        subreddit_list=sub_list,
    )

    logger.info("Sending %d subreddits to LLM for relevance filtering", len(subreddits))
    logger.debug("LLM prompt:\n%s", prompt)

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        logger.debug("LLM raw response:\n%s", raw)
        return _parse_response(raw, subreddits, min_relevance), True

    except (anthropic.APIError, anthropic.APIConnectionError) as exc:
        logger.warning("LLM filter failed: %s — returning unfiltered results", exc)
        return _fallback(subreddits), False

    except Exception as exc:
        logger.warning("Unexpected LLM error: %s — returning unfiltered results", exc)
        return _fallback(subreddits), False


def _parse_response(
    raw: str,
    original: list[SubredditStat],
    min_relevance: int,
) -> list[FilteredSubreddit]:
    """Parse the LLM JSON response. Falls back to unfiltered on parse error."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse LLM response as JSON, returning unfiltered")
        return _fallback(original)

    if not isinstance(data, list):
        logger.warning("LLM response is not a list, returning unfiltered")
        return _fallback(original)

    # Build lookup for original stats
    stat_map = {s.name.lower(): s for s in original}

    results: list[FilteredSubreddit] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        relevance = item.get("relevance", 0)
        reason = item.get("reason", "")

        if not isinstance(relevance, int):
            try:
                relevance = int(relevance)
            except (ValueError, TypeError):
                relevance = 0

        if relevance < min_relevance:
            continue

        # Match back to original stats — strip "r/" prefix if LLM included it
        clean_name = name.removeprefix("r/").removeprefix("R/")
        orig = stat_map.get(clean_name.lower())
        results.append(
            FilteredSubreddit(
                name=clean_name,
                commenter_count=orig.commenter_count if orig else 0,
                total_activity=orig.total_activity if orig else 0,
                relevance_score=relevance,
                reason=reason,
            )
        )

    results.sort(key=lambda s: (s.relevance_score, s.commenter_count), reverse=True)
    return results


def _fallback(subreddits: list[SubredditStat]) -> list[FilteredSubreddit]:
    """Return all subreddits without LLM scoring."""
    return [
        FilteredSubreddit(
            name=s.name,
            commenter_count=s.commenter_count,
            total_activity=s.total_activity,
            relevance_score=-1,  # indicates unscored
            reason="LLM filter unavailable",
        )
        for s in subreddits
    ]
