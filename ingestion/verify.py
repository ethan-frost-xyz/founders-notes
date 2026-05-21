#!/usr/bin/env python3
"""Regenerate catalog/gaps.md and print completeness stats."""

from __future__ import annotations

import re
from pathlib import Path

from vault_lib import (
    CONTENT_TYPES,
    EPISODE_NUMBER_WIDTH,
    GAPS_PATH,
    NOTES_DIR,
    POSTS_DIR,
    ROOT,
    TRANSCRIPTS_DIR,
    content_filename,
    format_episode_id,
    load_catalog,
    notes_file_path,
    post_file_path,
    transcript_path,
)

NUMBERED_ID_RE = re.compile(rf"^ep-\d{{{EPISODE_NUMBER_WIDTH}}}$")
LEGACY_EP_DIR_RE = re.compile(r"^ep-\d{1,3}-")
LEGACY_BARE_FILES = frozenset({"notes.md", "post.md", "expanded.md", "transcript.md"})
PER_EPISODE_FILE_RE = re.compile(
    r"^(?P<folder>.+)\.(?P<ctype>transcript|notes|expanded|post)\.md$"
)

BLOCKING_STATUSES = {"pending", "failed"}
TIMESTAMP_BULLET_RE = re.compile(
    r"^[\s]*-\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*.+$",
    re.MULTILINE,
)

# Documented intentional gaps (see catalog/import-review.md)
POST_EXCEPTIONS: dict[int, str] = {
    159: "skipped — deleted on X or never posted",
    189: "not posted yet",
}


def notes_body_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        return parts[2] if len(parts) >= 3 else text
    return text


def has_timestamp_datapoints(path: Path) -> bool:
    return bool(TIMESTAMP_BULLET_RE.search(notes_body_text(path)))


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


def scan_layout_violations(rows: list[dict]) -> list[str]:
    """Return human-readable layout/id violations."""
    errors: list[str] = []

    for r in rows:
        num = r.get("episode_number")
        ep_id = r["id"]
        if num is not None:
            if not NUMBERED_ID_RE.match(ep_id):
                errors.append(f"bad id format: {ep_id} (expected ep-{'0' * EPISODE_NUMBER_WIDTH}N)")
            expected_id = format_episode_id(num)
            if ep_id != expected_id:
                errors.append(f"id mismatch ep {num}: catalog {ep_id} != {expected_id}")
            if r.get("transcript_status") == "complete":
                expected_tx = transcript_path(ep_id, r["slug"], num)
                if r.get("transcript_path") != expected_tx:
                    errors.append(
                        f"transcript_path mismatch {ep_id}: {r.get('transcript_path')} != {expected_tx}"
                    )

    for base in (TRANSCRIPTS_DIR, NOTES_DIR, POSTS_DIR):
        if not base.exists():
            continue
        for child in base.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if LEGACY_EP_DIR_RE.match(child.name):
                errors.append(f"legacy folder name: {child.relative_to(ROOT)}")
            for f in child.iterdir():
                if not f.is_file() or not f.name.endswith(".md"):
                    continue
                if f.name in LEGACY_BARE_FILES:
                    errors.append(f"legacy bare filename: {f.relative_to(ROOT)}")
                    continue
                m = PER_EPISODE_FILE_RE.match(f.name)
                if not m:
                    if f.name == f"{child.name}.md":
                        errors.append(f"legacy transcript filename: {f.relative_to(ROOT)}")
                    else:
                        errors.append(f"unexpected file: {f.relative_to(ROOT)}")
                    continue
                if m.group("folder") != child.name:
                    errors.append(
                        f"filename folder prefix != dir: {f.relative_to(ROOT)}"
                    )
                if m.group("ctype") not in CONTENT_TYPES:
                    errors.append(f"unknown content type in filename: {f.relative_to(ROOT)}")
    return errors


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
        lines.append("Homepage URL instead of `/episodes/…`. Run `python sync_new.py --repair-urls --apply`.")
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
        lines.append("File exists but no `MM:SS —` bullets under `## Raw datapoints` (empty scaffold or not started).")
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

    layout_errors = scan_layout_violations(rows)
    if layout_errors:
        lines.append(f"## Layout violations ({len(layout_errors)})")
        lines.append("")
        for err in layout_errors[:30]:
            lines.append(f"- {err}")
        if len(layout_errors) > 30:
            lines.append(f"- … and {len(layout_errors) - 30} more")
        lines.append("")

    GAPS_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Catalog: {len(rows)} rows")
    print(f"Complete: {len(complete)} / {len(numbered)} numbered")
    print(f"Notes files: {notes_files} | with datapoints: {notes_with_datapoints} | Posts: {posts_n}")
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
    if layout_errors:
        raise SystemExit(f"VERIFY FAILED: {len(layout_errors)} layout/id violations")


if __name__ == "__main__":
    main()
