#!/usr/bin/env python3
"""Strip timestamp-meta noise from .expanded.draft.md files (regex only, no LLM)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

from expanded_timestamp_lint import (
    clean_expanded_body,
    contains_forbidden_timestamp_meta,
    has_noisy_quote_paren,
    lint_expanded_body,
)
from markdown_io import split_markdown_parts, write_frontmatter_md
import paths


def iter_drafts(root: Path) -> list[Path]:
    return sorted(root.glob("**/*.expanded.draft.md"))


def needs_clean(body: str) -> bool:
    return bool(contains_forbidden_timestamp_meta(body)) or has_noisy_quote_paren(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List files that would change")
    parser.add_argument("--apply", action="store_true", help="Write cleaned drafts")
    parser.add_argument("--all", action="store_true", help="Process every draft, not only noisy")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        parser.error("Specify --dry-run or --apply")

    notes_root = paths.ROOT / "content" / "notes"
    drafts = iter_drafts(notes_root)
    changed = 0
    for path in drafts:
        text = path.read_text(encoding="utf-8")
        fm, body = split_markdown_parts(text)
        body = body.strip()
        if fm is None:
            fm = {}
        if not args.all and not needs_clean(body):
            continue
        cleaned = clean_expanded_body(body)
        if cleaned == body:
            continue
        rel = path.relative_to(paths.ROOT)
        remaining = lint_expanded_body(cleaned)
        if args.dry_run:
            print(f"would clean {rel}" + (f"  ({len(remaining)} lint left)" if remaining else ""))
            changed += 1
            continue
        write_frontmatter_md(path, frontmatter=fm, body=cleaned)
        print(f"cleaned {rel}" + (f"  WARN: {remaining}" if remaining else ""))
        changed += 1

    if changed == 0:
        print("No files to clean.")
    else:
        print(f"{'Would change' if args.dry_run else 'Changed'} {changed} file(s).")


if __name__ == "__main__":
    main()
