"""Shared helpers for founders-notes ingestion."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog" / "episodes.jsonl"
GAPS_PATH = ROOT / "catalog" / "gaps.md"
UNMAPPED_POSTS_PATH = ROOT / "catalog" / "unmapped-posts.jsonl"
IMPORT_REVIEW_PATH = ROOT / "catalog" / "import-review.md"
TRANSCRIPTS_DIR = ROOT / "content" / "transcripts"
NOTES_DIR = ROOT / "content" / "notes"
POSTS_DIR = ROOT / "content" / "posts"
POSTS_CORPUS_PATH = POSTS_DIR / "_corpus" / "all-posts.md"
CHUNKS_PATH = ROOT / "catalog" / "chunks.jsonl"

USER_AGENT = "founders-notes/1.0"
EPISODE_NUMBER_RE = re.compile(r"^#(\d+)")
FOUNDERS_EPISODE_TITLE_RE = re.compile(r"^#\d+[:\s]")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug_from_founders_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1]


def make_id(episode_number: int | None, slug: str) -> str:
    if episode_number is not None:
        return f"ep-{episode_number}"
    return f"ep-special-{slug}"


def folder_name(episode_id: str, slug: str) -> str:
    """e.g. ep-418 + 418-phil-knight -> ep-418-phil-knight-founder-of-nike"""
    prefix = episode_id.replace("ep-special-", "").replace("ep-", "")
    if prefix.isdigit() and slug.startswith(f"{prefix}-"):
        return f"{episode_id}-{slug[len(prefix) + 1:]}"
    return f"{episode_id}-{slug}"


def transcript_dir(episode_id: str, slug: str) -> Path:
    return TRANSCRIPTS_DIR / folder_name(episode_id, slug)


def transcript_filename(episode_id: str, slug: str) -> str:
    return f"{folder_name(episode_id, slug)}.md"


def transcript_path(episode_id: str, slug: str) -> str:
    rel = transcript_dir(episode_id, slug) / transcript_filename(episode_id, slug)
    return str(rel.relative_to(ROOT))


def episode_content_dir(episode_id: str, slug: str, base: Path) -> Path:
    return base / folder_name(episode_id, slug)


def notes_dir(episode_id: str, slug: str) -> Path:
    return episode_content_dir(episode_id, slug, NOTES_DIR)


def notes_path(episode_id: str, slug: str) -> str:
    rel = notes_dir(episode_id, slug) / "notes.md"
    return str(rel.relative_to(ROOT))


def post_dir(episode_id: str, slug: str) -> Path:
    return episode_content_dir(episode_id, slug, POSTS_DIR)


def post_path(episode_id: str, slug: str) -> str:
    rel = post_dir(episode_id, slug) / "post.md"
    return str(rel.relative_to(ROOT))


def catalog_by_number(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {r["episode_number"]: r for r in rows if r.get("episode_number") is not None}


def catalog_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in rows}


def escape_yaml_value(value: str) -> str:
    return value.replace('"', "'")


def write_frontmatter_md(
    path: Path,
    *,
    frontmatter: dict[str, Any],
    body: str,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, val in frontmatter.items():
        if val is None:
            continue
        if isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, int):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f'{key}: "{escape_yaml_value(str(val))}"')
    lines.extend(["---", "", body.strip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_notes_md(row: dict[str, Any], body: str, *, source: str = "apple_notes_import") -> Path:
    episode_id = row["id"]
    slug = row["slug"]
    path = notes_dir(episode_id, slug) / "notes.md"
    fm: dict[str, Any] = {
        "id": episode_id,
        "title": row["title"],
        "source": source,
        "imported_at": utc_now_iso(),
    }
    if row.get("episode_number") is not None:
        fm["episode_number"] = row["episode_number"]
    return write_frontmatter_md(path, frontmatter=fm, body=body)


def write_post_md(
    row: dict[str, Any],
    body: str,
    *,
    x_url: str,
    x_post_id: str,
    published_at: str | None = None,
    source: str = "x_api",
    alt_source: str | None = None,
) -> Path:
    episode_id = row["id"]
    slug = row["slug"]
    path = post_dir(episode_id, slug) / "post.md"
    fm: dict[str, Any] = {
        "id": episode_id,
        "title": row["title"],
        "x_url": x_url,
        "x_post_id": x_post_id,
        "source": source,
        "imported_at": utc_now_iso(),
    }
    if row.get("episode_number") is not None:
        fm["episode_number"] = row["episode_number"]
    if published_at:
        fm["published_at"] = published_at
    if alt_source:
        fm["alt_source"] = alt_source
    return write_frontmatter_md(path, frontmatter=fm, body=body)


def append_unmapped_post(record: dict[str, Any]) -> None:
    UNMAPPED_POSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with UNMAPPED_POSTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_unmapped_posts() -> list[dict[str, Any]]:
    if not UNMAPPED_POSTS_PATH.exists():
        return []
    rows = []
    with UNMAPPED_POSTS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_unmapped_posts(rows: list[dict[str, Any]]) -> None:
    UNMAPPED_POSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with UNMAPPED_POSTS_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def new_row(
    *,
    episode_number: int | None,
    title: str,
    slug: str,
    founders_url: str,
    published_at: str | None = None,
    colossus_url: str | None = None,
) -> dict[str, Any]:
    episode_id = make_id(episode_number, slug)
    return {
        "id": episode_id,
        "episode_number": episode_number,
        "title": title,
        "published_at": published_at,
        "founders_url": founders_url,
        "colossus_url": colossus_url,
        "slug": slug,
        "transcript_status": "pending",
        "transcript_path": None,
        "last_error": None,
        "fetched_at": None,
    }


def load_catalog() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return []
    rows = []
    with CATALOG_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_catalog(rows: list[dict[str, Any]]) -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def parse_episode_number(title: str) -> int | None:
    m = EPISODE_NUMBER_RE.match(title.strip())
    return int(m.group(1)) if m else None


def is_founders_numbered_title(title: str) -> bool:
    return bool(FOUNDERS_EPISODE_TITLE_RE.match(title.strip()))


def extract_episode_description(soup: BeautifulSoup) -> str | None:
    el = soup.select_one(".single-podcast-episode-header__description")
    if not el:
        return None
    text = el.get_text("\n", strip=True)
    return text or None


def extract_transcript_text(soup: BeautifulSoup) -> str | None:
    content = soup.select_one(".transcript__columns > .transcript__content")
    if not content:
        content = soup.select_one(".transcript__content")
    if content:
        text = content.get_text("\n", strip=True)
        return text or None
    article = soup.select_one("article.transcript")
    if article:
        text = article.get_text("\n", strip=True)
        return text or None
    return None


def is_colossus_transcript_unavailable(soup: BeautifulSoup) -> bool:
    """True only when Colossus shows the episode-level 'Coming soon.' placeholder, not in-quote text."""
    transcript = extract_transcript_text(soup)
    if transcript and len(transcript) >= 1000:
        return False
    for p in soup.find_all("p"):
        if p.get_text(strip=True) == "Coming soon.":
            return True
    return False


def extract_episode_body(html: str) -> str | None:
    """Description (above transcript on Colossus) + full transcript text."""
    soup = BeautifulSoup(html, "html.parser")
    if is_colossus_transcript_unavailable(soup):
        return None
    description = extract_episode_description(soup)
    transcript = extract_transcript_text(soup)
    if not transcript:
        return None
    parts: list[str] = []
    if description:
        parts.append(f"## Description\n\n{description}")
    parts.append(f"## Transcript\n\n{transcript}")
    return "\n\n".join(parts)


def write_transcript_md(row: dict[str, Any], body: str, fetched_at: str) -> Path:
    episode_id = row["id"]
    slug = row["slug"]
    out_dir = transcript_dir(episode_id, slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / transcript_filename(episode_id, slug)
    legacy = out_dir / "transcript.md"
    if legacy.exists() and legacy != path:
        legacy.unlink()
    lines = [
        "---",
        f"id: {episode_id}",
    ]
    if row.get("episode_number") is not None:
        lines.append(f"episode_number: {row['episode_number']}")
    lines.extend(
        [
            f'title: "{row["title"].replace(chr(34), chr(39))}"',
            f"published_at: {row.get('published_at') or 'unknown'}",
            f"colossus_url: {row.get('colossus_url') or ''}",
            f"founders_url: {row['founders_url']}",
            "source: colossus",
            f"fetched_at: {fetched_at}",
            "---",
            "",
            body.strip(),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def colossus_login(sess: requests.Session, email: str, password: str) -> None:
    login_url = "https://colossus.com/login/"
    page = sess.get(login_url, timeout=60)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")
    form = soup.find("form", class_="uwp_form")
    if not form:
        raise RuntimeError("Could not find Colossus login form")
    data: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        input_type = (inp.get("type") or "text").lower()
        if input_type in ("submit", "button", "image"):
            continue
        data[name] = inp.get("value") or ""
    data["username"] = email
    data["password"] = password
    data["uwp_login_submit"] = "Log in"
    action = form.get("action") or login_url
    if action.startswith("/"):
        action = "https://colossus.com" + action
    resp = sess.post(action, data=data, timeout=60, allow_redirects=True)
    resp.raise_for_status()
    if "isLoggedIn: true" not in resp.text and "isLoggedIn: true" not in page.text:
        # Check a gated episode page for transcript access
        test = sess.get(
            "https://colossus.com/episode/senra-333-red-bulls-billionaire-maniac-founder-dietrich-mateschitz/",
            timeout=60,
        )
        if "content-gate-obscure" in test.text and "transcript__content" not in test.text:
            raise RuntimeError("Colossus login failed — check COLOSSUS_EMAIL and COLOSSUS_PASSWORD")


def load_cookies_file(sess: requests.Session, path: Path) -> None:
    """Load Netscape/Mozilla cookies.txt into session."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _, cookie_path, secure, expires, name, value = parts[:7]
        sess.cookies.set(
            name,
            value,
            domain=domain.lstrip("."),
            path=cookie_path,
            secure=secure.upper() == "TRUE",
        )


def rate_limit(seconds: float = 1.0) -> None:
    time.sleep(seconds)
