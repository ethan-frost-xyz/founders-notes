"""Telegram-adjustable settings (models, tuning) persisted outside launchd env."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from config import AgentConfig, BotConfig

JANITOR_TEMP_FLOOR = 0.0
JANITOR_TEMP_CEILING = 2.0

RUNTIME_KEY_LIBRARIAN = "librarian_model"
RUNTIME_KEY_RETRIEVAL = "retrieval_model"
RUNTIME_KEY_JANITOR = "janitor_clean_model"
RUNTIME_KEY_EXPAND = "expand_model"
RUNTIME_KEY_EMBED = "embed_model"
RUNTIME_KEY_JANITOR_TEMP = "janitor_clean_temperature"
RUNTIME_KEY_STREAM_REPLIES = "stream_replies"

# Shown after embed slug changes (/setmodel, Settings) — matches build_embeddings self-heal.
EMBED_REINDEX_REMINDER = (
    "Run /reindex or /sync when idle before trusting search — "
    "stale vectors rebuild automatically."
)
EMBED_SETTINGS_REMINDER = (
    "After changing embed: Ops → Reindex or Sync when idle "
    "(stale vectors rebuild automatically)."
)

MODEL_ROLE_TO_KEY: dict[str, str] = {
    "librarian": RUNTIME_KEY_LIBRARIAN,
    "retrieval": RUNTIME_KEY_RETRIEVAL,
    "janitor": RUNTIME_KEY_JANITOR,
    "expand": RUNTIME_KEY_EXPAND,
    "embed": RUNTIME_KEY_EMBED,
}

def runtime_settings_path() -> Path:
    raw = os.environ.get("FOUNDERS_TELEGRAM_RUNTIME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".config" / "founders-telegram" / "runtime.json"


def load_runtime_settings() -> dict[str, Any]:
    path = runtime_settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_runtime_settings(data: dict[str, Any]) -> Path:
    path = runtime_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def clear_runtime_settings() -> None:
    path = runtime_settings_path()
    if path.is_file():
        path.unlink()


def reset_runtime_key(key: str) -> None:
    data = load_runtime_settings()
    if key in data:
        del data[key]
        if data:
            save_runtime_settings(data)
        else:
            clear_runtime_settings()


def _resolve_str(runtime_key: str, env_key: str) -> tuple[str | None, str]:
    overrides = load_runtime_settings()
    raw = overrides.get(runtime_key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), "runtime.json"
    env_val = os.environ.get(env_key, "").strip()
    if env_val:
        return env_val, f"env {env_key}"
    return None, "unset"


def _resolve_float(runtime_key: str, env_key: str, default: float) -> tuple[float, str]:
    overrides = load_runtime_settings()
    raw = overrides.get(runtime_key)
    if raw is not None:
        try:
            return float(raw), "runtime.json"
        except (TypeError, ValueError):
            pass
    env_raw = os.environ.get(env_key, "").strip()
    if env_raw:
        try:
            return float(env_raw), f"env {env_key}"
        except ValueError:
            pass
    return default, f"default ({default})"


def _parse_bool_value(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and raw in (0, 1):
        return bool(raw)
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off"):
            return False
    return None


def _resolve_bool(runtime_key: str, env_key: str, default: bool) -> tuple[bool, str]:
    overrides = load_runtime_settings()
    parsed = _parse_bool_value(overrides.get(runtime_key))
    if parsed is not None:
        return parsed, "runtime.json"
    env_raw = os.environ.get(env_key, "").strip()
    if env_raw:
        parsed = _parse_bool_value(env_raw)
        if parsed is not None:
            return parsed, f"env {env_key}"
    return default, f"default ({str(default).lower()})"


def effective_librarian_model() -> tuple[str | None, str]:
    return _resolve_str(RUNTIME_KEY_LIBRARIAN, "TELEGRAM_CHAT_MODEL")


def effective_retrieval_model() -> tuple[str | None, str]:
    """Query expand + rerank in the Librarian orchestrator (not synthesis)."""
    slug, src = _resolve_str(RUNTIME_KEY_RETRIEVAL, "TELEGRAM_RETRIEVAL_MODEL")
    if slug:
        return slug, src
    lib, lib_src = effective_librarian_model()
    if lib:
        return lib, f"fallback ({lib_src})"
    return None, "unset"


def effective_janitor_clean_model() -> tuple[str | None, str]:
    return _resolve_str(RUNTIME_KEY_JANITOR, "JANITOR_CLEAN_MODEL")


def effective_expand_model() -> tuple[str | None, str]:
    return _resolve_str(RUNTIME_KEY_EXPAND, "OPENROUTER_MODEL")


def effective_embed_model() -> tuple[str | None, str]:
    return _resolve_str(RUNTIME_KEY_EMBED, "OPENROUTER_EMBED_MODEL")


def effective_janitor_clean_temperature() -> tuple[float, str]:
    return _resolve_float(RUNTIME_KEY_JANITOR_TEMP, "JANITOR_CLEAN_TEMPERATURE", 0.2)


def effective_stream_replies() -> tuple[bool, str]:
    return _resolve_bool(RUNTIME_KEY_STREAM_REPLIES, "TELEGRAM_STREAM_REPLIES", False)


def set_model(role: str, slug: str) -> str:
    role = role.strip().lower()
    key = MODEL_ROLE_TO_KEY.get(role)
    if key is None:
        raise ValueError(
            f"Unknown role {role!r}. Use: {', '.join(sorted(MODEL_ROLE_TO_KEY))}"
        )
    slug = slug.strip()
    if not slug:
        raise ValueError("Model slug cannot be empty")
    data = load_runtime_settings()
    data[key] = slug
    save_runtime_settings(data)
    return slug


def set_stream_replies(enabled: bool) -> bool:
    data = load_runtime_settings()
    data[RUNTIME_KEY_STREAM_REPLIES] = bool(enabled)
    save_runtime_settings(data)
    return bool(data[RUNTIME_KEY_STREAM_REPLIES])


def set_janitor_clean_temperature(value: float) -> float:
    if value < JANITOR_TEMP_FLOOR or value > JANITOR_TEMP_CEILING:
        raise ValueError(
            f"janitor_clean_temperature must be between {JANITOR_TEMP_FLOOR} and "
            f"{JANITOR_TEMP_CEILING}, got {value}"
        )
    data = load_runtime_settings()
    data[RUNTIME_KEY_JANITOR_TEMP] = round(value, 2)
    save_runtime_settings(data)
    return float(data[RUNTIME_KEY_JANITOR_TEMP])


def reset_model_role(role: str) -> None:
    role = role.strip().lower()
    key = MODEL_ROLE_TO_KEY.get(role)
    if key is None:
        raise ValueError(
            f"Unknown role {role!r}. Use: {', '.join(sorted(MODEL_ROLE_TO_KEY))}"
        )
    reset_runtime_key(key)


def apply_runtime_overrides(cfg: AgentConfig) -> AgentConfig:
    model, _ = effective_librarian_model()
    if model:
        return replace(cfg, model=model)
    return cfg


def apply_runtime_to_bot_config(cfg: BotConfig) -> BotConfig:
    janitor_model, _ = effective_janitor_clean_model()
    return replace(cfg, janitor_clean_model=janitor_model)


def build_subprocess_env(
    base: dict[str, str] | None = None,
    *,
    vault_root: Path | None = None,
) -> dict[str, str]:
    env = dict(base if base is not None else os.environ)
    if vault_root is not None:
        env["VAULT_ROOT"] = str(vault_root)
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if api_key:
        env["OPENROUTER_API_KEY"] = api_key
    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip()
    if base_url:
        env["OPENROUTER_BASE_URL"] = base_url.rstrip("/")
    expand, _ = effective_expand_model()
    if expand:
        env["OPENROUTER_MODEL"] = expand
    embed, _ = effective_embed_model()
    if embed:
        env["OPENROUTER_EMBED_MODEL"] = embed
    return env


def sync_embed_to_os_environ() -> str | None:
    embed, _ = effective_embed_model()
    if embed:
        os.environ["OPENROUTER_EMBED_MODEL"] = embed
        return embed
    os.environ.pop("OPENROUTER_EMBED_MODEL", None)
    return None


def format_settings_summary(agent_cfg: AgentConfig, bot_cfg: BotConfig) -> str:
    lib, lib_src = effective_librarian_model()
    ret, ret_src = effective_retrieval_model()
    jan, jan_src = effective_janitor_clean_model()
    exp, exp_src = effective_expand_model()
    emb, emb_src = effective_embed_model()
    temp, temp_src = effective_janitor_clean_temperature()
    stream, stream_src = effective_stream_replies()

    lines = [
        "Vault bot settings",
        "",
        f"librarian_model: {lib or '(unset)'} ({lib_src})",
        f"retrieval_model: {ret or '(unset)'} ({ret_src})",
        f"janitor_clean_model: {jan or '(unset)'} ({jan_src})",
        f"expand_model: {exp or '(unset)'} ({exp_src})",
        f"embed_model: {emb or '(unset)'} ({emb_src})",
        f"janitor_clean_temperature: {temp} ({temp_src})",
        f"stream_replies: {str(stream).lower()} ({stream_src})",
    ]
    if emb_src == "runtime.json" or emb:
        lines.append("")
        lines.append(EMBED_SETTINGS_REMINDER)
    return "\n".join(lines)
