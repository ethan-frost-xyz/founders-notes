"""Generate catalog/gaps.md coverage report."""

from __future__ import annotations

from episode_ids import format_episode_id
from markdown_io import has_timestamp_datapoints
from paths import GAPS_PATH, notes_file_path, post_file_path

# Documented intentional gaps (see catalog/import-review.md)
POST_EXCEPTIONS: dict[int, str] = {
    159: "skipped — deleted on X or never posted",
    189: "not posted yet",
}

BLOCKING_STATUSES = {"pending", "failed"}


def count_phase2_coverage(
    rows: list[dict],
) -> tuple[int, int, int, list[int], list[int], list[int]]:
    """Returns (notes_files, notes_with_datapoints, posts_count, missing_notes, missing_datapoints, missing_posts)."""
    notes_files = 0
    notes_with_datapoints = 0
    posts_n = 0
    missing_notes: list[int] = []
    missing_datapoints: list[int] = []
    missing_posts: list[int] = []

    for r in rows:
        if r.get("episode_number") is None:
            continue
        if r.get("transcript_status") != "complete":
            continue
        ep_id = r["id"]
        slug = r["slug"]
        num = r["episode_number"]
        npath = notes_file_path(ep_id, slug, num)
        if npath.exists():
            notes_files += 1
            if has_timestamp_datapoints(npath):
                notes_with_datapoints += 1
            else:
                missing_datapoints.append(num)
        else:
            missing_notes.append(num)
            missing_datapoints.append(num)
        if post_file_path(ep_id, slug, num).exists():
            posts_n += 1
        else:
            missing_posts.append(num)

    return (
        notes_files,
        notes_with_datapoints,
        posts_n,
        missing_notes,
        missing_datapoints,
        missing_posts,
    )


