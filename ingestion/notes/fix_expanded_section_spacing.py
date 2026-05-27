#!/usr/bin/env python3
"""Restore blank lines before ### headings in expanded drafts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_INGESTION / "lib"))
sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

from markdown_io import split_markdown_parts, write_frontmatter_md
import paths


def fix_spacing(body: str) -> str:
    text = re.sub(r"(## Expanded datapoints)\s*(### )", r"\1\n\n\2", body)
    text = re.sub(r"([.!?\"])(### )", r"\1\n\n\2", text)
    return text


def main() -> None:
    n = 0
    for path in sorted((paths.ROOT / "content" / "notes").glob("**/*.expanded.draft.md")):
        raw = path.read_text(encoding="utf-8")
        fm, body = split_markdown_parts(raw)
        body = body.strip()
        if fm is None:
            fm = {}
        fixed = fix_spacing(body)
        if fixed != body:
            write_frontmatter_md(path, frontmatter=fm, body=fixed)
            print(path.relative_to(paths.ROOT))
            n += 1
    print(f"Fixed {n} file(s).")


if __name__ == "__main__":
    main()
