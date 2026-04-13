"""FastAPI server — thin HTTP wrapper around the discovery pipeline."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from reddit_network.config import DEFAULT_MIN_RELEVANCE, DEFAULT_TOP_N_COMMENTERS
from reddit_network.pipeline import discover_subreddits

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)
app = FastAPI(title="Reddit Network Discovery", version="0.1.0", docs_url=None, redoc_url=None)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class DiscoverRequest(BaseModel):
    post_url: str = Field(max_length=500)
    top_n_commenters: int = Field(default=DEFAULT_TOP_N_COMMENTERS, ge=1, le=50)
    min_relevance: int = Field(default=DEFAULT_MIN_RELEVANCE, ge=0, le=10)


class PostOut(BaseModel):
    post_id: str
    title: str
    subreddit: str
    score: int
    num_comments: int
    url: str
    author: str | None = None


class SubredditOut(BaseModel):
    name: str
    commenter_count: int
    total_activity: int
    relevance_score: int
    reason: str


class RawSubredditOut(BaseModel):
    name: str
    commenter_count: int
    total_activity: int
    avg_score: float


class CommenterOut(BaseModel):
    username: str
    comment_score: int
    weighted_score: float
    comment_karma: int
    account_age_days: int
    active_subreddits: list[str]


class DiscoverResponse(BaseModel):
    post: PostOut
    filtered_subreddits: list[SubredditOut]
    raw_subreddits: list[RawSubredditOut]
    top_commenters: list[CommenterOut]
    commenters_analyzed: int
    commenters_skipped: int
    llm_filtered: bool
    warnings: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/discover", response_model=DiscoverResponse)
def discover(req: DiscoverRequest) -> DiscoverResponse:
    """Run the discovery pipeline and return structured results."""
    logger.info("POST /discover — url=%s top_n=%d min_rel=%d", req.post_url, req.top_n_commenters, req.min_relevance)
    try:
        result = discover_subreddits(
            post_url=req.post_url,
            top_n_commenters=req.top_n_commenters,
            min_relevance=req.min_relevance,
        )
    except ValueError as exc:
        logger.warning("Bad request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail="Internal server error")

    return DiscoverResponse(
        post=PostOut(
            post_id=result.post.post_id,
            title=result.post.title,
            subreddit=result.post.subreddit,
            score=result.post.score,
            num_comments=result.post.num_comments,
            url=result.post.url,
            author=result.post.author,
        ),
        filtered_subreddits=[
            SubredditOut(
                name=s.name,
                commenter_count=s.commenter_count,
                total_activity=s.total_activity,
                relevance_score=s.relevance_score,
                reason=s.reason,
            )
            for s in result.subreddits
        ],
        raw_subreddits=[
            RawSubredditOut(
                name=s.name,
                commenter_count=s.commenter_count,
                total_activity=s.total_activity,
                avg_score=round(s.avg_score, 2),
            )
            for s in result.raw_subreddits
        ],
        top_commenters=[
            CommenterOut(
                username=r.username,
                comment_score=r.comment.score,
                weighted_score=round(r.weighted_score, 4),
                comment_karma=r.profile.comment_karma,
                account_age_days=round(r.profile.account_age_days),
                active_subreddits=sorted(
                    {a.subreddit for a in r.profile.activities}
                ),
            )
            for r in result.commenters
        ],
        commenters_analyzed=result.commenters_analyzed,
        commenters_skipped=result.commenters_skipped,
        llm_filtered=result.llm_filtered,
        warnings=result.warnings,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
