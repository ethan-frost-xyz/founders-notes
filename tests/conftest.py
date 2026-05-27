"""Add ingestion/ and ingestion/lib/ to sys.path for test imports."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_INGESTION = REPO / "ingestion"
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

from _bootstrap import setup_ingestion_paths  # noqa: E402

setup_ingestion_paths(REPO, include_subpackages=True)

_BOT = REPO / "services" / "telegram" / "bot"
_TOOLS = _BOT / "tools"
for entry in (str(_BOT), str(_TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)
