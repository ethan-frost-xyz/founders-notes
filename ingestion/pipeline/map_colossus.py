#!/usr/bin/env python3
"""Resolve colossus_url for each catalog row."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import re

from catalog import load_catalog, save_catalog
from colossus import (
    is_founders_numbered_title,
    parse_episode_number,
    rate_limit,
    session,
)

COLOSSUS_API = "https://colossus.com/wp-json/wp/v2/podcast_episode"
MAX_FOUNDERS_EPISODE = 450


def build_founders_index(sess) -> dict[int, str]:
    """Paginate Colossus API and index numbered Founders episodes."""
    index: dict[int, str] = {}
    page = 1
    while page <= 20:
        url = f"{COLOSSUS_API}?per_page=100&page={page}"
        resp = sess.get(url, timeout=60)
        if resp.status_code != 200:
            break
        eps = resp.json()
        if not eps:
            break
        for ep in eps:
            if "topic-founders" not in ep.get("class_list", []):
                continue
            title = ep.get("title", {}).get("rendered", "")
            if not is_founders_numbered_title(title):
                continue
            num = parse_episode_number(title)
            if num is None or num > MAX_FOUNDERS_EPISODE:
                continue
            link = ep.get("link")
            if link:
                index[num] = link
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break
        page += 1
        rate_limit(0.2)
    return index


def probe_url(sess, url: str) -> bool:
    try:
        resp = sess.head(url, timeout=30, allow_redirects=True)
        return resp.status_code == 200
    except Exception:
        return False


def candidate_urls(slug: str, episode_number: int | None) -> list[str]:
    base = "https://colossus.com/episode"
    candidates = [f"{base}/{slug}/"]
    if episode_number and not slug.startswith("senra-"):
        candidates.append(f"{base}/senra-{slug}/")
        if slug.startswith(f"{episode_number}-"):
            rest = slug[len(str(episode_number)) + 1 :]
            candidates.append(f"{base}/senra-{episode_number}-{rest}/")
            candidates.append(f"{base}/senra-{rest}/")
    seen: set[str] = set()
    out = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main() -> None:
    rows = load_catalog()
    if not rows:
        raise SystemExit("Run build_catalog.py first")

    sess = session()
    print("Building Colossus Founders episode index from API ...")
    index = build_founders_index(sess)
    print(f"Indexed {len(index)} numbered Founders episodes on Colossus")

    mapped = 0
    for row in rows:
        ep_num = row.get("episode_number")
        if ep_num is not None and ep_num in index:
            row["colossus_url"] = index[ep_num]
            mapped += 1
            continue

        if row.get("colossus_url"):
            mapped += 1
            continue

        slug = row["slug"]
        for url in candidate_urls(slug, ep_num):
            if probe_url(sess, url):
                row["colossus_url"] = url
                mapped += 1
                break
            rate_limit(0.15)

    save_catalog(rows)
    numbered = [r for r in rows if r.get("episode_number") is not None]
    with_url = sum(1 for r in numbered if r.get("colossus_url"))
    print(f"Done: {with_url}/{len(numbered)} numbered episodes have colossus_url")


if __name__ == "__main__":
    main()
