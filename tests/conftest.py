"""Add ingestion/ to sys.path for test imports."""

from __future__ import annotations

import sys
from pathlib import Path

INGESTION = Path(__file__).resolve().parent.parent / "ingestion"
if str(INGESTION) not in sys.path:
    sys.path.insert(0, str(INGESTION))
