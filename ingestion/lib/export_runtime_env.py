"""Print shell export lines for model slugs resolved from runtime.json.

Used by sync-and-index.sh (cron / GitHub webhook) so reindex_vault sees
OPENROUTER_EMBED_MODEL and OPENROUTER_MODEL when they live only in runtime.json.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

_RUNTIME_TO_ENV: dict[str, str] = {
    "embed_model": "OPENROUTER_EMBED_MODEL",
    "expand_model": "OPENROUTER_MODEL",
}


def runtime_settings_path() -> Path:
    raw = os.environ.get("FOUNDERS_TELEGRAM_RUNTIME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".config" / "founders-telegram" / "runtime.json"


def load_runtime_settings() -> dict:
    path = runtime_settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_model_exports() -> dict[str, str]:
    """Map env var name → slug (runtime.json overrides existing os.environ)."""
    overrides = load_runtime_settings()
    out: dict[str, str] = {}
    for runtime_key, env_key in _RUNTIME_TO_ENV.items():
        raw = overrides.get(runtime_key)
        if isinstance(raw, str) and raw.strip():
            out[env_key] = raw.strip()
            continue
        env_val = os.environ.get(env_key, "").strip()
        if env_val:
            out[env_key] = env_val
    return out


def format_shell_exports(exports: dict[str, str] | None = None) -> str:
    exports = exports if exports is not None else resolve_model_exports()
    lines = [
        f"export {env_key}={shlex.quote(slug)}" for env_key, slug in sorted(exports.items())
    ]
    return "\n".join(lines)


def main() -> int:
    text = format_shell_exports()
    if text:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
