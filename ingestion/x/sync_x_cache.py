#!/usr/bin/env python3
"""Deprecated: use x/x_posts_sync.py. Thin wrapper for backward compatibility."""

from __future__ import annotations
import sys
import warnings
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)


def main() -> None:
    warnings.warn(
        "sync_x_cache.py is deprecated — use: python x/x_posts_sync.py",
        DeprecationWarning,
        stacklevel=1,
    )
    argv = list(sys.argv)
    if "--full" in argv:
        argv[argv.index("--full")] = "--backfill"
    sys.argv = argv
    from x_posts_sync import main as sync_main

    sync_main()


if __name__ == "__main__":
    main()
