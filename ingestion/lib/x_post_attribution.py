"""X post attribution cascade: rules → chrono → fuzzy → optional LLM."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

from catalog import catalog_by_number, load_catalog
from markdown_io import read_markdown_body, utc_now_iso, write_frontmatter_md, write_post_md
from paths import POSTS_CORPUS_PATH, ROOT, post_file_path
from x_posts_chrono import try_chrono_attribution
from x_posts_csv import POSTS_CORPUS_OTHER, POSTS_OTHER_DIR, POST_MAPPING_REVIEW, tweet_url
from x_posts_match import AUTO_ACCEPT_SCORE, REVIEW_SCORE, match_episode
from x_posts_threads import is_article_unit

DEFAULT_ATTRIBUTION_MODEL = "deepseek/deepseek-v4-flash"
Action = Literal["founders", "review", "other", "skip_article", "skip_existing"]


@dataclass(frozen=True)
class AttributionOutcome:
    action: Action
    row: dict[str, Any] | None
    score: float
    reason: str


def write_other_post(unit: dict[str, Any], username: str) -> Any:
    POSTS_OTHER_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTS_OTHER_DIR / f"{unit['x_post_id']}.md"
    fm = {
        "x_post_id": unit["x_post_id"],
        "x_url": tweet_url(username, unit["x_post_id"]),
        "published_at": unit.get("created_at") or "unknown",
        "post_kind": unit.get("post_kind") or "tweet",
        "source": "x_csv",
        "imported_at": utc_now_iso(),
        "thread_root_id": unit.get("thread_root_id"),
    }
    body = unit.get("text") or ""
    return write_frontmatter_md(path, frontmatter=fm, body=body)


def write_founders_post(row: dict[str, Any], unit: dict[str, Any], username: str) -> Any:
    return write_post_md(
        row,
        unit.get("text") or "",
        x_url=tweet_url(username, unit["x_post_id"]),
        x_post_id=unit["x_post_id"],
        published_at=unit.get("created_at"),
        source="x_csv",
        post_kind=unit.get("post_kind") or "tweet",
    )


def load_review_records() -> list[dict[str, Any]]:
    if not POST_MAPPING_REVIEW.exists():
        return []
    rows: list[dict[str, Any]] = []
    with POST_MAPPING_REVIEW.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_review_records(records: list[dict[str, Any]], *, merge: bool = False) -> None:
    if merge:
        by_id = {r["x_post_id"]: r for r in load_review_records() if r.get("x_post_id")}
        for rec in records:
            by_id[rec["x_post_id"]] = rec
        records = list(by_id.values())
    POST_MAPPING_REVIEW.parent.mkdir(parents=True, exist_ok=True)
    with POST_MAPPING_REVIEW.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def regenerate_corpus(rows: list[dict[str, Any]], *, founders_only: bool = True) -> None:
    path = POSTS_CORPUS_PATH if founders_only else POSTS_CORPUS_OTHER
    path.parent.mkdir(parents=True, exist_ok=True)
    title = "All Founders posts" if founders_only else "Other X posts (non-Founders / unmapped)"
    parts = [f"# {title} (auto-generated)", "", f"Built at {utc_now_iso()}", ""]
    count = 0

    if founders_only:
        for row in sorted(rows, key=lambda r: r.get("episode_number") or 9999):
            p = post_file_path(row["id"], row["slug"], row.get("episode_number"))
            if not p.exists():
                continue
            body = read_markdown_body(p)
            num = row.get("episode_number")
            label = f"#{num}" if num else row["id"]
            parts.extend([f"## {label} — {row['title']}", "", body, ""])
            count += 1
    else:
        for p in sorted(POSTS_OTHER_DIR.glob("*.md")):
            body = read_markdown_body(p)
            parts.extend([f"## {p.stem}", "", body, ""])
            count += 1

    parts.insert(2, f"**Sections:** {count}")
    parts.insert(3, "")
    path.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {path.relative_to(ROOT)} ({count} sections)")


def _extract_json_episode(text: str) -> int | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    num = payload.get("episode_number")
    if num is None:
        return None
    try:
        return int(num)
    except (TypeError, ValueError):
        return None


def llm_suggest_episode(
    unit: dict[str, Any],
    *,
    last_assigned_ep: int,
    candidate_rows: list[dict[str, Any]],
    api_key: str,
    model: str,
) -> tuple[dict[str, Any] | None, float, str]:
    """Low-cost LLM pick for review-band posts."""
    if not candidate_rows:
        return None, 0.0, "llm_no_candidates"

    lines = [
        f"Last assigned episode: {last_assigned_ep}",
        "",
        "Candidate episodes:",
    ]
    for row in candidate_rows[:3]:
        num = row.get("episode_number")
        lines.append(f"- ep-{num:04d}: {row.get('title') or ''}")

    system = (
        "You map Founders podcast X recap posts to episode numbers. "
        "Reply with JSON only: {\"episode_number\": N, \"confidence\": 0.0-1.0}. "
        "Use null episode_number if unsure."
    )
    user = "\n".join(lines) + f"\n\nPost text:\n{(unit.get('text') or '')[:2000]}"

    from openrouter_client import call_openrouter

    result = call_openrouter(
        system=system,
        user=user,
        model=model,
        api_key=api_key,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    num = _extract_json_episode(result.content)
    if num is None:
        return None, 0.0, "llm_unsure"

    by_number = {r["episode_number"]: r for r in candidate_rows if r.get("episode_number")}
    row = by_number.get(num)
    if not row:
        return None, 0.0, "llm_invalid_episode"
    return row, 0.78, f"llm_suggest_{num}"


def classify_unit(
    unit: dict[str, Any],
    rows_by_number: dict[int, dict[str, Any]],
    *,
    llm_review: bool = False,
    api_key: str | None = None,
    model: str | None = None,
    last_assigned_ep: int | None = None,
) -> AttributionOutcome:
    text = unit.get("text") or ""
    post_date = unit.get("created_at")

    row, score, reason = match_episode(text, post_date, rows_by_number)

    if not (row and score >= AUTO_ACCEPT_SCORE):
        chrono_row, chrono_score, chrono_reason = try_chrono_attribution(unit, rows_by_number)
        if chrono_row and chrono_score >= AUTO_ACCEPT_SCORE:
            row, score, reason = chrono_row, chrono_score, chrono_reason

    if is_article_unit(unit) and not (row and score >= AUTO_ACCEPT_SCORE):
        return AttributionOutcome("skip_article", row, score, reason)

    if row and score >= AUTO_ACCEPT_SCORE:
        ep_id = row["id"]
        num = row.get("episode_number")
        if post_file_path(ep_id, row["slug"], num).exists():
            return AttributionOutcome("skip_existing", row, score, reason)
        return AttributionOutcome("founders", row, score, reason)

    if row and score >= REVIEW_SCORE and llm_review and api_key:
        from x_posts_chrono import next_expected_episode, vault_max_episode

        last_ep = last_assigned_ep if last_assigned_ep is not None else vault_max_episode()
        next_ep = next_expected_episode()
        candidates = [
            rows_by_number[n]
            for n in range(next_ep, next_ep + 3)
            if n in rows_by_number
        ]
        llm_row, llm_score, llm_reason = llm_suggest_episode(
            unit,
            last_assigned_ep=last_ep,
            candidate_rows=candidates,
            api_key=api_key,
            model=model or os.environ.get("X_ATTRIBUTION_MODEL", DEFAULT_ATTRIBUTION_MODEL),
        )
        if llm_row and llm_score >= AUTO_ACCEPT_SCORE:
            ep_id = llm_row["id"]
            num = llm_row.get("episode_number")
            if not post_file_path(ep_id, llm_row["slug"], num).exists():
                return AttributionOutcome("founders", llm_row, llm_score, llm_reason)

    if row and score >= REVIEW_SCORE:
        return AttributionOutcome("review", row, score, reason)

    return AttributionOutcome("other", None, score, reason)


@dataclass
class ProcessStats:
    mapped: int = 0
    review: int = 0
    other: int = 0
    skipped_articles: int = 0
    skipped_existing: int = 0


def process_units(
    units: list[dict[str, Any]],
    *,
    dry_run: bool = False,
    founders_only: bool = False,
    llm_review: bool = False,
    merge_review: bool = False,
    username: str | None = None,
) -> tuple[ProcessStats, list[dict[str, Any]], set[str]]:
    """Attribute units; returns stats, review records, and processed pending ids."""
    rows = load_catalog()
    by_number = catalog_by_number(rows)
    user = (username or os.environ.get("X_USERNAME", "ethanfrost")).strip().lstrip("@")
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip() if llm_review else ""

    stats = ProcessStats()
    review_records: list[dict[str, Any]] = []
    seen_episodes: dict[str, str] = {}
    processed_ids: set[str] = set()

    for unit in units:
        text = unit.get("text") or ""
        post_date = unit.get("created_at")
        outcome = classify_unit(
            unit,
            by_number,
            llm_review=llm_review and bool(api_key),
            api_key=api_key or None,
        )

        if outcome.action == "skip_article":
            stats.skipped_articles += 1
            processed_ids.add(unit["x_post_id"])
            continue

        if outcome.action == "skip_existing":
            stats.skipped_existing += 1
            processed_ids.add(unit["x_post_id"])
            continue

        if outcome.action == "founders" and outcome.row:
            ep_id = outcome.row["id"]
            if ep_id in seen_episodes:
                processed_ids.add(unit["x_post_id"])
                continue
            if dry_run:
                print(
                    f"[founders] {ep_id} score={outcome.score:.2f} "
                    f"reason={outcome.reason} — {text[:50]}..."
                )
            else:
                write_founders_post(outcome.row, unit, user)
                seen_episodes[ep_id] = unit["x_post_id"]
            stats.mapped += 1
            processed_ids.add(unit["x_post_id"])
        elif outcome.action == "review" and outcome.row:
            stats.review += 1
            review_records.append(
                {
                    "x_post_id": unit["x_post_id"],
                    "suggested_episode": outcome.row["id"],
                    "episode_number": outcome.row.get("episode_number"),
                    "match_score": outcome.score,
                    "match_reason": outcome.reason,
                    "text_excerpt": text[:280],
                    "published_at": post_date,
                }
            )
            if dry_run:
                print(f"[review] {outcome.row['id']} score={outcome.score:.2f}")
            processed_ids.add(unit["x_post_id"])
        else:
            stats.other += 1
            if dry_run:
                print(f"[other] {unit['x_post_id']} — {text[:40]}...")
            elif not founders_only:
                write_other_post(unit, user)
            processed_ids.add(unit["x_post_id"])

    if not dry_run:
        save_review_records(review_records, merge=merge_review)
        regenerate_corpus(rows, founders_only=True)
        if not founders_only:
            regenerate_corpus(rows, founders_only=False)

    return stats, review_records, processed_ids