def build_gaps_markdown(
    rows: list[dict],
    *,
    layout_errors: list[str],
) -> str:
    numbered = [r for r in rows if r.get("episode_number") is not None]
    specials = [r for r in rows if r.get("episode_number") is None]
    complete = [r for r in rows if r.get("transcript_status") == "complete"]
    blocking = [
        r
        for r in numbered
        if r.get("transcript_status") in BLOCKING_STATUSES
        or (
            r.get("colossus_url")
            and r.get("transcript_status") not in ("complete", "coming_soon", "no_transcript")
        )
    ]
    unmapped = [r for r in numbered if not r.get("colossus_url")]
    missing_files = []
    for r in complete:
        from paths import ROOT

        rel = r.get("transcript_path")
        if not rel or not (ROOT / rel).exists():
            missing_files.append(r["id"])

    weak_urls = [
        r
        for r in rows
        if (r.get("founders_url") or "").rstrip("/")
        in (
            "https://www.founderspodcast.com",
            "https://www.founderspodcast.com/",
        )
    ]

    (
        notes_files,
        notes_with_datapoints,
        posts_n,
        missing_notes,
        missing_datapoints,
        missing_posts,
    ) = count_phase2_coverage(rows)
    transcript_complete_numbered = sum(
        1 for r in numbered if r.get("transcript_status") == "complete"
    )

    lines = [
        "# Catalog gaps (auto-generated)",
        "",
        "> **Work in progress:** Low note/post counts are expected. Ethan adds timestamp bullets",
        "> daily (~1 episode) while listening; empty scaffolds are placeholders, not import failures.",
        "> See [docs/notes-pipeline.md](../docs/notes-pipeline.md). Only **blocking** transcript gaps matter for Phase 1.",
        "",
        f"**Total episodes:** {len(rows)}",
        f"**Numbered:** {len(numbered)} | **Specials:** {len(specials)}",
        f"**Transcripts complete:** {len(complete)}",
        "",
        "## Phase 2 coverage",
        "",
        f"**Notes files:** {notes_files} / {transcript_complete_numbered} numbered (with transcript)",
        f"**Notes with datapoints:** {notes_with_datapoints} / {transcript_complete_numbered} numbered (timestamp bullets)",
        f"**Posts imported:** {posts_n} / {transcript_complete_numbered} numbered",
        "",
    ]

    if weak_urls:
        lines.append(f"## Weak founders_url ({len(weak_urls)})")
        lines.append("")
        lines.append(
            "Homepage URL instead of `/episodes/…`. Run `python sync_new.py --repair-urls --apply`."
        )
        lines.append("")

    if missing_notes:
        lines.append(f"## Missing notes files ({len(missing_notes)} numbered)")
        lines.append("")
        for n in sorted(missing_notes)[:40]:
            lines.append(f"- `{format_episode_id(n)}`")
        if len(missing_notes) > 40:
            lines.append(f"- … and {len(missing_notes) - 40} more")
        lines.append("")

    scaffold_only = [n for n in missing_datapoints if n not in missing_notes]
    if scaffold_only:
        lines.append(f"## Notes without datapoints ({len(scaffold_only)} numbered)")
        lines.append("")
        lines.append(
            "File exists but no `MM:SS —` bullets yet — **expected** for episodes not listened to "
            "(empty scaffold or backlog). Filled in over time via the daily notes workflow; not a blocking gap."
        )
        lines.append("")
        for n in sorted(scaffold_only)[:40]:
            lines.append(f"- `{format_episode_id(n)}`")
        if len(scaffold_only) > 40:
            lines.append(f"- … and {len(scaffold_only) - 40} more")
        lines.append("")

    if missing_posts:
        documented_post = [n for n in missing_posts if n in POST_EXCEPTIONS]
        blocking_post = [n for n in missing_posts if n not in POST_EXCEPTIONS]
        if blocking_post:
            lines.append(f"## Missing posts ({len(blocking_post)} numbered)")
            lines.append("")
            for n in sorted(blocking_post)[:40]:
                lines.append(f"- `{format_episode_id(n)}`")
            if len(blocking_post) > 40:
                lines.append(f"- … and {len(blocking_post) - 40} more")
            lines.append("")
        if documented_post:
            lines.append(f"## Post gaps (documented, {len(documented_post)})")
            lines.append("")
            for n in sorted(documented_post):
                lines.append(f"- `{format_episode_id(n)}` — {POST_EXCEPTIONS[n]}")
            lines.append("")

    if unmapped:
        lines.append(f"## Unmapped Colossus URLs ({len(unmapped)})")
        lines.append("")
        for r in unmapped[:50]:
            lines.append(f"- `{r['id']}` — {r['title']} — {r['founders_url']}")
        if len(unmapped) > 50:
            lines.append(f"- … and {len(unmapped) - 50} more")
        lines.append("")

    if blocking:
        lines.append(f"## Blocking transcript gaps ({len(blocking)})")
        lines.append("")
        for r in blocking[:50]:
            err = r.get("last_error") or r.get("transcript_status")
            lines.append(f"- `{r['id']}` — {err}")
        if len(blocking) > 50:
            lines.append(f"- … and {len(blocking) - 50} more")
        lines.append("")

    documented = [
        r
        for r in rows
        if r.get("transcript_status") in ("coming_soon", "no_transcript")
        and r not in blocking
    ]
    if documented:
        lines.append(f"## Documented exceptions ({len(documented)})")
        lines.append("")
        for r in documented[:30]:
            lines.append(f"- `{r['id']}` — {r['transcript_status']}")
        lines.append("")

    if missing_files:
        lines.append(f"## Missing transcript files ({len(missing_files)})")
        for mid in missing_files[:20]:
            lines.append(f"- `{mid}`")
        lines.append("")

    if not unmapped and not blocking and not missing_files:
        lines.append("No blocking gaps. Phase 1 transcript archive is complete.")
        lines.append("")

    if layout_errors:
        lines.append(f"## Layout violations ({len(layout_errors)})")
        lines.append("")
        for err in layout_errors[:30]:
            lines.append(f"- {err}")
        if len(layout_errors) > 30:
            lines.append(f"- … and {len(layout_errors) - 30} more")
        lines.append("")

    return "\n".join(lines)


def write_gaps_report(rows: list[dict], layout_errors: list[str]) -> None:
    GAPS_PATH.write_text(
        build_gaps_markdown(rows, layout_errors=layout_errors),
        encoding="utf-8",
    )
