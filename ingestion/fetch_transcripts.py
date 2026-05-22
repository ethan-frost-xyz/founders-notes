#!/usr/bin/env python3
"""Fetch Colossus transcripts into content/transcripts/."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from catalog import load_catalog, resolve_catalog_row, save_catalog
from colossus import (
    colossus_login,
    extract_episode_body,
    extract_transcript_text,
    is_colossus_transcript_unavailable,
    load_cookies_file,
    rate_limit,
    session,
)
from markdown_io import utc_now_iso, write_transcript_md
from paths import ROOT, transcript_path

load_dotenv(ROOT / ".env")


def authenticate(sess) -> None:
    cookies_path = os.environ.get("COLOSSUS_COOKIES_FILE")
    if cookies_path:
        load_cookies_file(sess, Path(cookies_path))
        return

    email = os.environ.get("COLOSSUS_EMAIL")
    password = os.environ.get("COLOSSUS_PASSWORD")
    if email and password:
        colossus_login(sess, email, password)
        return

    raise SystemExit(
        "Colossus credentials required. Set COLOSSUS_EMAIL and COLOSSUS_PASSWORD in .env "
        "(see .env.example) or export COLOSSUS_COOKIES_FILE pointing to a browser cookies export."
    )


def fetch_one(sess, row: dict, *, force: bool = False) -> None:
    if row.get("transcript_status") == "complete" and not force:
        return

    url = row.get("colossus_url")
    if not url:
        row["transcript_status"] = "pending"
        row["last_error"] = "No colossus_url"
        return

    try:
        resp = sess.get(url, timeout=90)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        row["transcript_status"] = "failed"
        row["last_error"] = str(exc)[:500]
        return

    soup = BeautifulSoup(html, "html.parser")

    if is_colossus_transcript_unavailable(soup):
        row["transcript_status"] = "coming_soon"
        row["last_error"] = None
        return

    transcript_only = extract_transcript_text(soup)
    if not transcript_only or len(transcript_only) < 1000:
        if "content-gate" in html:
            row["transcript_status"] = "failed"
            row["last_error"] = "Transcript gated or incomplete — check Colossus login"
        else:
            row["transcript_status"] = "no_transcript"
            row["last_error"] = "No transcript content found on page"
        return

    body = extract_episode_body(html)
    if not body:
        row["transcript_status"] = "no_transcript"
        row["last_error"] = "Could not assemble episode body"
        return

    fetched_at = utc_now_iso()
    write_transcript_md(row, body, fetched_at)
    row["transcript_status"] = "complete"
    row["transcript_path"] = transcript_path(
        row["id"], row["slug"], row.get("episode_number")
    )
    row["fetched_at"] = fetched_at
    row["last_error"] = None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="Fetch single episode id (e.g. ep-0418)")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if complete")
    parser.add_argument("--limit", type=int, default=0, help="Max episodes to fetch (0=all)")
    args = parser.parse_args()

    rows = load_catalog()
    if not rows:
        raise SystemExit("Run build_catalog.py first")

    sess = session()
    authenticate(sess)

    targets = rows
    if args.id:
        targets = [resolve_catalog_row(rows, args.id)]

    count = 0
    for row in targets:
        if args.limit and count >= args.limit:
            break
        if row.get("transcript_status") == "complete" and not args.force and not args.id:
            continue
        if not row.get("colossus_url"):
            continue
        fetch_one(sess, row, force=args.force)
        count += 1
        if count % 10 == 0:
            save_catalog(rows)
            print(f"  fetched {count} ...")
        rate_limit(0.75)

    save_catalog(rows)
    complete = sum(1 for r in rows if r.get("transcript_status") == "complete")
    print(f"Done. {complete}/{len(rows)} episodes have transcripts on disk.")


if __name__ == "__main__":
    main()
