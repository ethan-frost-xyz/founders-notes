#!/usr/bin/env python3
"""Legacy entrypoint — use sync_x_cache.py + organize_posts_from_csv.py instead."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deprecated: runs sync_x_cache.py then organize_posts_from_csv.py"
    )
    parser.add_argument("--full", action="store_true", help="Full X timeline backfill")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-pages", type=int, default=100)
    args = parser.parse_args()

    here = Path(__file__).parent
    py = sys.executable
    sync_cmd = [py, str(here / "sync_x_cache.py"), "--max-pages", str(args.max_pages)]
    if args.full:
        sync_cmd.append("--full")
    if args.dry_run:
        sync_cmd.append("--dry-run")

    print("Step 1/2: sync_x_cache.py")
    subprocess.run(sync_cmd, check=True)

    org_cmd = [py, str(here / "organize_posts_from_csv.py")]
    if args.dry_run:
        org_cmd.append("--dry-run")

    print("Step 2/2: organize_posts_from_csv.py")
    subprocess.run(org_cmd, check=True)


if __name__ == "__main__":
    main()
