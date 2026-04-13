"""Streamlit UI for Reddit Network Discovery — calls the FastAPI backend."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

from reddit_network.config import DEFAULT_MIN_RELEVANCE, DEFAULT_TOP_N_COMMENTERS

API_BASE = "http://localhost:8550"

st.set_page_config(
    page_title="Reddit Network Discovery",
    page_icon="🕸️",
    layout="wide",
)


def _sub_link(name: str) -> str:
    """Markdown link to a subreddit."""
    return f"[r/{name}](https://www.reddit.com/r/{name})"


def _user_link(username: str) -> str:
    """Markdown link to a Reddit user profile."""
    return f"[u/{username}](https://www.reddit.com/user/{username})"


def _build_full_export(result: dict) -> str:
    """Build a JSON export from the API response dict."""
    return json.dumps(
        {"exported_at": datetime.now(timezone.utc).isoformat(), **result},
        indent=2,
    )


def _build_csv(result: dict) -> str:
    """Build CSV with subreddit URLs and user URLs."""
    rows = []
    for s in result["filtered_subreddits"]:
        rows.append({
            "Subreddit": f"r/{s['name']}",
            "URL": f"https://www.reddit.com/r/{s['name']}",
            "Commenters": f"{s['commenter_count']}/{result['commenters_analyzed']}",
            "Activity": s["total_activity"],
            "Relevance": s["relevance_score"] if result["llm_filtered"] else "",
            "Why": s["reason"] if result["llm_filtered"] else "",
        })
    return pd.DataFrame(rows).to_csv(index=False)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("Settings")
top_n = st.sidebar.slider(
    "Top N commenters to analyze",
    min_value=5,
    max_value=50,
    value=DEFAULT_TOP_N_COMMENTERS,
)
min_relevance = st.sidebar.slider(
    "Min relevance score (0-10)",
    min_value=1,
    max_value=10,
    value=DEFAULT_MIN_RELEVANCE,
)
show_raw = st.sidebar.checkbox("Show raw (unfiltered) data", value=False)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

st.title("Reddit Network Discovery")
st.caption(
    "Paste a Reddit post URL to discover related subreddits "
    "based on where the top commenters are active."
)

post_url = st.text_input(
    "Reddit Post URL",
    placeholder="https://www.reddit.com/r/datascience/comments/...",
)

# --- Run pipeline on button click, store result in session_state ---
if st.button("Discover", type="primary", disabled=not post_url):
    with st.status("Running discovery pipeline...", expanded=True) as status:
        try:
            resp = requests.post(
                f"{API_BASE}/discover",
                json={
                    "post_url": post_url,
                    "top_n_commenters": top_n,
                    "min_relevance": min_relevance,
                },
                timeout=180,
            )
        except requests.ConnectionError:
            status.update(label="Error", state="error")
            st.error(
                "Could not connect to the API server. "
                "Make sure it's running: `uvicorn reddit_network.api:app`"
            )
            st.stop()

        if resp.status_code == 429:
            status.update(label="Rate limited", state="error")
            st.error("Too many requests — please wait a minute before trying again.")
            st.stop()

        if resp.status_code != 200:
            status.update(label="Error", state="error")
            detail = resp.json().get("detail", resp.text)
            st.error(f"API error: {detail}")
            st.stop()

        st.session_state["result"] = resp.json()
        status.update(label="Done!", state="complete")

# --- Display results from session_state (persists across reruns) ---
if "result" not in st.session_state:
    st.stop()

result = st.session_state["result"]

if not isinstance(result, dict):
    del st.session_state["result"]
    st.rerun()

post = result["post"]
filtered = result["filtered_subreddits"]
raw = result["raw_subreddits"]
commenters = result["top_commenters"]
llm_filtered = result["llm_filtered"]

# --- Warnings ---
for warning in result.get("warnings", []):
    st.warning(warning)

# --- Post info ---
st.subheader(f'"{post["title"]}"')
col1, col2, col3, col4 = st.columns(4)
col1.metric("Subreddit", f"r/{post['subreddit']}")
col2.metric("Upvotes", f"{post['score']:,}")
col3.metric("Comments", f"{post['num_comments']:,}")
col4.metric("Commenters Analyzed", result["commenters_analyzed"])

if not filtered:
    st.info("No related subreddits found.")
    st.stop()

# --- Results table (with clickable links) ---
st.subheader("Related Subreddits")

sub_table = ""
if llm_filtered:
    sub_table += "| Subreddit | Commenters | Relevance | Why |\n"
    sub_table += "|:----------|----------:|:---------:|:----|\n"
    for s in filtered:
        sub_table += (
            f"| {_sub_link(s['name'])} "
            f"| {s['commenter_count']}/{result['commenters_analyzed']} "
            f"| {s['relevance_score']}/10 "
            f"| {s['reason']} |\n"
        )
else:
    sub_table += "| Subreddit | Commenters | Activity |\n"
    sub_table += "|:----------|----------:|---------:|\n"
    for s in filtered:
        sub_table += (
            f"| {_sub_link(s['name'])} "
            f"| {s['commenter_count']}/{result['commenters_analyzed']} "
            f"| {s['total_activity']} |\n"
        )

st.markdown(sub_table)

st.download_button(
    "Export filtered subreddits (CSV)",
    data=_build_csv(result),
    file_name=f"subreddits_{post['subreddit']}_{post['post_id']}.csv",
    mime="text/csv",
)

# --- Bar chart ---
chart_data = pd.DataFrame(
    {
        "Subreddit": [f"r/{s['name']}" for s in filtered[:15]],
        "Commenter Overlap": [s["commenter_count"] for s in filtered[:15]],
    }
)
st.subheader("Top Subreddits by Commenter Overlap")
st.bar_chart(chart_data, x="Subreddit", y="Commenter Overlap")

# --- Top commenters (with clickable links) ---
st.subheader("Top Commenters")
for c in commenters[:10]:
    subs = c["active_subreddits"]
    with st.expander(
        f"u/{c['username']}  —  comment score: {c['comment_score']}, "
        f"active in {len(subs)} subreddits"
    ):
        st.markdown(f"**Profile:** {_user_link(c['username'])}")
        st.write(f"**Karma:** {c['comment_karma']:,}")
        st.write(f"**Account age:** {c['account_age_days']} days")
        st.markdown(
            "**Active subreddits:** "
            + ", ".join(_sub_link(s) for s in subs[:30])
        )

# --- Raw data ---
if show_raw and raw:
    st.subheader("Raw Subreddit Map (unfiltered)")
    raw_table = "| Subreddit | Commenters | Activity | Avg Score |\n"
    raw_table += "|:----------|----------:|---------:|----------:|\n"
    for s in raw[:50]:
        raw_table += (
            f"| {_sub_link(s['name'])} "
            f"| {s['commenter_count']} "
            f"| {s['total_activity']} "
            f"| {s['avg_score']:.1f} |\n"
        )
    st.markdown(raw_table)

    raw_df = pd.DataFrame(
        [
            {
                "Subreddit": f"r/{s['name']}",
                "URL": f"https://www.reddit.com/r/{s['name']}",
                "Commenters": s["commenter_count"],
                "Activity": s["total_activity"],
                "Avg Score": f"{s['avg_score']:.1f}",
            }
            for s in raw[:50]
        ]
    )
    st.download_button(
        "Export raw subreddits (CSV)",
        data=raw_df.to_csv(index=False),
        file_name=f"raw_subreddits_{post['subreddit']}_{post['post_id']}.csv",
        mime="text/csv",
    )

# --- Full export ---
st.divider()
st.download_button(
    "Export full results (JSON)",
    data=_build_full_export(result),
    file_name=f"reddit_network_{post['subreddit']}_{post['post_id']}.json",
    mime="application/json",
)
