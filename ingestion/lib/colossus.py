"""Colossus HTTP session, login, and HTML extraction."""

from __future__ import annotations

import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USER_AGENT = "founders-notes/1.0"
EPISODE_NUMBER_RE = re.compile(r"^#(\d+)")
FOUNDERS_EPISODE_TITLE_RE = re.compile(r"^#\d+[:\s]")


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
    """True only when Colossus shows the episode-level 'Coming soon.' placeholder."""
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
