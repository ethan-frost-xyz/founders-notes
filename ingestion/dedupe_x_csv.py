#!/usr/bin/env python3
"""One-off: dedupe import/x-posts-raw.csv by x_post_id (keeps last row)."""

from __future__ import annotations

import csv

from x_posts_lib import CSV_COLUMNS, X_POSTS_CSV, load_meta, save_meta


def main() -> None:
    if not X_POSTS_CSV.exists():
        raise SystemExit("No CSV found")
    rows_by_id: dict[str, dict[str, str]] = {}
    with X_POSTS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows_by_id[row["x_post_id"]] = row
    ordered = sorted(rows_by_id.values(), key=lambda r: r.get("created_at") or "", reverse=True)
    with X_POSTS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered)
    meta = load_meta()
    meta["row_count"] = len(ordered)
    save_meta(meta)
    print(f"Deduped to {len(ordered)} rows")


if __name__ == "__main__":
    main()
