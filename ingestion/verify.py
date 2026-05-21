#!/usr/bin/env python3
"""Regenerate catalog/gaps.md and print completeness stats."""

from __future__ import annotations

from pathlib import Path

from vault_lib import GAPS_PATH, ROOT, load_catalog, notes_dir, post_dir

BLOCKING_STATUSES = {"pending", "failed"}

# Documented intentional gaps (see catalog/import-review.md)
POST_EXCEPTIONS: dict[int, str] = {
    159: "skipped — deleted on X or never posted",
    189: "not posted yet",
}


def count_phase2_coverage(rows: list[dict]) -> tuple[int, int, list[int], list[int]]:
    """Returns (notes_count, posts_count, missing_notes, missing_posts) for numbered complete transcripts."""
    notes_n = 0
    posts_n = 0
    missing_notes: list[int] = []
    missing_posts: list[int] = []

    for r in rows:
        if r.get("episode_number") is None:
            continue
        if r.get("transcript_status") != "complete":
            continue
        ep_id = r["id"]
        slug = r["slug"]
        num = r["episode_number"]
        if (notes_dir(ep_id, slug) / "notes.md").exists():
            notes_n += 1
        else:
            missing_notes.append(num)
        if (post_dir(ep_id, slug) / "post.md").exists():
            posts_n += 1
        else:
            missing_posts.append(num)

    return notes_n, posts_n, missing_notes, missing_posts


def main() -> None:
    rows = load_catalog()
    if not rows:
        raise SystemExit("catalog/episodes.jsonl is empty — run build_catalog.py")

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
        rel = r.get("transcript_path")
        if not rel or not (ROOT / rel).exists():
            missing_files.append(r["id"])

    weak_urls = [
        r
        for r in rows
        if (r.get("founders_url") or "").rstrip("/") in (
            "https://www.founderspodcast.com",
            "https://www.founderspodcast.com/",
        )
    ]

    notes_n, posts_n, missing_notes, missing_posts = count_phase2_coverage(rows)
    transcript_complete_numbered = sum(
        1 for r in numbered if r.get("transcript_status") == "complete"
    )

    lines = [
        "# Catalog gaps (auto-generated)",
        "",
        f"**Total episodes:** {len(rows)}",
        f"**Numbered:** {len(numbered)} | **Specials:** {len(specials)}",
        f"**Transcripts complete:** {len(complete)}",
        "",
        "## Phase 2 coverage",
        "",
        f"**Notes imported:** {notes_n} / {transcript_complete_numbered} numbered (with transcript)",
        f"**Posts imported:** {posts_n} / {transcript_complete_numbered} numbered",
        "",
    ]

    if weak_urls:
        lines.append(f"## Weak founders_url ({len(weak_urls)})")
        lines.append("")
        lines.append("Homepage URL instead of `/episodes/…`. Run `python sync_new.py --repair-urls --apply`.")
        lines.append("")

    if missing_notes:
        lines.append(f"## Missing notes ({len(missing_notes)} numbered)")
        lines.append("")
        for n in sorted(missing_notes)[:40]:
            lines.append(f"- `ep-{n}`")
        if len(missing_notes) > 40:
            lines.append(f"- … and {len(missing_notes) - 40} more")
        lines.append("")

    if missing_posts:
        documented_post = [n for n in missing_posts if n in POST_EXCEPTIONS]
        blocking_post = [n for n in missing_posts if n not in POST_EXCEPTIONS]
        if blocking_post:
            lines.append(f"## Missing posts ({len(blocking_post)} numbered)")
            lines.append("")
            for n in sorted(blocking_post)[:40]:
                lines.append(f"- `ep-{n}`")
            if len(blocking_post) > 40:
                lines.append(f"- … and {len(blocking_post) - 40} more")
            lines.append("")
        if documented_post:
            lines.append(f"## Post gaps (documented, {len(documented_post)})")
            lines.append("")
            for n in sorted(documented_post):
                lines.append(f"- `ep-{n}` — {POST_EXCEPTIONS[n]}")
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

    GAPS_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Catalog: {len(rows)} rows")
    print(f"Complete: {len(complete)} / {len(numbered)} numbered")
    print(f"Notes: {notes_n} | Posts: {posts_n}")
    print(f"Unmapped colossus_url: {len(unmapped)}")
    print(f"Weak founders_url: {len(weak_urls)}")
    print(f"Blocking gaps: {len(blocking)}")
    print(f"Wrote {GAPS_PATH.relative_to(ROOT)}")

    if len(rows) < 400:
        raise SystemExit(f"VERIFY FAILED: expected >= 400 rows, got {len(rows)}")
    if unmapped:
        raise SystemExit(f"VERIFY FAILED: {len(unmapped)} numbered episodes lack colossus_url")
    if blocking:
        raise SystemExit(f"VERIFY FAILED: {len(blocking)} blocking transcript gaps")
    if missing_files:
        raise SystemExit(f"VERIFY FAILED: {len(missing_files)} complete rows missing files")


if __name__ == "__main__":
    main()
