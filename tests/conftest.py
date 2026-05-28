"""Add ingestion/ and ingestion/lib/ to sys.path for test imports."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

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


@pytest.fixture(autouse=True)
def _restore_openrouter_embed_env():
    """Runtime-settings tests may call sync_embed_to_os_environ(); restore after each test."""
    saved = os.environ.get("OPENROUTER_EMBED_MODEL")
    yield
    if saved is None:
        os.environ.pop("OPENROUTER_EMBED_MODEL", None)
    else:
        os.environ["OPENROUTER_EMBED_MODEL"] = saved
