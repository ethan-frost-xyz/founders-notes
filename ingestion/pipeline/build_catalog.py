#!/usr/bin/env python3
"""Build catalog/episodes.jsonl from founderspodcast.com sitemap + RSS metadata."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from catalog import new_row, save_catalog
from colossus import parse_episode_number, session
from sitemap import iter_sitemap_episodes

RSS_URL = "https://feeds.megaphone.fm/DSLLC6297708582"


def load_rss_meta(sess) -> dict[int | str, dict]:
    """Map episode_number or lowercase title -> {title, published_at}."""
    resp = sess.get(RSS_URL, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    meta: dict[int | str, dict] = {}
    for item in root.findall(".//item"):
        title_el = item.find("title")
        if title_el is None or not title_el.text:
            continue
        title = title_el.text.strip()
        pub = item.find("pubDate")
        published_at = None
        if pub is not None and pub.text:
            try:
                published_at = parsedate_to_datetime(pub.text).strftime("%Y-%m-%d")
            except Exception:
                pass
        link_el = item.find("link")
        founders_url = link_el.text.strip() if link_el is not None and link_el.text else None

        ep_num = parse_episode_number(title)
        entry = {"title": title, "published_at": published_at, "founders_url": founders_url}
        if ep_num is not None:
            meta[ep_num] = entry
        meta[title.lower()] = entry
    return meta


def title_from_slug(slug: str) -> str:
    if slug.split("-", 1)[0].isdigit():
        rest = slug.split("-", 1)[1]
        return rest.replace("-", " ").title()
    return slug.replace("-", " ").title()


def main() -> None:
    sess = session()
    print(f"Loading RSS metadata from {RSS_URL} ...")
    rss_meta = load_rss_meta(sess)

    print("Fetching sitemap ...")
    sitemap = iter_sitemap_episodes(sess)

    rows = []
    for slug, info in sitemap.items():
        founders_url = info["founders_url"]
        ep_num = info["episode_number"]
        published_at = None

        title = title_from_slug(slug)
        if ep_num is not None and ep_num in rss_meta:
            title = rss_meta[ep_num]["title"]
            if rss_meta[ep_num].get("published_at"):
                published_at = rss_meta[ep_num]["published_at"]
            rss_url = rss_meta[ep_num].get("founders_url")
            if rss_url and "/episodes/" in rss_url:
                founders_url = rss_url
        else:
            low = title.lower()
            if low in rss_meta and rss_meta[low].get("published_at"):
                published_at = rss_meta[low]["published_at"]

        row = new_row(
            episode_number=ep_num,
            title=title,
            slug=slug,
            founders_url=founders_url,
            published_at=published_at,
        )
        rows.append(row)

    def sort_key(r: dict) -> tuple:
        n = r.get("episode_number")
        return (0 if n is not None else 1, n or 0, r.get("published_at") or "")

    rows.sort(key=sort_key)
    save_catalog(rows)
    numbered = sum(1 for r in rows if r.get("episode_number") is not None)
    print(f"Wrote {len(rows)} rows ({numbered} numbered)")


if __name__ == "__main__":
    main()
