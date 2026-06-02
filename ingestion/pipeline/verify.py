#!/usr/bin/env python3
"""Regenerate catalog/gaps.md and print completeness stats."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

from catalog import load_catalog
from gaps_report import (
    compute_catalog_health,
    count_expanded_coverage,
    count_phase2_coverage,
    write_gaps_report,
)
from layout import scan_layout_violations
from paths import GAPS_PATH, ROOT


def main() -> None:
    rows = load_catalog()
    if not rows:
        raise SystemExit("catalog/episodes.jsonl is empty — run pipeline/build_catalog.py")

    health = compute_catalog_health(rows)

    (
        notes_files,
        notes_with_datapoints,
        posts_n,
        _,
        _,
        _,
        missing_timestamp_episodes,
    ) = count_phase2_coverage(rows)
    lost_ts_bullets = sum(c for _, c in missing_timestamp_episodes)
    expanded_n, expanded_drafts_n, _ = count_expanded_coverage(rows)

    layout_errors = scan_layout_violations(rows)
    write_gaps_report(rows, layout_errors=layout_errors)

    print(f"Catalog: {len(rows)} rows")
    print(f"Complete: {len(health.complete)} / {len(health.numbered)} numbered")
    print(
        f"Notes files: {notes_files} | with timestamp datapoints: {notes_with_datapoints} | "
        f"Posts: {posts_n}"
    )
    if lost_ts_bullets:
        print(
            f"Bullets missing timestamp: {lost_ts_bullets} across "
            f"{len(missing_timestamp_episodes)} episode(s)"
        )
    print(f"Expanded: {expanded_n} | expanded drafts: {expanded_drafts_n}")
    print(f"Unmapped colossus_url: {len(health.unmapped)}")
    print(f"Weak founders_url: {len(health.weak_urls)}")
    print(f"Blocking gaps: {len(health.blocking)}")
    print(f"Wrote {GAPS_PATH.relative_to(ROOT)}")

    for msg in health.blocking_messages(len(rows), layout_errors):
        raise SystemExit(f"VERIFY FAILED: {msg}")


if __name__ == "__main__":
    main()
