#!/usr/bin/env python3
"""Remove legacy transcript.md files after rename to {folder}/{folder}.md."""

from pathlib import Path

from vault_lib import TRANSCRIPTS_DIR

def main() -> None:
    removed = 0
    for legacy in TRANSCRIPTS_DIR.glob("*/transcript.md"):
        legacy.unlink()
        removed += 1
    print(f"Removed {removed} legacy transcript.md files")


if __name__ == "__main__":
    main()
