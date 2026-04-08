# Technical Design: Reddit Network Discovery -- v0.1 Prototype

## Overview

A Python app (CLI + Streamlit UI) that takes a Reddit post URL and outputs a relevance-filtered map of related subreddits, discovered by analyzing where the top commenters in that post are active.

```
INPUT:  https://reddit.com/r/datascience/comments/abc123/...
OUTPUT: Filtered list of related subreddits, ranked by commenter overlap
```

---

## Core Pipeline

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Post URL   │────>│  Fetch Comments   │────>│  Rank Commenters    │
│  (user)     │     │  (Reddit API)     │     │  (static criteria)  │
└─────────────┘     └──────────────────┘     └────────┬────────────┘
                                                       │
                                                       v
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Filtered   │<────│  LLM Relevance   │<────│  Fetch User         │
│  Subreddit  │     │  Filter (1 call) │     │  Histories          │
│  Map        │     └──────────────────┘     │  (Reddit API)       │
└─────────────┘                              └─────────────────────┘
```

### Step 1: Fetch Post Comments

```
GET /comments/{post_id}?sort=top&limit=200&depth=1
```

- Sort by `top` (Reddit's default ranking by upvotes)
- `depth=1` -- only top-level comments (replies are less relevant for finding domain experts)
- `limit=200` -- enough to find signal, not so many we waste API calls
- **Cost:** 1 API call

### Step 2: Rank Commenters

Static criteria for v0.1 (no LLM needed here):

| Criterion | Weight | Rationale |
|-----------|--------|-----------|
| Comment score (upvotes - downvotes) | 0.5 | Community-validated quality |
| Comment length (chars) | 0.2 | Longer comments tend to be more substantive |
| Account age | 0.15 | Older accounts are less likely to be bots/throwaways |
| Comment karma (profile) | 0.15 | Track record of quality contributions |

Produce a ranked list. Take **top N** (configurable, default 20).

**Future:** LLM-based scoring as an optional mode ("how technical does this sound?"). But not for v0.1 -- validate the pipeline first.

### Step 3: Fetch User Histories

For each of the top N commenters:

```
GET /user/{username}/overview?limit=100&sort=top
```

- Uses the `overview` endpoint which returns comments AND submissions interleaved in one call
- 1 API call per user instead of 2 -- cuts Reddit API usage in half
- Extract the `subreddit` field from each item
- **Cost:** 1 API call per user = 20 calls for 20 users
- **Rate limit math:** 100 req/min limit. 20 calls = ~12 seconds minimum. Parallelize with rate limiter.

**Tradeoff:** 100 mixed items vs 100 comments + 100 submissions separately. For most users, 100 items is enough signal for subreddit discovery. If a user needs deeper history, we can fall back to separate endpoints later.

**API hard limit:** Reddit caps history at ~1000 items. 100 per request is well within this. For users with very long histories, we get their *top* content, which is actually better for our purpose (their best contributions indicate their real interests).

### Step 4: Aggregate Subreddit Map

Build a frequency table:

```python
{
    "r/machinelearning": {"commenter_count": 12, "total_activity": 87},
    "r/Python": {"commenter_count": 9, "total_activity": 43},
    "r/hiking": {"commenter_count": 2, "total_activity": 3},
    ...
}
```

- `commenter_count` = how many of the top N commenters are active there
- `total_activity` = sum of posts + comments across all tracked users

Filter out:
- The source subreddit itself (you already know about it)
- Default/mega subreddits (r/AskReddit, r/funny, r/pics, etc.) -- hardcoded blocklist
- Subreddits with only 1 commenter active (weak signal)

### Step 5: LLM Relevance Filter

**One API call.** Send the aggregated list + the original post context to an LLM:

```
Prompt:
Given this Reddit post about "{post_title}" from r/{subreddit},
here are subreddits frequently visited by the top commenters:

{subreddit_list_with_counts}

Which of these subreddits are likely related to the topic of 
the original post? For each, give a relevance score (0-10) 
and a one-line reason.

Remove anything clearly unrelated (hobbies, geographic subs, 
general entertainment).
```

**Model choice:** Claude Haiku or GPT-4o-mini. This is a classification/filtering task, not a generation task. Cheapest model that can handle ~100 subreddit names.

**Cost:** ~$0.001-0.005 per query (list of 50-100 subreddit names is ~500 tokens input, ~1000 tokens output).

### Output

```
Reddit Network Discovery for:
"Best practices for feature engineering in production ML systems"
(r/datascience, 847 upvotes, 234 comments)

