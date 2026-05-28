"""Deploy artifact smoke tests (no python-telegram-bot required)."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEPLOY = REPO / "services" / "telegram" / "deploy"


def test_deploy_scripts_exist_and_are_executable():
    for name in ("sync-and-index.sh", "run-bot.sh", "install-cron.sh"):
        path = DEPLOY / name
        assert path.is_file(), name
        assert path.stat().st_mode & 0o111, f"{name} should be executable"


def test_install_cron_print_includes_sync_script():
    proc = subprocess.run(
        [str(DEPLOY / "install-cron.sh"), "--print"],
        capture_output=True,
        text=True,
        env={"VAULT_ROOT": str(REPO), "HOME": str(Path.home())},
    )
    assert proc.returncode == 0
    assert "sync-and-index.sh" in proc.stdout
    assert "0 4 * * *" in proc.stdout
    assert "founders-telegram-sync-and-index" in proc.stdout
    assert "Installed crontab" not in proc.stdout


def test_env_example_lists_required_keys():
    text = (DEPLOY / "env.example").read_text(encoding="utf-8")
    for key in (
        "VAULT_ROOT",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_ALLOWED_USER_IDS",
        "OPENROUTER_API_KEY",
        "TELEGRAM_CHAT_MODEL",
        "OPENROUTER_EMBED_MODEL",
        "JANITOR_CLEAN_MODEL",
        "OPENROUTER_MODEL",
    ):
        assert key in text


def test_launchd_plist_has_label():
    plist = (DEPLOY / "com.founders.telegram.bot.plist").read_text(encoding="utf-8")
    assert "com.founders.telegram.bot" in plist
    assert "run-bot.sh" in plist
