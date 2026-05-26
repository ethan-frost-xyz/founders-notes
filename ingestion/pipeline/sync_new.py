#!/usr/bin/env python3
"""Detect new founderspodcast.com episodes and repair catalog founders_url."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse

from catalog import load_catalog, new_row, save_catalog
from colossus import session
from sitemap import iter_sitemap_episodes

HOMEPAGE_URL = "https://www.founderspodcast.com/"


def repair_founders_urls(rows: list[dict]) -> int:
    fixed = 0
    for row in rows:
        url = row.get("founders_url") or ""
        if url.rstrip("/") not in (HOMEPAGE_URL.rstrip("/"), "https://www.founderspodcast.com"):
            continue
        slug = row.get("slug")
        if slug:
            row["founders_url"] = f"https://www.founderspodcast.com/episodes/{slug}"
            fixed += 1
    return fixed


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync new episodes and repair catalog URLs")
    parser.add_argument("--repair-urls", action="store_true", help="Fix homepage founders_url rows")
    parser.add_argument("--apply", action="store_true", help="Write catalog changes (default is dry-run)")
    args = parser.parse_args()

    rows = load_catalog()
    by_slug = {r["slug"]: r for r in rows}
    sess = session()

    if args.repair_urls:
        n = repair_founders_urls(rows)
        print(f"Repaired {n} founders_url rows")
        if args.apply and n:
            save_catalog(rows)
            print("Saved catalog")

    sitemap = iter_sitemap_episodes(sess)
    new_slugs = [s for s in sitemap if s not in by_slug]
    if not new_slugs:
        print("No new episodes in sitemap")
        return

    print(f"Found {len(new_slugs)} new episode(s) in sitemap:")
    for slug in sorted(new_slugs, key=lambda s: (0 if s.split("-")[0].isdigit() else 1, s)):
        info = sitemap[slug]
        print(f"  - {slug} ({info.get('founders_url')})")

    if not args.apply:
        print("\nDry-run. Re-run with --apply to add rows, then:")
        print("  python pipeline/map_colossus.py")
        print("  python transcripts/fetch_transcripts.py --id ep-0418")
        print("  python notes/scaffold_notes.py --missing")
        print("  python pipeline/verify.py")
        return

    for slug in new_slugs:
        info = sitemap[slug]
        ep_num = info["episode_number"]
        title = slug.replace("-", " ").title()
        if ep_num is not None:
            title = f"#{ep_num} {title.split(' ', 1)[-1] if ' ' in title else title}"
        row = new_row(
            episode_number=ep_num,
            title=title,
            slug=slug,
            founders_url=info["founders_url"],
        )
        rows.append(row)

    rows.sort(
        key=lambda r: (
            0 if r.get("episode_number") is not None else 1,
            r.get("episode_number") or 0,
            r.get("published_at") or "",
        )
    )
    save_catalog(rows)
    print(
        f"Added {len(new_slugs)} rows. Next: pipeline/map_colossus.py → transcripts/fetch_transcripts.py "
        "→ notes/scaffold_notes.py --missing → pipeline/verify.py"
    )


if __name__ == "__main__":
    main()