Analyzed top 20 commenters. Found 67 unique subreddits.
After relevance filtering:

 #  Subreddit                Commenters  Relevance  Why
 1  r/MachineLearning        14/20       10/10      Core ML research & practice
 2  r/dataengineering         9/20        9/10      Feature pipelines, infra
 3  r/learnmachinelearning    7/20        8/10      ML education & fundamentals
 4  r/Python                  8/20        7/10      Primary implementation language
 5  r/MLOps                   5/20        9/10      Production ML systems
 6  r/statistics               6/20        7/10      Statistical foundations
 7  r/cscareerquestions        4/20        5/10      Career context for DS
 ...
```

---

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | PRAW ecosystem, fast prototyping |
| Reddit API | PRAW 7.8.x | Handles OAuth2, rate limiting, pagination |
| LLM | Anthropic API (Claude Haiku) | Cheap, fast, good at classification |
| CLI framework | `click` | Simple CLI entrypoint |
| Web UI | Streamlit | Fastest path to interactive UI in Python, zero frontend code |
| Config | `.env` file | Reddit OAuth creds + Anthropic API key |
| Output | Terminal (rich/tabulate) + Streamlit tables/charts | Both interfaces share the same pipeline |

No database for v0.1. No caching. Add those when there's a reason to.

---

## Project Structure

```
reddit_network/
├── README.md
├── pyproject.toml
├── .env.example              # Reddit + LLM API keys
├── docs/
│   └── design/
│       ├── evaluation.md
│       └── technical_design.md
└── src/
    └── reddit_network/
        ├── __init__.py
        ├── cli.py            # CLI entrypoint (click)
        ├── app.py            # Streamlit UI
        ├── pipeline.py       # Orchestrates the full discovery pipeline (shared by CLI + UI)
        ├── reddit_client.py  # PRAW wrapper: fetch post, comments, user history
        ├── ranker.py         # Score and rank commenters
        ├── aggregator.py     # Build subreddit frequency map
        ├── llm_filter.py     # Single LLM call for relevance filtering
        └── config.py         # Load .env, constants (blocklist, defaults)
```

### Why `pipeline.py`?

Both `cli.py` and `app.py` need to run the same 5-step pipeline. Rather than duplicating logic, `pipeline.py` exposes a single function:

```python
def discover_subreddits(
    post_url: str,
    top_n_commenters: int = 20,
    min_relevance: int = 5,
) -> DiscoveryResult:
    """Run the full pipeline. Returns structured result."""
```

CLI and Streamlit both call this. The only difference is how they display the result.

---

## Reddit API Auth Setup

```python
# config.py
import praw

def get_reddit_client():
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent="reddit-network-discovery:v0.1 (by /u/{your_username})",
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
    )
```

Registration: https://www.reddit.com/prefs/apps → "script" type app.

---

## API Budget Per Query

| Step | API Calls | Target |
|------|-----------|--------|
| Fetch post comments | 1 | Reddit |
| Fetch commenter profiles (karma, age) | 20 | Reddit |
| Fetch user overviews (comments + posts) | 20 | Reddit |
| LLM relevance filter | 1 | Anthropic |
| **Total** | **42** | |

At 100 req/min Reddit rate limit: **~25 seconds per query** (with headroom).

LLM cost: **~$0.003 per query**.

Total cost per query: effectively free (Reddit API is free for non-commercial), plus fractions of a cent for LLM.

---

## Key Design Decisions

### Why top-level comments only (depth=1)?

Reply threads are conversations, not expertise signals. Someone writing a top-level answer to "best practices for feature engineering" is more likely a practitioner than someone replying "lol same" three levels deep.

### Why static ranking before LLM?

The LLM is expensive relative to counting upvotes. Use the cheap signal (upvotes, length, karma) to select the top 20, THEN invest the expensive signal (LLM) only on the final relevance filter. Don't burn LLM calls on ranking 200 commenters when Reddit's own voting already did 90% of the work.

### Why a blocklist for mega-subreddits?

r/AskReddit has 40M+ members. Every user is "active" there. It tells you nothing. Same for r/funny, r/pics, r/gaming, etc. A static blocklist of the top ~50 default subs eliminates the biggest noise source without needing LLM.

### Why no caching in v0.1?

Premature. We don't know usage patterns yet. If you're running 2 queries a day while dogfooding, caching adds complexity for zero benefit. Add it when you're running 100+/day or when the same users keep appearing across queries.

### Why no database?

Same reasoning. A database is for when you need persistence, querying, or sharing state. v0.1 is a CLI tool that runs, prints results, and exits. If we add "follow users over time" (v0.2+), that's when a DB makes sense.

---

## Streamlit UI (`app.py`)

### Layout

```
┌──────────────────────────────────────────────────────────┐
│  Reddit Network Discovery                                │
│                                                          │
│  [Post URL input________________________] [Discover]     │
│                                                          │
│  Settings (sidebar):                                     │
│  ├── Top N commenters: [slider 5-50, default 20]         │
│  ├── Min relevance score: [slider 1-10, default 5]       │
│  └── Show raw data: [checkbox]                           │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  📋 Post Info                                            │
│  Title, subreddit, score, comment count                  │
│                                                          │
│  ⏳ Progress                                             │
│  [Step 1/5: Fetching comments... ████████░░ ]            │
│                                                          │
│  📊 Results                                              │
│  ┌──────────────────────────────────────────────────┐    │
│  │ Sortable table: subreddit, commenter overlap,    │    │
│  │ relevance score, reason                          │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  📈 Bar chart: top 15 subreddits by commenter overlap    │
│                                                          │
│  👥 Top Commenters (expandable)                          │
│  ├── username1 (score: 847) — active in 12 subreddits   │
│  ├── username2 (score: 523) — active in 8 subreddits    │
│  └── ...                                                 │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Key UI Decisions

