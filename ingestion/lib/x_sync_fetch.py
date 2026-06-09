"""Windowed X timeline fetch with since_id support."""

from __future__ import annotations

import os
from typing import Any

X_API = "https://api.twitter.com/2"
TWEET_FIELDS = (
    "created_at,conversation_id,referenced_tweets,attachments,entities,"
    "note_tweet,public_metrics,in_reply_to_user_id"
)
WINDOW_EXPANSION_SIZES = (15, 20)


def x_bearer() -> str:
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set X_BEARER_TOKEN in .env or founders-telegram env")
    return token


def x_user_id(sess: Any, bearer: str) -> str:
    uid = os.environ.get("X_USER_ID", "").strip()
    if uid:
        return uid
    username = os.environ.get("X_USERNAME", "ethanfrost").strip().lstrip("@")
    resp = sess.get(
        f"{X_API}/users/by/username/{username}",
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json().get("data")
    if not data:
        raise SystemExit(f"Could not resolve X user @{username}")
    return data["id"]


def _timeline_request(
    sess: Any,
    bearer: str,
    user_id: str,
    *,
    max_results: int,
    since_id: str | None = None,
    pagination_token: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "max_results": max_results,
        "tweet.fields": TWEET_FIELDS,
        "exclude": "retweets",
    }
    if since_id:
        params["since_id"] = since_id
    if pagination_token:
        params["pagination_token"] = pagination_token

    resp = sess.get(
        f"{X_API}/users/{user_id}/tweets",
        headers={"Authorization": f"Bearer {bearer}"},
        params=params,
        timeout=60,
    )
    if resp.status_code == 429:
        raise SystemExit("X API rate limited — try again later")
    resp.raise_for_status()
    return resp.json()


def fetch_timeline_windowed(
    sess: Any,
    bearer: str,
    user_id: str,
    *,
    existing_ids: set[str],
    since_id: str | None = None,
    initial_window: int = 10,
    max_expansions: int = 3,
) -> tuple[list[dict[str, Any]], int]:
    """Incremental weekly fetch: small first page, expand on full-new pages."""
    collected: list[dict[str, Any]] = []
    pages = 0
    next_token: str | None = None
    expansions = 0
    max_results = initial_window
    use_since_id = since_id

    while pages < max_expansions + 1:
        payload = _timeline_request(
            sess,
            bearer,
            user_id,
            max_results=max_results,
            since_id=use_since_id if pages == 0 else None,
            pagination_token=next_token,
        )
        pages += 1
        batch = payload.get("data") or []
        if not batch:
            break

        page_all_new = True
        for tweet in batch:
            tid = tweet["id"]
            if tid in existing_ids:
                return collected, pages
            collected.append(tweet)

        meta = payload.get("meta") or {}
        next_token = meta.get("next_token")
        if not next_token or not page_all_new:
            break

        expansions += 1
        if expansions > max_expansions:
            break
        if expansions - 1 < len(WINDOW_EXPANSION_SIZES):
            max_results = WINDOW_EXPANSION_SIZES[expansions - 1]
        use_since_id = None

    return collected, pages


def fetch_timeline_backfill(
    sess: Any,
    bearer: str,
    user_id: str,
    *,
    max_pages: int,
    existing_ids: set[str],
    incremental: bool,
    max_results: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    """Full timeline scan for admin backfill (legacy --full behavior)."""
    collected: list[dict[str, Any]] = []
    pages = 0
    next_token: str | None = None
    hit_known = False

    while pages < max_pages and not hit_known:
        payload = _timeline_request(
            sess,
            bearer,
            user_id,
            max_results=max_results,
            pagination_token=next_token,
        )
        batch = payload.get("data") or []
        pages += 1

        for tweet in batch:
            tid = tweet["id"]
            if tid in existing_ids:
                if incremental:
                    hit_known = True
                    break
                continue
            collected.append(tweet)

        if hit_known:
            break
        meta = payload.get("meta") or {}
        next_token = meta.get("next_token")
        if not next_token:
            break

    return collected, pages
