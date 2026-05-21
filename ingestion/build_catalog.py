#!/usr/bin/env python3
"""Build catalog/episodes.jsonl from founderspodcast.com sitemap + RSS metadata."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from vault_lib import (
    new_row,
    parse_episode_number,
    save_catalog,
    session,
    slug_from_founders_url,
)

SITEMAP_URL = "https://www.founderspodcast.com/sitemap.xml"
RSS_URL = "https://feeds.megaphone.fm/DSLLC6297708582"
EPISODE_PATH_RE = re.compile(r"^/episodes/([^/]+)/?$")


def load_rss_meta(sess) -> dict[int | str, dict]:
    """Map episode_number or lowercase title -> {title, published_at}."""
    resp = sess.get(RSS_URL, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {
        "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    }
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

    print(f"Fetching {SITEMAP_URL} ...")
    resp = sess.get(SITEMAP_URL, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    rows = []
    for url_el in root.findall("sm:url", ns):
        loc = url_el.findtext("sm:loc", default="", namespaces=ns)
        lastmod = url_el.findtext("sm:lastmod", default="", namespaces=ns)
        if "/episodes/" not in loc:
            continue
        path = loc.split("founderspodcast.com", 1)[-1]
        m = EPISODE_PATH_RE.match(path)
        if not m:
            continue
        slug = m.group(1)
        founders_url = loc.strip()
        published_at = lastmod[:10] if lastmod else None

        ep_num = None
        if slug.split("-", 1)[0].isdigit():
            ep_num = int(slug.split("-", 1)[0])

        title = title_from_slug(slug)
        if ep_num is not None and ep_num in rss_meta:
            title = rss_meta[ep_num]["title"]
            if rss_meta[ep_num].get("published_at"):
                published_at = rss_meta[ep_num]["published_at"]
            if rss_meta[ep_num].get("founders_url"):
                founders_url = rss_meta[ep_num]["founders_url"]
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
