#!/usr/bin/env python3
"""Retrieval v1: search catalog/chunks.jsonl and content/ without embeddings."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
import subprocess

from paths import CHUNKS_PATH, ROOT
from search_retrieval import search_chunks_keyword

CONTENT_DIRS = [
    ROOT / "content" / "transcripts",
    ROOT / "content" / "notes",
    ROOT / "content" / "posts",
]


def search_chunks(query: str, limit: int, section_filter: str | None) -> list[tuple[float, dict]]:
    predicate = None
    if section_filter:

        def predicate(ch: dict) -> bool:
            return section_filter in ch.get("section", "")

    return search_chunks_keyword(query, limit, chunk_predicate=predicate)


def ripgrep_fallback(query: str, limit: int) -> None:
    cmd = [
        "rg",
        "-i",
        "--line-number",
        "--max-count",
        "3",
        "-m",
        str(limit),
        query,
        *[str(d) for d in CONTENT_DIRS if d.exists()],
        str(ROOT / "content" / "posts" / "_corpus"),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        if result.stdout:
            print(result.stdout.rstrip())
        if result.returncode not in (0, 1):
            print(result.stderr)
    except FileNotFoundError:
        print("ripgrep (rg) not installed — chunk index results only")


def main() -> None:
    parser = argparse.ArgumentParser(description="Search founders-notes vault")
    parser.add_argument("query", help="Search string")
    parser.add_argument("-n", "--limit", type=int, default=20)
    parser.add_argument(
        "--type",
        choices=["transcript", "notes", "post", "all"],
        default="all",
        help="Filter chunk section type",
    )
    parser.add_argument("--rg", action="store_true", help="Also run ripgrep on content/")
    args = parser.parse_args()

    section_filter = None if args.type == "all" else args.type
    hits = search_chunks(args.query, args.limit, section_filter)

    if not hits and not CHUNKS_PATH.exists():
        print("No chunks index — run: python search/build_chunks.py")
        args.rg = True
    elif not hits:
        print(f"No chunk hits for: {args.query}")
        args.rg = True

    for score, ch in hits:
        cid = ch.get("chunk_id", "")
        path = ch.get("source_path", "")
        start = ch.get("start_line", "")
        excerpt = (ch.get("excerpt") or "").replace("\n", " ")[:120]
        print(f"{path}:{start}  [{cid}]  {excerpt}…")

    if args.rg or not hits:
        print("\n# ripgrep")
        ripgrep_fallback(args.query, args.limit)


if __name__ == "__main__":
    main()
