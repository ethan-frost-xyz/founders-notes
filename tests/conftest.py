"""Add ingestion/ and ingestion/lib/ to sys.path for test imports."""

from __future__ import annotations

import sys
from pathlib import Path

INGESTION = Path(__file__).resolve().parent.parent / "ingestion"
for entry in (
    INGESTION,
    INGESTION / "lib",
    INGESTION / "search",
    INGESTION / "notes",
    INGESTION / "x",
):
    s = str(entry)
    if s not in sys.path:
        sys.path.insert(0, s)
