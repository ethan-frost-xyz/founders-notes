"""Deploy artifact smoke tests (no python-telegram-bot required)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DEPLOY = REPO / "services" / "telegram" / "deploy"

_DEPLOY_ARTIFACTS: list[tuple[str, bool, str | None]] = [
    ("sync-and-index.sh", True, None),
    ("run-bot.sh", True, None),
    ("install-cron.sh", True, None),
    ("run-webhook.sh", True, None),
    ("install-webhook.sh", True, None),
    ("github_webhook_server.py", False, None),
    ("com.founders.telegram.bot.plist", False, "com.founders.telegram.bot"),
    ("env.example", False, "VAULT_ROOT"),
]


@pytest.mark.parametrize(
    ("name", "executable", "content_contains"),
    _DEPLOY_ARTIFACTS,
    ids=[a[0] for a in _DEPLOY_ARTIFACTS],
)
def test_deploy_artifact(name: str, executable: bool, content_contains: str | None) -> None:
    path = DEPLOY / name
    assert path.is_file(), name
    if executable:
        assert path.stat().st_mode & 0o111, f"{name} should be executable"
    if content_contains:
        text = path.read_text(encoding="utf-8")
        assert content_contains in text
        if name == "env.example":
            for key in (
                "TELEGRAM_BOT_TOKEN",
                "TELEGRAM_ALLOWED_USER_IDS",
                "OPENROUTER_API_KEY",
            ):
                assert key in text
            assert "runtime.json" in text
            assert "# TELEGRAM_CHAT_MODEL=" in text or "TELEGRAM_CHAT_MODEL" in text
        if name == "com.founders.telegram.bot.plist":
            assert "run-bot.sh" in text


def test_install_webhook_print_documents_plist_label():
    proc = subprocess.run(
        [str(DEPLOY / "install-webhook.sh"), "--print"],
        capture_output=True,
        text=True,
        env={"VAULT_ROOT": str(REPO), "HOME": str(Path.home())},
    )
    assert proc.returncode == 0
    assert "com.founders.telegram.webhook" in proc.stdout
    assert "github_webhook_server.py" in (DEPLOY / "run-webhook.sh").read_text(encoding="utf-8")


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
