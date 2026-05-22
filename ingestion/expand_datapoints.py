#!/usr/bin/env python3
"""Build datapoint expansion prompt from {folder}.notes.md + {folder}.transcript.md."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from catalog import load_catalog, resolve_catalog_row
from markdown_io import read_markdown_body
from paths import ROOT, expanded_file_path, notes_file_path, transcript_dir, transcript_filename

PROMPT_TEMPLATE = """You are expanding Founders podcast study notes.

For each line under "## Raw datapoints" in NOTES:
- Find the matching moment in TRANSCRIPT using the timestamp (MM:SS or H:MM:SS).
- Quote the relevant transcript passage verbatim (1–3 sentences).
- Write one clear takeaway.

Output markdown:

## Expanded datapoints

### 12:34 — [original bullet text]
**Quote:** "…"
**Takeaway:** …

Repeat for every bullet. If timestamp is ambiguous, note uncertainty.

---

## NOTES

{notes}

---

## TRANSCRIPT

{transcript}
"""


def read_body(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Missing file: {path.relative_to(ROOT)}")
    return read_markdown_body(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Datapoint expansion prompt builder")
    parser.add_argument("--id", required=True, help="Episode id, e.g. ep-0200")
    parser.add_argument("--copy", action="store_true", help="Copy prompt to macOS clipboard")
    parser.add_argument("--write", action="store_true", help="Write expanded.md scaffold")
    args = parser.parse_args()

    rows = load_catalog()
    row = resolve_catalog_row(rows, args.id)
    slug = row["slug"]
    ep_id = row["id"]
    num = row.get("episode_number")

    npath = notes_file_path(ep_id, slug, num)
    tx_path = transcript_dir(ep_id, slug, num) / transcript_filename(ep_id, slug, num)

    notes_body = read_body(npath)
    transcript_body = read_body(tx_path)
    prompt = PROMPT_TEMPLATE.format(notes=notes_body, transcript=transcript_body)

    if args.write:
        out = expanded_file_path(ep_id, slug, num)
        out.parent.mkdir(parents=True, exist_ok=True)
        content = f"<!-- Run expand_datapoints.py --id {ep_id} and replace below -->\n\n{prompt}\n"
        out.write_text(content, encoding="utf-8")
        print(f"Wrote scaffold {out.relative_to(ROOT)}")
        return

    if args.copy:
        try:
            subprocess.run(["pbcopy"], input=prompt.encode("utf-8"), check=True)
            print("Copied prompt to clipboard")
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("pbcopy unavailable; printing to stdout", file=sys.stderr)

    print(prompt)


if __name__ == "__main__":
    main()
