#!/usr/bin/env python3
"""Remove legacy transcript.md files after rename to {folder}/{folder}.md."""

import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

from paths import TRANSCRIPTS_DIR

def main() -> None:
    removed = 0
    for legacy in TRANSCRIPTS_DIR.glob("*/transcript.md"):
        legacy.unlink()
        removed += 1
    print(f"Removed {removed} legacy transcript.md files")


if __name__ == "__main__":
    main()
