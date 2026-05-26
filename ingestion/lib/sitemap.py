"""Founders Podcast sitemap parsing."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

SITEMAP_URL = "https://www.founderspodcast.com/sitemap.xml"
EPISODE_PATH_RE = re.compile(r"^/episodes/([^/]+)/?$")


def iter_sitemap_episodes(sess) -> dict[str, dict]:
    """Return slug -> {slug, founders_url, episode_number}."""
    resp = sess.get(SITEMAP_URL, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    found: dict[str, dict] = {}
    for url_el in root.findall("sm:url", ns):
        loc = url_el.findtext("sm:loc", default="", namespaces=ns)
        if "/episodes/" not in loc:
            continue
        path = loc.split("founderspodcast.com", 1)[-1]
        m = EPISODE_PATH_RE.match(path)
        if not m:
            continue
        slug = m.group(1)
        ep_num = int(slug.split("-", 1)[0]) if slug.split("-", 1)[0].isdigit() else None
        found[slug] = {"slug": slug, "founders_url": loc.strip(), "episode_number": ep_num}
    return found
