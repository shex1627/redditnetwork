"""CLI entrypoint — paste a Reddit post URL, get a subreddit discovery map."""

from __future__ import annotations

import logging

import click
from rich.console import Console
from rich.table import Table

from reddit_network.config import DEFAULT_MIN_RELEVANCE, DEFAULT_TOP_N_COMMENTERS
from reddit_network.pipeline import discover_subreddits

console = Console()


@click.command()
@click.argument("post_url")
@click.option(
    "-n",
    "--top-n",
    default=DEFAULT_TOP_N_COMMENTERS,
    show_default=True,
    help="Number of top commenters to analyze.",
)
@click.option(
    "-r",
    "--min-relevance",
    default=DEFAULT_MIN_RELEVANCE,
    show_default=True,
    help="Minimum LLM relevance score (0-10) to include.",
)
@click.option(
    "--raw",
    is_flag=True,
    help="Show raw (unfiltered) subreddit map alongside filtered results.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose logging (DEBUG level).",
)
def main(post_url: str, top_n: int, min_relevance: int, raw: bool, verbose: bool) -> None:
    """Discover related subreddits from a Reddit post URL."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    with console.status("[bold green]Running discovery pipeline..."):
        result = discover_subreddits(
            post_url=post_url,
            top_n_commenters=top_n,
            min_relevance=min_relevance,
            on_progress=lambda msg, _frac: console.log(msg),
        )

    # --- Post info ---
    console.print()
    console.rule("[bold]Reddit Network Discovery")
    console.print(f'[bold]"{result.post.title}"[/bold]')
    console.print(
        f"r/{result.post.subreddit}  |  "
        f"{result.post.score} upvotes  |  "
        f"{result.post.num_comments} comments"
    )
    console.print(
        f"Analyzed {result.commenters_analyzed} commenters"
        f" (skipped {result.commenters_skipped})"
    )
    console.print()

    # --- Warnings ---
    for warning in result.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")

    # --- Results table ---
    if not result.subreddits:
        console.print("[red]No related subreddits found.[/red]")
        return

    table = Table(title="Related Subreddits", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Subreddit", style="bold cyan")
    table.add_column("Commenters", justify="right")
    table.add_column("Activity", justify="right")
    if result.llm_filtered:
        table.add_column("Relevance", justify="right")
        table.add_column("Why", style="dim")

    for i, sub in enumerate(result.subreddits, 1):
        row = [
            str(i),
            f"r/{sub.name}",
            f"{sub.commenter_count}/{result.commenters_analyzed}",
            str(sub.total_activity),
        ]
        if result.llm_filtered:
            row.append(f"{sub.relevance_score}/10")
            row.append(sub.reason)
        table.add_row(*row)

    console.print(table)

    # --- Raw data ---
    if raw and result.raw_subreddits:
        console.print()
        raw_table = Table(title="Raw Subreddit Map (unfiltered)", show_lines=False)
        raw_table.add_column("Subreddit", style="cyan")
        raw_table.add_column("Commenters", justify="right")
        raw_table.add_column("Activity", justify="right")
        for sub in result.raw_subreddits[:50]:
            raw_table.add_row(
                f"r/{sub.name}",
                str(sub.commenter_count),
                str(sub.total_activity),
            )
        console.print(raw_table)

    # --- Top commenters ---
    console.print()
    console.rule("[bold]Top Commenters")
    for r in result.commenters[:10]:
        subs = {a.subreddit for a in r.profile.activities}
        console.print(
            f"  u/{r.username}  "
            f"(comment score: {r.comment.score}, "
            f"active in {len(subs)} subreddits)"
        )


if __name__ == "__main__":
    main()
