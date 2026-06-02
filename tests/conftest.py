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

VAULT_SEARCH_CHUNKS = REPO / "tests" / "fixtures" / "vault_search_chunks.jsonl"


@pytest.fixture
def agent_config(monkeypatch: pytest.MonkeyPatch):
    """Vault agent config with a small chunk index (CI-fast)."""
    from catalog import clear_jsonl_cache
    from config import AgentConfig

    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    clear_jsonl_cache()
    import paths as vault_paths

    monkeypatch.setattr(vault_paths, "CHUNKS_PATH", VAULT_SEARCH_CHUNKS)
    return AgentConfig(
        api_key="test-key",
        model="test/model",
        vault_root=REPO,
    )


@pytest.fixture(autouse=True)
def _vault_search_chunks_for_vault_tests(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patch CHUNKS_PATH for vault integration modules unless opted out."""
    mod = request.module
    if mod is None or not Path(mod.__file__).name.startswith("test_vault_"):
        return
    if request.node.name == "test_chunk_count_after_listen_filter":
        return

    from catalog import clear_jsonl_cache

    clear_jsonl_cache()
    import paths as vault_paths

    monkeypatch.setattr(vault_paths, "CHUNKS_PATH", VAULT_SEARCH_CHUNKS)


@pytest.fixture(autouse=True)
def _clear_jsonl_cache_between_tests() -> None:
    from catalog import clear_jsonl_cache

    clear_jsonl_cache()
    yield
    clear_jsonl_cache()


@pytest.fixture(autouse=True)
def _restore_openrouter_embed_env():
    """Runtime-settings tests may call sync_embed_to_os_environ(); restore after each test."""
    saved = os.environ.get("OPENROUTER_EMBED_MODEL")
    yield
    if saved is None:
        os.environ.pop("OPENROUTER_EMBED_MODEL", None)
    else:
        os.environ["OPENROUTER_EMBED_MODEL"] = saved
