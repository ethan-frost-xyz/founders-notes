"""Shared argparse helpers for ingestion CLI scripts."""

from __future__ import annotations

import argparse

from catalog import load_catalog, resolve_catalog_row


def add_episode_id_arg(
    parser: argparse.ArgumentParser,
    *,
    required: bool = False,
    help_text: str = "Episode id, e.g. ep-0200 (legacy ep-200 accepted)",
) -> None:
    parser.add_argument(
        "--id",
        dest="episode_id",
        required=required,
        metavar="EP_ID",
        help=help_text,
    )


def resolve_episode_id_arg(rows: list[dict], episode_id: str | None) -> dict | None:
    """Return catalog row for --id, or None if episode_id not set."""
    if not episode_id:
        return None
    return resolve_catalog_row(rows, episode_id)


def ensure_catalog() -> list[dict]:
    rows = load_catalog()
    if not rows:
        raise SystemExit("catalog/episodes.jsonl is empty — run build_catalog.py")
    return rows
