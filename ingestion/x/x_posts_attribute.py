#!/usr/bin/env python3
"""Attribute pending X posts (or full CSV rebuild) into content/posts/."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse

from dotenv import load_dotenv

from paths import ROOT
from x_post_attribution import process_units
from x_posts_csv import POST_MAPPING_REVIEW, POSTS_OTHER_DIR, X_POSTS_CSV, load_csv_rows
from x_posts_pending import (
    clear_pending,
    load_pending,
    pending_units_from_records,
    remove_pending_ids,
)
from x_posts_threads import assemble_threads, filter_attributable_rows, x_user_id

load_dotenv(ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Attribute X posts into vault")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Full CSV scan (default: pending queue only)",
    )
    parser.add_argument("--clear-pending", action="store_true", help="With --rebuild, clear pending queue")
    parser.add_argument("--llm-review", action="store_true", help="Use LLM for review-band matches")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--founders-only", action="store_true")
    args = parser.parse_args()

    if args.rebuild:
        if not X_POSTS_CSV.exists():
            raise SystemExit(f"Missing {X_POSTS_CSV} — run: python x/x_posts_sync.py --backfill")
        csv_rows = load_csv_rows()
        if not csv_rows:
            raise SystemExit("CSV is empty")
        uid = x_user_id()
        attributable = filter_attributable_rows(csv_rows, uid)
        units = assemble_threads(csv_rows, user_id=uid, attributable_only=True)
        skipped = len(csv_rows) - len(attributable)
        print(
            f"Rebuild: {len(csv_rows)} CSV rows ({skipped} replies-to-others skipped) "
            f"→ {len(units)} units"
        )
        if args.clear_pending and not args.dry_run:
            clear_pending()
    else:
        pending = load_pending()
        if not pending:
            print("No pending units")
            return
        units = pending_units_from_records(pending)
        print(f"Pending: {len(units)} units")

    stats, review_records, processed_ids = process_units(
        units,
        dry_run=args.dry_run,
        founders_only=args.founders_only,
        llm_review=args.llm_review,
        merge_review=not args.rebuild,
    )

    if not args.rebuild and not args.dry_run:
        remove_pending_ids(processed_ids)

    print(
        f"Founders mapped: {stats.mapped} | Review: {stats.review} | Other: {stats.other} "
        f"| Articles skipped: {stats.skipped_articles} | Already in vault: {stats.skipped_existing}"
    )
    if review_records:
        print(f"Review queue → {POST_MAPPING_REVIEW.relative_to(ROOT)}")
    if stats.other and not args.founders_only:
        print(f"Other posts → {POSTS_OTHER_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
