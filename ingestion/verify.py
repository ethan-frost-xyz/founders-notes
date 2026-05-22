#!/usr/bin/env python3
"""Regenerate catalog/gaps.md and print completeness stats."""

from __future__ import annotations

from catalog import load_catalog
from gaps_report import count_phase2_coverage, write_gaps_report
from layout import scan_layout_violations
from paths import GAPS_PATH, ROOT


def main() -> None:
    rows = load_catalog()
    if not rows:
        raise SystemExit("catalog/episodes.jsonl is empty — run build_catalog.py")

    numbered = [r for r in rows if r.get("episode_number") is not None]
    complete = [r for r in rows if r.get("transcript_status") == "complete"]
    blocking = [
        r
        for r in numbered
        if r.get("transcript_status") in {"pending", "failed"}
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
        _,
        _,
        _,
    ) = count_phase2_coverage(rows)

    layout_errors = scan_layout_violations(rows)
    write_gaps_report(rows, layout_errors=layout_errors)

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
