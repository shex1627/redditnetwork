"""Configuration, constants, and environment loading."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Reddit API
# ---------------------------------------------------------------------------

REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = "reddit-network-discovery:v0.1"

# ---------------------------------------------------------------------------
# Anthropic API
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Pipeline defaults
# ---------------------------------------------------------------------------

DEFAULT_TOP_N_COMMENTERS = 20
DEFAULT_MIN_RELEVANCE = 5
DEFAULT_COMMENT_FETCH_LIMIT = 200
DEFAULT_USER_HISTORY_LIMIT = 100
PIPELINE_TIMEOUT_SECONDS = 120

# ---------------------------------------------------------------------------
# Commenter ranking weights
# ---------------------------------------------------------------------------

RANKING_WEIGHTS = {
    "comment_score": 0.50,
    "comment_length": 0.20,
    "account_age": 0.15,
    "comment_karma": 0.15,
}

# ---------------------------------------------------------------------------
# Mega-subreddit blocklist — these appear in almost every user's history
# and carry zero signal for community discovery.
# ---------------------------------------------------------------------------

MEGA_SUBREDDIT_BLOCKLIST: set[str] = {
    "announcements",
    "art",
    "askreddit",
    "askscience",
    "aww",
    "blog",
    "books",
    "creepy",
    "dataisbeautiful",
    "diy",
    "documentaries",
    "earthporn",
    "explainlikeimfive",
    "food",
    "funny",
    "futurology",
    "gadgets",
    "gaming",
    "getmotivated",
    "gifs",
    "history",
    "iama",
    "internetisbeautiful",
    "jokes",
    "lifeprotips",
    "listentothis",
    "memes",
    "mildlyinteresting",
    "movies",
    "music",
    "news",
    "nosleep",
    "nottheonion",
    "oldschoolcool",
    "personalfinance",
    "philosophy",
    "photoshopbattles",
    "pics",
    "science",
    "showerthoughts",
    "space",
    "sports",
    "television",
    "tifu",
    "todayilearned",
    "twoxchromosomes",
    "upliftingnews",
    "videos",
    "worldnews",
}

# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

# Matches reddit.com/r/{sub}/comments/{post_id}/...
_REDDIT_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:(?:www|old|new)\.)?reddit\.com"
    r"/r/(?P<subreddit>[^/]+)/comments/(?P<post_id>[a-z0-9]+)",
    re.IGNORECASE,
)

# Short link: redd.it/{post_id}
_REDDIT_SHORT_PATTERN = re.compile(
    r"(?:https?://)?redd\.it/(?P<post_id>[a-z0-9]+)",
    re.IGNORECASE,
)


def parse_post_url(url: str) -> str:
    """Extract a Reddit post ID from various URL formats.

    Returns the post ID string, or raises ValueError.
    """
    m = _REDDIT_URL_PATTERN.search(url)
    if m:
        return m.group("post_id")

    m = _REDDIT_SHORT_PATTERN.search(url)
    if m:
        return m.group("post_id")

    raise ValueError(
        f"Could not parse Reddit post URL: {url!r}. "
        "Expected format: https://reddit.com/r/SUB/comments/POST_ID/..."
    )
