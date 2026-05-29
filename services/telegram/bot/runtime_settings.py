"""Telegram-adjustable settings (models, max_steps) persisted outside launchd env."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from config import AgentConfig, BotConfig

MAX_STEPS_CEILING = 20
MAX_STEPS_FLOOR = 1

RUNTIME_KEY_LIBRARIAN = "librarian_model"
RUNTIME_KEY_JANITOR = "janitor_clean_model"
RUNTIME_KEY_EXPAND = "expand_model"
RUNTIME_KEY_EMBED = "embed_model"
RUNTIME_KEY_MAX_STEPS = "max_steps"
RUNTIME_KEY_JANITOR_TEMP = "janitor_clean_temperature"

MODEL_ROLE_TO_KEY: dict[str, str] = {
    "librarian": RUNTIME_KEY_LIBRARIAN,
    "janitor": RUNTIME_KEY_JANITOR,
    "expand": RUNTIME_KEY_EXPAND,
    "embed": RUNTIME_KEY_EMBED,
}

_SEED_ENV_MAP: dict[str, str] = {
    RUNTIME_KEY_LIBRARIAN: "TELEGRAM_CHAT_MODEL",
    RUNTIME_KEY_JANITOR: "JANITOR_CLEAN_MODEL",
    RUNTIME_KEY_EXPAND: "OPENROUTER_MODEL",
    RUNTIME_KEY_EMBED: "OPENROUTER_EMBED_MODEL",
    RUNTIME_KEY_MAX_STEPS: "TELEGRAM_MAX_STEPS",
    RUNTIME_KEY_JANITOR_TEMP: "JANITOR_CLEAN_TEMPERATURE",
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


def effective_librarian_model() -> tuple[str | None, str]:
    return _resolve_str(RUNTIME_KEY_LIBRARIAN, "TELEGRAM_CHAT_MODEL")


def effective_janitor_clean_model() -> tuple[str | None, str]:
    return _resolve_str(RUNTIME_KEY_JANITOR, "JANITOR_CLEAN_MODEL")


def effective_expand_model() -> tuple[str | None, str]:
    return _resolve_str(RUNTIME_KEY_EXPAND, "OPENROUTER_MODEL")


def effective_embed_model() -> tuple[str | None, str]:
    return _resolve_str(RUNTIME_KEY_EMBED, "OPENROUTER_EMBED_MODEL")


def effective_janitor_clean_temperature() -> tuple[float, str]:
    return _resolve_float(RUNTIME_KEY_JANITOR_TEMP, "JANITOR_CLEAN_TEMPERATURE", 0.2)


def effective_max_steps(_base: AgentConfig) -> tuple[int, str]:
    overrides = load_runtime_settings()
    raw = overrides.get(RUNTIME_KEY_MAX_STEPS)
    if raw is not None:
        try:
            return int(raw), "runtime.json"
        except (TypeError, ValueError):
            pass
    env_raw = os.environ.get("TELEGRAM_MAX_STEPS", "").strip()
    if env_raw:
        return int(env_raw), "env TELEGRAM_MAX_STEPS"
    return 5, "default (5)"


def seed_runtime_from_env_if_missing() -> bool:
    """Copy legacy env model keys into runtime.json when absent. Returns True if file written."""
    data = load_runtime_settings()
    changed = False
    for runtime_key, env_key in _SEED_ENV_MAP.items():
        if runtime_key in data:
            continue
        env_val = os.environ.get(env_key, "").strip()
        if not env_val:
            continue
        if runtime_key == RUNTIME_KEY_MAX_STEPS:
            try:
                data[runtime_key] = int(env_val)
            except ValueError:
                continue
        elif runtime_key == RUNTIME_KEY_JANITOR_TEMP:
            try:
                data[runtime_key] = float(env_val)
            except ValueError:
                continue
        else:
            data[runtime_key] = env_val
        changed = True
    if changed:
        save_runtime_settings(data)
    return changed


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


def set_max_steps(value: int) -> int:
    if value < MAX_STEPS_FLOOR or value > MAX_STEPS_CEILING:
        raise ValueError(
            f"max_steps must be between {MAX_STEPS_FLOOR} and {MAX_STEPS_CEILING}, got {value}"
        )
    data = load_runtime_settings()
    data[RUNTIME_KEY_MAX_STEPS] = value
    save_runtime_settings(data)
    return value


def reset_model_role(role: str) -> None:
    role = role.strip().lower()
    key = MODEL_ROLE_TO_KEY.get(role)
    if key is None:
        raise ValueError(
            f"Unknown role {role!r}. Use: {', '.join(sorted(MODEL_ROLE_TO_KEY))}"
        )
    reset_runtime_key(key)


def apply_runtime_overrides(cfg: AgentConfig) -> AgentConfig:
    out = cfg
    model, _ = effective_librarian_model()
    if model:
        out = replace(out, model=model)

    overrides = load_runtime_settings()
    raw_steps = overrides.get(RUNTIME_KEY_MAX_STEPS)
    if raw_steps is not None:
        try:
            value = int(raw_steps)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid max_steps in runtime settings: {raw_steps!r}") from exc
        if value < MAX_STEPS_FLOOR or value > MAX_STEPS_CEILING:
            raise ValueError(
                f"max_steps in runtime settings must be {MAX_STEPS_FLOOR}–{MAX_STEPS_CEILING}, "
                f"got {value}"
            )
        out = replace(out, max_steps=value)
    else:
        steps, _ = effective_max_steps(cfg)
        out = replace(out, max_steps=steps)

    return out


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
    jan, jan_src = effective_janitor_clean_model()
    exp, exp_src = effective_expand_model()
    emb, emb_src = effective_embed_model()
    steps, steps_src = effective_max_steps(agent_cfg)
    temp, temp_src = effective_janitor_clean_temperature()

    lines = [
        "Vault bot settings",
        "",
        f"librarian_model: {lib or '(unset)'} ({lib_src})",
        f"janitor_clean_model: {jan or '(unset)'} ({jan_src})",
        f"expand_model: {exp or '(unset)'} ({exp_src})",
        f"embed_model: {emb or '(unset)'} ({emb_src})",
        f"max_steps: {steps} ({steps_src})",
        f"janitor_clean_temperature: {temp} ({temp_src})",
        "",
        "Telegram commands:",
        "/settings — tap buttons to change models (no typing)",
        "/setmodel <role> <slug> — optional typed override",
        "/resetmodel <role> — drop runtime override for one role",
        "/setsteps <n> — max tool steps (1–20)",
        "/resetsteps — clear runtime max_steps only",
        "/pull — git pull --ff-only",
        "/reindex — rebuild chunks + embeddings",
        "/sync — pull then reindex",
        "/restart — exit; launchd restarts bot",
        "",
        "Secrets stay in ~/.config/founders-telegram/env (token, API key, VAULT_ROOT).",
    ]
    if emb_src == "runtime.json" or emb:
        lines.append("After changing embed_model, run /reindex or /sync before trusting search.")
    lines.append(f"\nRuntime file: {runtime_settings_path()}")
    return "\n".join(lines)
