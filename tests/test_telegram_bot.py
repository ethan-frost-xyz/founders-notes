"""SP3 Telegram transport: auth, sessions, /web parsing (no live Bot API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("telegram")

REPO = Path(__file__).resolve().parent.parent

from auth import is_allowed  # noqa: E402
from config import AgentConfig, BotConfig, load_bot_config  # noqa: E402
from handlers import parse_web_query  # noqa: E402
from messaging import (  # noqa: E402
    TELEGRAM_MESSAGE_LIMIT,
    markdown_to_telegram_html,
    split_telegram_text,
)
from sessions import SessionStore, session_stale_warning  # noqa: E402
from web import web_search  # noqa: E402


@pytest.fixture
def bot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BotConfig:
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    agent = AgentConfig(
        api_key="test-key",
        model="test/model",
        vault_root=REPO,
    )
    sessions_dir = tmp_path / "telegram-sessions"
    sessions_dir.mkdir()
    return BotConfig(
        agent=agent,
        telegram_token="test-token",
        allowed_user_ids=frozenset({111, 222}),
        sessions_dir=sessions_dir,
    )


def test_load_bot_config_reads_janitor_clean_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runtime = tmp_path / "runtime.json"
    monkeypatch.setenv("FOUNDERS_TELEGRAM_RUNTIME", str(runtime))
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("TELEGRAM_CHAT_MODEL", "librarian/model")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "111")
    monkeypatch.setenv("JANITOR_CLEAN_MODEL", "janitor/clean-model")
    cfg = load_bot_config()
    assert cfg.agent.model == "librarian/model"
    assert cfg.janitor_clean_model == "janitor/clean-model"


def test_load_bot_config_models_from_runtime_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    runtime = tmp_path / "runtime.json"
    runtime.write_text(
        '{"librarian_model": "rt/librarian", "janitor_clean_model": "rt/janitor"}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("FOUNDERS_TELEGRAM_RUNTIME", str(runtime))
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.delenv("TELEGRAM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("JANITOR_CLEAN_MODEL", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "111")
    cfg = load_bot_config()
    assert cfg.agent.model == "rt/librarian"
    assert cfg.janitor_clean_model == "rt/janitor"


def test_is_allowed_rejects_unknown_user(bot_config: BotConfig):
    assert not is_allowed(999, bot_config)
    assert is_allowed(111, bot_config)


def test_parse_web_query():
    assert parse_web_query("/web foo bar") == "foo bar"
    assert parse_web_query("/web") is None
    assert parse_web_query("hello") is None


def test_split_telegram_text_short_unchanged():
    text = "hello"
    assert split_telegram_text(text) == [text]


def test_markdown_to_telegram_html_bold_and_escape():
    html = markdown_to_telegram_html("**inner scorecard** & [ep-0100]")
    assert "<b>inner scorecard</b>" in html
    assert "&amp;" in html
    assert "[ep-0100]" in html


def test_split_telegram_text_exact_limit():
    text = "a" * TELEGRAM_MESSAGE_LIMIT
    assert split_telegram_text(text) == [text]


def test_split_telegram_text_over_limit():
    text = "a" * (TELEGRAM_MESSAGE_LIMIT + 1)
    parts = split_telegram_text(text)
    assert len(parts) == 2
    assert all(len(p) <= TELEGRAM_MESSAGE_LIMIT for p in parts)
    assert "".join(parts) == text


def test_split_telegram_text_prefers_paragraph_break():
    para = "word " * 200
    text = (para.strip() + "\n\n") * 30
    parts = split_telegram_text(text)
    assert len(parts) > 1
    assert all(len(p) <= TELEGRAM_MESSAGE_LIMIT for p in parts)
    assert "".join(parts) == text


def test_split_telegram_text_hard_splits_long_token():
    text = "x" * 9000
    parts = split_telegram_text(text)
    assert len(parts) >= 3
    assert all(len(p) <= TELEGRAM_MESSAGE_LIMIT for p in parts)
    assert "".join(parts) == text


def test_web_search_not_configured_without_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WEB_SEARCH_API_KEY", raising=False)
    assert web_search("test")["error"] == "not configured"


def test_newchat_exports_valid_jsonl(bot_config: BotConfig):
    store = SessionStore(bot_config)
    uid = 111
    store.append_turn(uid, user_text="Rockefeller discipline", assistant_text="Answer [ep-0016].")
    path = store.new_chat(uid)
    assert path is not None
    assert path.suffix == ".jsonl"
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines[0]["record"] == "meta"
    assert any(r.get("role") == "user" for r in lines if r.get("record") == "message")
    assert store.get(uid).messages == []


def test_resume_latest_loads_export(bot_config: BotConfig):
    store = SessionStore(bot_config)
    uid = 111
    store.append_turn(uid, user_text="Question", assistant_text="Reply")
    store.new_chat(uid)
    store.append_turn(uid, user_text="Follow-up", assistant_text="Reply 2")
    path = store.export_session(uid)
    store.clear(uid)

    ok, msg = store.resume_latest(uid)
    assert ok
    assert path is not None and path.name in msg
    assert len(store.get(uid).messages) == 2


def test_session_stale_warning_when_index_newer(bot_config: BotConfig, tmp_path: Path):
    session_file = tmp_path / "old.jsonl"
    session_file.write_text('{"record":"meta"}\n', encoding="utf-8")
    old = session_file.stat().st_mtime
    chunks = bot_config.agent.vault_root / "catalog" / "chunks.jsonl"
    assert chunks.is_file()
    import os
    import time

    now = time.time()
    os.utime(chunks, (now, now))
    if session_file.stat().st_mtime >= chunks.stat().st_mtime:
        os.utime(session_file, (old - 3600, old - 3600))
    warn = session_stale_warning(session_file, bot_config.agent.vault_root)
    assert warn is not None
    assert "index" in warn.lower()


def test_run_turn_allow_web_false_uses_agent(bot_config: BotConfig):
    from agent import VaultAgent
    from types import SimpleNamespace

    agent = VaultAgent(config=bot_config.agent)
    calls: list[bool] = []

    def fake_completion(**kwargs):
        calls.append("web_search" in [t["function"]["name"] for t in kwargs.get("tools", [])])
        msg = SimpleNamespace(content="Vault answer.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    agent.run_turn("theme question", completion_fn=fake_completion, allow_web=False)
    assert calls == [False]


def test_run_turn_allow_web_true_registers_web(bot_config: BotConfig):
    from agent import VaultAgent
    from types import SimpleNamespace

    agent = VaultAgent(config=bot_config.agent)

    def fake_completion(**kwargs):
        names = [t["function"]["name"] for t in kwargs.get("tools", [])]
        assert "web_search" in names
        msg = SimpleNamespace(content="Done.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    agent.run_turn("weather", completion_fn=fake_completion, allow_web=True)


def test_resume_latest_scoped_to_user(bot_config: BotConfig):
    store = SessionStore(bot_config)
    store.append_turn(111, user_text="User 111 question", assistant_text="Reply")
    path_111 = store.export_session(111)
    assert path_111 is not None
    store.clear(111)

    store.append_turn(222, user_text="User 222 question", assistant_text="Reply")
    path_222 = store.export_session(222)
    assert path_222 is not None

    ok, msg = store.resume_latest(111)
    assert ok
    assert path_111.name in msg
    assert path_222.name not in msg


def test_resume_named_scoped_to_user(bot_config: BotConfig):
    store = SessionStore(bot_config)
    store.append_turn(111, user_text="Rockefeller discipline", assistant_text="Reply")
    path_111 = store.export_session(111)
    assert path_111 is not None

    store.append_turn(222, user_text="Rockefeller strategy", assistant_text="Reply")
    path_222 = store.export_session(222)
    assert path_222 is not None

    ok, msg = store.resume_named(111, "rockefeller")
    assert ok
    assert path_111.name in msg
    assert path_222.name not in msg
