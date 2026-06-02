"""Generate catalog/gaps.md coverage report."""

from __future__ import annotations

from dataclasses import dataclass

from episode_ids import format_episode_id
from markdown_io import count_notes_datapoints_file, has_timestamp_datapoints
from paths import (
    GAPS_PATH,
    ROOT,
    expanded_draft_file_path,
    expanded_file_path,
    notes_file_path,
    post_file_path,
)

# Documented intentional gaps (see catalog/import-review.md)
POST_EXCEPTIONS: dict[int, str] = {
    159: "skipped — deleted on X or never posted",
    189: "not posted yet",
}

BLOCKING_STATUSES = {"pending", "failed"}


@dataclass(frozen=True)
class CatalogHealth:
    numbered: list[dict]
    specials: list[dict]
    complete: list[dict]
    blocking: list[dict]
    unmapped: list[dict]
    missing_files: list[str]
    weak_urls: list[dict]

    def blocking_messages(
        self, row_count: int, layout_errors: list[str], *, min_rows: int = 400
    ) -> list[str]:
        msgs: list[str] = []
        if row_count < min_rows:
            msgs.append(f"expected >= {min_rows} catalog rows, got {row_count}")
        if self.unmapped:
            msgs.append(f"{len(self.unmapped)} numbered episodes lack colossus_url")
        if self.blocking:
            msgs.append(f"{len(self.blocking)} blocking transcript gaps")
        if self.missing_files:
            msgs.append(f"{len(self.missing_files)} complete rows missing transcript files")
        if layout_errors:
            msgs.append(f"{len(layout_errors)} layout/id violations")
        return msgs


def compute_catalog_health(rows: list[dict]) -> CatalogHealth:
    numbered = [r for r in rows if r.get("episode_number") is not None]
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
    missing_files: list[str] = []
    for r in complete:
        rel = r.get("transcript_path")
        if not rel or not (ROOT / rel).exists():
            missing_files.append(r["id"])

    return CatalogHealth(
        numbered=numbered,
        specials=[r for r in rows if r.get("episode_number") is None],
        complete=complete,
        blocking=blocking,
        unmapped=[r for r in numbered if not r.get("colossus_url")],
        missing_files=missing_files,
        weak_urls=[
            r
            for r in rows
            if (r.get("founders_url") or "").rstrip("/") == "https://www.founderspodcast.com"
        ],
    )


def count_phase2_coverage(
    rows: list[dict],
) -> tuple[
    int,
    int,
    int,
    list[int],
    list[int],
    list[int],
    list[tuple[int, int]],
]:
    """Returns (notes_files, notes_with_datapoints, posts_count, missing_notes, missing_datapoints, missing_posts, missing_timestamp_episodes).

    missing_timestamp_episodes: (episode_number, bullet_count) for notes with `- —` bullets lacking MM:SS.
    missing_datapoints: numbered episodes with no timestamp bullets (includes empty scaffolds and lost-timestamp-only).
    """
    notes_files = 0
    notes_with_datapoints = 0
    posts_n = 0
    missing_notes: list[int] = []
    missing_datapoints: list[int] = []
    missing_posts: list[int] = []
    missing_timestamp_episodes: list[tuple[int, int]] = []

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
            counts = count_notes_datapoints_file(npath)
            if counts.timestamped > 0:
                notes_with_datapoints += 1
            else:
                missing_datapoints.append(num)
            if counts.missing_timestamp > 0:
                missing_timestamp_episodes.append((num, counts.missing_timestamp))
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
        missing_timestamp_episodes,
    )


def count_expanded_coverage(
    rows: list[dict],
) -> tuple[int, int, list[int]]:
    """Returns (expanded_files, expanded_drafts, missing_expanded_episode_numbers).

    missing_expanded_* counts numbered episodes with transcript + datapoints but no .expanded.md.
    """
    expanded_n = 0
    drafts_n = 0
    missing_expanded: list[int] = []

    for r in rows:
        num = r.get("episode_number")
        if num is None or r.get("transcript_status") != "complete":
            continue
        ep_id = r["id"]
        slug = r["slug"]
        npath = notes_file_path(ep_id, slug, num)
        if expanded_file_path(ep_id, slug, num).exists():
            expanded_n += 1
        if expanded_draft_file_path(ep_id, slug, num).exists():
            drafts_n += 1
        if npath.exists() and has_timestamp_datapoints(npath):
            if not expanded_file_path(ep_id, slug, num).exists():
                missing_expanded.append(num)

    return expanded_n, drafts_n, missing_expanded


