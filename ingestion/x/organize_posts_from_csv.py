#!/usr/bin/env python3
"""Deprecated: use x/x_posts_attribute.py --rebuild. Thin wrapper for backward compatibility."""

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
        "organize_posts_from_csv.py is deprecated — use: python x/x_posts_attribute.py --rebuild",
        DeprecationWarning,
        stacklevel=1,
    )
    if "--rebuild" not in sys.argv:
        sys.argv.insert(1, "--rebuild")
    from x_posts_attribute import main as attribute_main

    attribute_main()


if __name__ == "__main__":
    main()