**Progress feedback is essential.** The pipeline takes ~25 seconds. Without feedback, users think it's broken. Streamlit's `st.status` and `st.progress` update in real-time as each step completes.

**Pipeline callbacks for progress.** `pipeline.py` accepts an optional callback so the UI can update progress without coupling the pipeline to Streamlit:

```python
def discover_subreddits(
    post_url: str,
    top_n_commenters: int = 20,
    min_relevance: int = 5,
    on_progress: Callable[[str, float], None] | None = None,
) -> DiscoveryResult:
    """
    on_progress receives (step_description, fraction_complete)
    e.g., ("Fetching user histories...", 0.6)
    """
```

**Clickable subreddit links.** Each subreddit in the results table links to `reddit.com/r/{name}` so users can immediately explore.

**Expandable commenter details.** Use `st.expander` per commenter -- shows their top subreddits and a link to their profile. Keeps the main view clean.

### Running

```bash
# CLI
python -m reddit_network.cli "https://reddit.com/r/datascience/comments/..."

# Streamlit
streamlit run src/reddit_network/app.py
```

---

## Future Extensions (Not v0.1)

| Feature | When | Why Wait |
|---------|------|----------|
| **LLM comment scoring** | v0.2 | Validate pipeline first, then add quality signals |
| **User following / tracking** | v0.2 | Requires persistence (DB), scheduled jobs |
| **Caching layer** | v0.2 | Add when usage patterns are clear |
| **Subreddit deep-dive** | v0.2 | Given a discovered subreddit, run the same analysis recursively |
| **Cross-platform (HN, SO)** | v0.3+ | Different APIs, same pipeline pattern |
| **Graph visualization** | v0.3+ | Network graph of subreddit relationships |

---

## Architecture Review

Applied against principles from DDIA [01], Philosophy of Software Design [06], Clean Architecture [04], Release It [17], and Fundamentals of Software Architecture [02].

### Strengths

- **Pipeline is a clean linear chain** -- each step has a single input and output, no branching or feedback loops. This is the simplest architecture that could work [02: Fundamentals]. Easy to reason about, test in isolation, and extend.
- **Shared pipeline with callback** -- `pipeline.py` as the single orchestration point with `on_progress` callback avoids duplicating logic across CLI/Streamlit while keeping the pipeline UI-agnostic. Dependencies point inward toward domain logic [04: Clean Architecture].
- **LLM as a filter, not a core dependency** -- the pipeline produces useful (if noisier) results even if the LLM call fails. The LLM refines; it doesn't generate. This is good degradation design [17: Release It].
- **No premature infrastructure** -- no DB, no cache, no queue. Correct for a prototype. Complexity must justify itself [06: Philosophy of SW Design].

### Concerns

**1. No failure isolation between user history fetches (Severity: High)**

If user #7 of 20 has a private profile or is suspended, what happens? PRAW will throw an exception. If uncaught, it kills the whole pipeline -- you lose the results from users 1-6 and never fetch 8-20.

