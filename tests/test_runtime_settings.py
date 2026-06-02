"""Runtime settings persisted for Telegram /setmodel and /setsteps."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BOT = REPO / "services" / "telegram" / "bot"
import sys

if str(BOT) not in sys.path:
    sys.path.insert(0, str(BOT))

from config import AgentConfig, BotConfig  # noqa: E402
from runtime_settings import (  # noqa: E402
    RUNTIME_KEY_JANITOR_TEMP,
    RUNTIME_KEY_LIBRARIAN,
    RUNTIME_KEY_MAX_STEPS,
    apply_runtime_overrides,
    build_subprocess_env,
    clear_runtime_settings,
    effective_janitor_clean_temperature,
    effective_librarian_model,
    effective_stream_replies,
    set_stream_replies,
    load_runtime_settings,
    reset_runtime_key,
    runtime_settings_path,
    seed_runtime_from_env_if_missing,
    set_janitor_clean_temperature,
    set_max_steps,
    set_model,
)


@pytest.fixture
def runtime_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "runtime.json"
    monkeypatch.setenv("FOUNDERS_TELEGRAM_RUNTIME", str(path))
    clear_runtime_settings()
    yield path
    clear_runtime_settings()


def test_set_max_steps_persists(runtime_file: Path):
    set_max_steps(10)
    assert load_runtime_settings()["max_steps"] == 10
    assert runtime_settings_path() == runtime_file


def test_apply_runtime_overrides_model_and_steps(runtime_file: Path):
    _ = runtime_file
    set_model("librarian", "runtime/lib-model")
    set_max_steps(12)
    base = AgentConfig(api_key="k", model="env-model", vault_root=REPO, max_steps=5)
    merged = apply_runtime_overrides(base)
    assert merged.model == "runtime/lib-model"
    assert merged.max_steps == 12


def test_set_max_steps_rejects_out_of_range(runtime_file: Path):
    _ = runtime_file
    with pytest.raises(ValueError, match="max_steps must be"):
        set_max_steps(0)
    with pytest.raises(ValueError, match="max_steps must be"):
        set_max_steps(21)


def test_reset_runtime_key_preserves_other_keys(runtime_file: Path):
    _ = runtime_file
    set_model("librarian", "a/b")
    set_max_steps(7)
    reset_runtime_key(RUNTIME_KEY_MAX_STEPS)
    data = load_runtime_settings()
    assert RUNTIME_KEY_MAX_STEPS not in data
    assert data[RUNTIME_KEY_LIBRARIAN] == "a/b"


def test_seed_runtime_from_env_if_missing(runtime_file: Path, monkeypatch: pytest.MonkeyPatch):
    _ = runtime_file
    monkeypatch.setenv("TELEGRAM_CHAT_MODEL", "seeded/librarian")
    monkeypatch.setenv("OPENROUTER_EMBED_MODEL", "seeded/embed")
    assert seed_runtime_from_env_if_missing() is True
    data = load_runtime_settings()
    assert data["librarian_model"] == "seeded/librarian"
    assert data["embed_model"] == "seeded/embed"
    monkeypatch.setenv("TELEGRAM_CHAT_MODEL", "other/model")
    assert seed_runtime_from_env_if_missing() is False
    assert load_runtime_settings()["librarian_model"] == "seeded/librarian"


def test_build_subprocess_env_injects_models(runtime_file: Path, monkeypatch: pytest.MonkeyPatch):
    _ = runtime_file
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    set_model("expand", "expand/model")
    set_model("embed", "embed/model")
    env = build_subprocess_env(base={}, vault_root=REPO)
    assert env["OPENROUTER_MODEL"] == "expand/model"
    assert env["OPENROUTER_EMBED_MODEL"] == "embed/model"
    assert env["VAULT_ROOT"] == str(REPO)
    assert env["OPENROUTER_API_KEY"] == "test-key"


def test_set_janitor_clean_temperature_persists(runtime_file: Path):
    temp = set_janitor_clean_temperature(0.3)
    assert temp == 0.3
    assert load_runtime_settings()[RUNTIME_KEY_JANITOR_TEMP] == 0.3
    value, src = effective_janitor_clean_temperature()
    assert value == 0.3
    assert src == "runtime.json"


def test_set_janitor_clean_temperature_rejects_out_of_range(runtime_file: Path):
    _ = runtime_file
    with pytest.raises(ValueError, match="janitor_clean_temperature must be"):
        set_janitor_clean_temperature(2.5)


def test_reset_janitor_temp_preserves_other_keys(runtime_file: Path, monkeypatch: pytest.MonkeyPatch):
    _ = runtime_file
    monkeypatch.setenv("JANITOR_CLEAN_TEMPERATURE", "0.9")
    set_janitor_clean_temperature(0.4)
    reset_runtime_key(RUNTIME_KEY_JANITOR_TEMP)
    temp, src = effective_janitor_clean_temperature()
    assert temp == 0.9
    assert "env" in src


def test_effective_stream_replies_default_on(runtime_file: Path, monkeypatch: pytest.MonkeyPatch):
    _ = runtime_file
    monkeypatch.delenv("TELEGRAM_STREAM_REPLIES", raising=False)
    enabled, src = effective_stream_replies()
    assert enabled is True
    assert "default" in src


def test_set_stream_replies_persists(runtime_file: Path):
    _ = runtime_file
    set_stream_replies(False)
    enabled, src = effective_stream_replies()
    assert enabled is False
    assert src == "runtime.json"


def test_effective_librarian_model_prefers_runtime(runtime_file: Path, monkeypatch: pytest.MonkeyPatch):
    _ = runtime_file
    monkeypatch.setenv("TELEGRAM_CHAT_MODEL", "env/model")
    set_model("librarian", "runtime/model")
    model, src = effective_librarian_model()
    assert model == "runtime/model"
    assert src == "runtime.json"
