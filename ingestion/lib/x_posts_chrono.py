"""Chronological gap-fill helpers for X post attribution."""

from __future__ import annotations

import re
from typing import Any

from catalog import catalog_by_number, load_catalog
from markdown_io import parse_frontmatter
from paths import POSTS_DIR, post_file_path
from x_posts_match import EP_MENTION_RE
from x_posts_threads import is_article_unit

_EP_DIR_RE = re.compile(r"^ep-(\d{4})")
_URL_RE = re.compile(r"https?://\S+")


def vault_max_episode() -> int:
    """Highest episode number with a .post.md file under content/posts/."""
    max_num = 0
    if not POSTS_DIR.is_dir():
        return 0
    for path in POSTS_DIR.glob("ep-*/*.post.md"):
        m = _EP_DIR_RE.match(path.parent.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num


def next_expected_episode() -> int:
    return vault_max_episode() + 1


def vault_has_post(episode_number: int) -> bool:
    by_number = catalog_by_number(load_catalog())
    row = by_number.get(episode_number)
    if not row:
        return False
    return post_file_path(row["id"], row["slug"], episode_number).exists()


def last_assigned_post_date() -> str | None:
    """published_at (YYYY-MM-DD) from the highest-numbered vault post, if any."""
    max_num = vault_max_episode()
    if max_num == 0:
        return None
    by_number = catalog_by_number(load_catalog())
    row = by_number.get(max_num)
    if not row:
        return None
    path = post_file_path(row["id"], row["slug"], max_num)
    if not path.exists():
        return None
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    pub = (fm.get("published_at") or "").strip()
    return pub[:10] if pub else None


def is_founders_recap_shape(unit: dict[str, Any]) -> bool:
    text = (unit.get("text") or "").strip()
    if not text:
        return False
    if is_article_unit(unit):
        pass
    elif len(text) < 200:
        return False

    stripped = _URL_RE.sub("", text).strip()
    if not stripped:
        return False
    words = re.findall(r"[a-zA-Z]{4,}", stripped)
    return len(words) >= 1


def try_chrono_attribution(
    unit: dict[str, Any],
    rows_by_number: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, float, str]:
    """Assign next sequential episode when recap-shaped and no explicit #N."""
    text = unit.get("text") or ""
    mentions = [int(m.group(1)) for m in EP_MENTION_RE.finditer(text)]
    next_ep = next_expected_episode()

    if mentions and mentions[0] != next_ep:
        return None, 0.0, "chrono_blocked_mention"

    if EP_MENTION_RE.search(text):
        return None, 0.0, "none"

    if not is_founders_recap_shape(unit):
        return None, 0.0, "none"

    if vault_has_post(next_ep):
        return None, 0.0, "none"

    post_date = (unit.get("created_at") or "")[:10] or None
    last_date = last_assigned_post_date()
    if post_date and last_date and post_date < last_date:
        return None, 0.0, "chrono_date_before_last"

    row = rows_by_number.get(next_ep)
    if not row:
        return None, 0.0, "none"

    return row, 0.9, "chrono_next"