> "What happens if this component fails?" is the first question. [17: Release It]

**Fix:** `reddit_client.py` should catch per-user errors and return a partial result. The pipeline continues with however many users succeeded. Report skip count to the user.

**2. Rate limiter is implicit (Severity: Medium)**

PRAW handles rate limiting internally, but the design doesn't account for what happens when you're sharing the rate limit budget across 20+ sequential calls. If PRAW sleeps to respect limits, the total wall time could exceed user expectations (especially in Streamlit where they're watching a progress bar).

**Fix:** Make the rate limiter explicit. Track remaining budget via PRAW's `reddit.auth.limits` dict, and update the progress callback with realistic ETAs.

**3. LLM response parsing is a fragile point (Severity: Medium)**

The LLM returns free-form text with scores and reasons. If the format drifts (extra newline, missing score, hallucinated subreddit name), parsing breaks silently or noisily.

> Every architecture choice is a tradeoff -- name both sides. [01: DDIA]

**Fix:** Use structured output (JSON mode) in the LLM call. Define a simple schema: `[{"subreddit": str, "relevance": int, "reason": str}]`. Validate the response against the schema before passing downstream. Fall back to unfiltered results if parsing fails.

**4. No timeout on the full pipeline (Severity: Low-Medium)**

42 API calls + 1 LLM call. If Reddit is slow or the LLM hangs, the user waits indefinitely. Streamlit has no built-in request timeout.

**Fix:** Add a configurable timeout to `discover_subreddits()` (default 120s). Use `concurrent.futures` with timeout for the Reddit fetch phase.

### Recommendations Summary

| Issue | Fix | Effort |
|-------|-----|--------|
| Per-user failure isolation | try/except per user in fetch loop, continue on error | Small |
| Explicit rate limit tracking | Surface PRAW's rate limit state in progress callback | Small |
| Structured LLM output | JSON mode + schema validation + fallback | Medium |
| Pipeline timeout | Wrap in concurrent.futures with configurable timeout | Small |

---

## Testing Strategy

Applied against principles from Unit Testing [12: Khorikov], GOOS [13: Freeman & Pryce], Pragmatic Programmer [14], and Anthropic's eval articles.

### Testing Pyramid

```
        ╱ ╲           Value Validation (manual + semi-automated)
       ╱   ╲          "Are the results actually useful?"
      ╱─────╲
     ╱       ╲        Integration Tests (live API, few)
    ╱         ╲       "Does the pipeline work end-to-end?"
   ╱───────────╲
  ╱             ╲     Unit Tests (mocked boundaries, many)
 ╱               ╲    "Does each step compute correctly?"
╱─────────────────╲
```

### Layer 1: Unit Tests (Pure Logic, No API Calls)

> Test observable behavior, not implementation details. [12: Unit Testing]

These test the **computation** steps where our logic lives. Mock the external boundaries (Reddit API, Anthropic API) but test real logic.

| Module | What to Test | Example |
|--------|-------------|---------|
| `ranker.py` | Scoring formula produces correct ordering | Commenter with 500 upvotes + long comment ranks above 50 upvotes + short comment |
| `ranker.py` | Edge cases: deleted users, zero karma, brand-new accounts | Account age = 0 doesn't cause division by zero |
| `ranker.py` | Weight configuration changes ranking | Doubling upvote weight changes top-N selection |
| `aggregator.py` | Frequency table built correctly from user histories | 3 users active in r/Python → commenter_count = 3 |
| `aggregator.py` | Blocklist filtering removes mega-subreddits | r/AskReddit never appears in output |
| `aggregator.py` | Source subreddit is excluded | If post is from r/datascience, it's filtered out |
| `aggregator.py` | Single-commenter subreddits are dropped | r/obscurehobby with 1 commenter doesn't appear |
| `llm_filter.py` | Response parsing extracts structured data | Valid JSON → list of scored subreddits |
| `llm_filter.py` | Malformed LLM response → graceful fallback | Returns unfiltered list with warning, not crash |
| `config.py` | URL parsing extracts post ID correctly | Various Reddit URL formats (old.reddit, www, short links) |

**Test fixtures:** Create 3-4 realistic snapshots of Reddit API responses (saved as JSON). Use these as canonical inputs so tests are deterministic.

```python
# Example: test_ranker.py
def test_ranking_order():
    comments = [
        make_comment(score=500, length=1200, author_karma=50000, account_age_days=2000),
        make_comment(score=50, length=100, author_karma=500, account_age_days=30),
        make_comment(score=200, length=800, author_karma=10000, account_age_days=500),
    ]
    ranked = rank_commenters(comments, top_n=2)
    assert ranked[0].score == 500  # highest weighted score
    assert len(ranked) == 2        # respects top_n

def test_zero_karma_does_not_crash():
    comments = [make_comment(score=10, length=50, author_karma=0, account_age_days=0)]
    ranked = rank_commenters(comments, top_n=1)
    assert len(ranked) == 1
```

### Layer 2: Integration Tests (Live API, Guarded)

> Mock only unmanaged out-of-process dependencies when unit testing. Use real instances for integration tests. [12: Unit Testing]

These hit the real Reddit API and real LLM. Run them manually or in CI with a `@pytest.mark.integration` marker (skipped by default).

| Test | What It Validates | Pass Criteria |
|------|-------------------|---------------|
| **Smoke test: known post** | Full pipeline on a real, stable Reddit post (pick one with 100+ comments that won't be deleted) | Returns ≥5 subreddits, completes in <120s |
| **Private user handling** | Pipeline with a mix of public and private/suspended users | Doesn't crash, reports skip count, still returns results |
| **Empty post** | Post with 0 comments | Returns empty result with clear message, no crash |
| **Deleted post** | URL points to a removed post | Returns clear error, not a stack trace |
| **Rate limit behavior** | Run 3 queries in quick succession | All complete without 429 errors (PRAW should handle this) |
| **LLM timeout** | Simulate slow LLM response | Pipeline returns unfiltered results after timeout, with warning |

**Pinned test post:** Pick one well-known, highly-upvoted post (e.g., a popular r/datascience thread) and hardcode its URL as the canonical integration test input. Check periodically that it still exists.

```python
# Example: test_integration.py
KNOWN_POST = "https://www.reddit.com/r/datascience/comments/XXXXX/..."

@pytest.mark.integration
def test_full_pipeline_smoke():
    result = discover_subreddits(KNOWN_POST, top_n_commenters=10)
    assert result.post_title is not None
    assert len(result.subreddits) >= 3
    assert all(s.relevance_score >= 1 for s in result.subreddits)
    assert result.commenters_analyzed >= 5
    assert result.commenters_skipped >= 0
```

### Layer 3: Stability Tests (Failure Modes)

> "What happens if this component fails?" [17: Release It]

These test that the system **degrades gracefully**, not that it works perfectly.

| Scenario | How to Simulate | Expected Behavior |
|----------|----------------|-------------------|
| Reddit API down | Mock PRAW to raise `prawcore.ServerError` | Pipeline raises clear error: "Reddit API unavailable" |
| Reddit API slow | Mock PRAW with `time.sleep(30)` per call | Pipeline times out after configurable limit, returns partial or error |
| LLM API down | Mock Anthropic client to raise `APIConnectionError` | Pipeline returns **unfiltered** subreddit map with warning: "LLM filtering unavailable, showing raw results" |
| LLM returns garbage | Mock Anthropic to return unparseable text | Falls back to unfiltered results, logs warning |
| All top commenters are private | Mock all user fetches to raise `Forbidden` | Returns empty result with message: "Could not access any user profiles" |
| Post has 1 comment | Use real post with minimal engagement | Returns result with 1 commenter, fewer subreddits |
| Malformed URL | Pass "not_a_url" or YouTube link | Clear validation error before any API calls |

```python
# Example: test_stability.py
def test_llm_failure_returns_unfiltered(mock_anthropic_down):
    result = discover_subreddits(KNOWN_POST, top_n_commenters=5)
    assert result.llm_filtered is False
    assert len(result.subreddits) > 0  # still has raw results
    assert "LLM filtering unavailable" in result.warnings
```

### Layer 4: Value Validation (Does It Actually Work?)

This is the most important layer and the hardest to automate. It answers: **"Are the discovered subreddits actually useful?"**

> Evals are the foundation of any AI system. Ship them before shipping the feature. [Anthropic: Demystifying Evals]

#### Manual Value Test (Do First)

Run the pipeline on 5 posts you know well. For each:

| Post | Domain | Expected Subreddits (you know these exist) | Surprising Finds? | Noise? |
|------|--------|---------------------------------------------|-------------------|--------|
| r/datascience post about feature eng | ML/DS | r/MachineLearning, r/dataengineering, r/MLOps | ? | ? |
| r/Python post about async | Python | r/learnpython, r/django, r/FastAPI | ? | ? |
| r/investing post about ETFs | Finance | r/Bogleheads, r/financialindependence | ? | ? |
| ... | ... | ... | ... | ... |

**Pass criteria:**
- ≥3 results you'd call "obviously relevant"
- ≥1 result you didn't know about but find genuinely interesting ("the discovery moment")
- ≤2 results that are clearly noise after LLM filtering

#### Semi-Automated Value Eval

For ongoing regression, build a small eval set:

```python
# eval/golden_set.py
EVAL_CASES = [
    {
        "post_url": "https://reddit.com/r/datascience/comments/XXXXX/...",
        "must_include": ["r/MachineLearning", "r/dataengineering"],
        "must_exclude": ["r/funny", "r/AskReddit", "r/gaming"],
        "min_results": 5,
    },
    {
        "post_url": "https://reddit.com/r/Python/comments/YYYYY/...",
        "must_include": ["r/learnpython"],
        "must_exclude": ["r/funny"],
        "min_results": 3,
    },
]
```

```python
# eval/run_eval.py
def test_golden_set():
    for case in EVAL_CASES:
        result = discover_subreddits(case["post_url"])
        found = {s.name for s in result.subreddits}
        for expected in case["must_include"]:
            assert expected in found, f"Missing expected: {expected}"
        for banned in case["must_exclude"]:
            assert banned not in found, f"Noise leaked through: {banned}"
        assert len(result.subreddits) >= case["min_results"]
```

> AI-resistant evaluations check for specific, non-obvious correctness criteria rather than generic "is this good?" [Anthropic: AI-Resistant Evaluations]

The golden set tests are "AI-resistant" because they check for **specific subreddits** (not "does this look reasonable?"), and the `must_include` set is based on your domain knowledge of what *should* appear.

#### LLM Filter Quality Eval

Separately measure the LLM filter's precision and recall:

```
For each eval post:
  1. Run pipeline WITHOUT LLM filter → raw subreddit list
  2. Manually label each subreddit: relevant / irrelevant
  3. Run pipeline WITH LLM filter → filtered list
  4. Compute:
     - Precision: % of filtered results that ARE relevant
     - Recall: % of relevant subreddits that SURVIVED filtering
     - Target: precision ≥ 0.85, recall ≥ 0.80
```

This tells you if the LLM is too aggressive (killing good results) or too permissive (letting noise through).

### Test File Structure

```
tests/
├── conftest.py               # Shared fixtures, mock factories
├── fixtures/
│   ├── post_comments.json    # Snapshot of a real post's comments
│   ├── user_overview.json    # Snapshot of a user's overview
│   └── llm_response.json    # Example LLM filter response
├── unit/
│   ├── test_ranker.py
│   ├── test_aggregator.py
│   ├── test_llm_filter.py
│   └── test_config.py
├── integration/
│   └── test_pipeline.py      # @pytest.mark.integration, hits real APIs
├── stability/
│   └── test_failure_modes.py  # Simulated failures
└── eval/
    ├── golden_set.py          # Expected results per post
    └── run_eval.py            # Value validation runner
```

### What to Run When

| When | What | Command |
|------|------|---------|
| Every code change | Unit tests | `pytest tests/unit/` |
| Before merging | Unit + stability | `pytest tests/unit/ tests/stability/` |
| Weekly / after prompt changes | Integration + eval | `pytest -m integration tests/` then `python eval/run_eval.py` |
| After changing LLM prompt | LLM filter eval | Manual precision/recall check |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reddit API rate limits (100/min) | Slow queries | Batch requests, respect limits, ~37s per query is acceptable for v0.1 |
| User profiles set to private | Missing data | Skip private users, log count. If >50% are private, warn user. |
| Reddit API deprecation/pricing | Existential | Keep abstraction layer clean so we can swap to Arctic Shift or scraping if needed |
| LLM hallucinating subreddit relevance | Bad results | Include subreddit subscriber count + description in prompt for grounding |
| Mega-subreddit noise | Useless results | Static blocklist + LLM filter as double defense |
| Bot accounts in top commenters | Noise | Account age + karma threshold as minimum filter |

---

## Success Criteria for v0.1

1. **Runs end-to-end** on a real post URL in under 60 seconds
2. **Produces useful results** -- when you run it on a post you know well, do the recommended subreddits make sense?
3. **Relevance filter works** -- irrelevant subreddits (hobbies, defaults) are removed
4. **You use it yourself** for 2 weeks and find at least 3 subreddits you didn't know about