def build_gaps_markdown(
    rows: list[dict],
    *,
    layout_errors: list[str],
) -> str:
    health = compute_catalog_health(rows)

    (
        notes_files,
        notes_with_datapoints,
        posts_n,
        missing_notes,
        missing_datapoints,
        missing_posts,
        missing_timestamp_episodes,
    ) = count_phase2_coverage(rows)
    lost_ts_ep_nums = {n for n, _ in missing_timestamp_episodes}
    total_lost_ts_bullets = sum(c for _, c in missing_timestamp_episodes)
    transcript_complete_numbered = sum(
        1 for r in health.numbered if r.get("transcript_status") == "complete"
    )
    expanded_n, expanded_drafts_n, missing_expanded_list = count_expanded_coverage(rows)

    lines = [
        "# Catalog gaps (auto-generated)",
        "",
        "> **Work in progress:** Low note/post counts are expected. Ethan adds timestamp bullets",
        "> daily (~1 episode) while listening; empty scaffolds are placeholders, not import failures.",
        "> See [docs/notes-pipeline.md](../docs/notes-pipeline.md). Only **blocking** transcript gaps matter for Phase 1.",
        "",
        f"**Total episodes:** {len(rows)}",
        f"**Numbered:** {len(health.numbered)} | **Specials:** {len(health.specials)}",
        f"**Transcripts complete:** {len(health.complete)}",
        "",
        "## Phase 2 coverage",
        "",
        f"**Notes files:** {notes_files} / {transcript_complete_numbered} numbered (with transcript)",
        f"**Notes with datapoints:** {notes_with_datapoints} / {transcript_complete_numbered} numbered (timestamp bullets)",
        (
            f"**Bullets missing timestamp:** {total_lost_ts_bullets} across "
            f"{len(missing_timestamp_episodes)} numbered (`- —` without `MM:SS`)"
            if missing_timestamp_episodes
            else "**Bullets missing timestamp:** 0"
        ),
        f"**Posts imported:** {posts_n} / {transcript_complete_numbered} numbered",
        f"**Expanded notes:** {expanded_n} / {transcript_complete_numbered} numbered (with transcript)",
        f"**Expanded drafts (pending review):** {expanded_drafts_n} / {transcript_complete_numbered} numbered",
        "",
    ]

    if health.weak_urls:
        lines.append(f"## Weak founders_url ({len(health.weak_urls)})")
        lines.append("")
        lines.append(
            "Homepage URL instead of `/episodes/…`. Run `python pipeline/sync_new.py --repair-urls --apply`."
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

    scaffold_only = [
        n for n in missing_datapoints if n not in missing_notes and n not in lost_ts_ep_nums
    ]
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

    if missing_timestamp_episodes:
        lines.append(
            f"## Datapoint bullets missing timestamp ({len(missing_timestamp_episodes)} numbered)"
        )
        lines.append("")
        lines.append(
            "Notes contain `- — …` bullets with no `MM:SS` prefix — timestamp may have been lost. "
            "Re-add times before LLM expand; mixed episodes may still expand from timestamped bullets only."
        )
        lines.append("")
        for n, bullet_count in sorted(missing_timestamp_episodes)[:40]:
            lines.append(f"- `{format_episode_id(n)}` ({bullet_count} bullet(s))")
        if len(missing_timestamp_episodes) > 40:
            lines.append(f"- … and {len(missing_timestamp_episodes) - 40} more")
        lines.append("")

    if missing_expanded_list:
        lines.append(
            f"## Has datapoints, no expanded.md ({len(missing_expanded_list)} numbered)"
        )
        lines.append("")
        lines.append(
            "Optional LLM expansion: `python notes/expand_datapoints_llm.py --missing-expanded --dry-run` "
            "then `--apply` (draft) and `--promote --apply`. "
            "See [docs/expanded-backfill.md](../docs/expanded-backfill.md) and "
            "[docs/datapoint-workflow.md](../docs/datapoint-workflow.md)."
        )
        lines.append("")
        for n in sorted(missing_expanded_list)[:40]:
            lines.append(f"- `{format_episode_id(n)}`")
        if len(missing_expanded_list) > 40:
            lines.append(f"- … and {len(missing_expanded_list) - 40} more")
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

    if health.unmapped:
        lines.append(f"## Unmapped Colossus URLs ({len(health.unmapped)})")
        lines.append("")
        for r in health.unmapped[:50]:
            lines.append(f"- `{r['id']}` — {r['title']} — {r['founders_url']}")
        if len(health.unmapped) > 50:
            lines.append(f"- … and {len(health.unmapped) - 50} more")
        lines.append("")

    if health.blocking:
        lines.append(f"## Blocking transcript gaps ({len(health.blocking)})")
        lines.append("")
        for r in health.blocking[:50]:
            err = r.get("last_error") or r.get("transcript_status")
            lines.append(f"- `{r['id']}` — {err}")
        if len(health.blocking) > 50:
            lines.append(f"- … and {len(health.blocking) - 50} more")
        lines.append("")

    documented = [
        r
        for r in rows
        if r.get("transcript_status") in ("coming_soon", "no_transcript")
        and r not in health.blocking
    ]
    if documented:
        lines.append(f"## Documented exceptions ({len(documented)})")
        lines.append("")
        for r in documented[:30]:
            lines.append(f"- `{r['id']}` — {r['transcript_status']}")
        lines.append("")

    if health.missing_files:
        lines.append(f"## Missing transcript files ({len(health.missing_files)})")
        for mid in health.missing_files[:20]:
            lines.append(f"- `{mid}`")
        lines.append("")

    if not health.unmapped and not health.blocking and not health.missing_files:
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
