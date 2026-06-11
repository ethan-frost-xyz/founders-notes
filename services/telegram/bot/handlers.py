"""Telegram command and message handlers (thin transport over VaultAgent)."""

from __future__ import annotations

import asyncio
import os
from functools import partial

from context import (
    config as _config,
    reject_unauthorized as _reject_unauthorized,
    reload_bot_config as _reload_bot_config,
    sessions as _sessions,
)
from index_status import vault_stats_text
from librarian_turn import run_librarian_turn
from messaging import reply_text_chunked
from telegram import Update
from telegram.ext import ContextTypes


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    await reply_text_chunked(
        update.message, vault_stats_text(_config(context).agent.vault_root)
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    uid = update.effective_user.id
    _sessions(context).clear(uid)
    await update.message.reply_text("Session cleared.")


async def cmd_newchat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    uid = update.effective_user.id
    path = _sessions(context).new_chat(uid)
    if path:
        await update.message.reply_text(f"Exported {path.name} and started a new chat.")
    else:
        await update.message.reply_text("No messages to export. Started a fresh chat.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    uid = update.effective_user.id
    args = context.args or []
    if args:
        ok, msg = _sessions(context).resume_named(uid, " ".join(args))
    else:
        ok, msg = _sessions(context).resume_latest(uid)
    await reply_text_chunked(update.message, msg)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    from settings_handlers import send_settings_panel

    await send_settings_panel(update, context)


async def cmd_setcleantemp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    args = context.args or []
    if len(args) != 1:
        await update.message.reply_text("Usage: /setcleantemp <n>  (0.0–2.0)")
        return
    from runtime_settings import (
        JANITOR_TEMP_CEILING,
        JANITOR_TEMP_FLOOR,
        effective_janitor_clean_temperature,
        set_janitor_clean_temperature,
    )

    try:
        value = float(args[0].strip())
        temp = set_janitor_clean_temperature(value)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    _, src = effective_janitor_clean_temperature()
    await update.message.reply_text(
        f"janitor_clean_temperature set to {temp} (saved; range "
        f"{JANITOR_TEMP_FLOOR}–{JANITOR_TEMP_CEILING}). Active now ({src})."
    )


async def cmd_resetcleantemp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    from runtime_settings import (
        RUNTIME_KEY_JANITOR_TEMP,
        effective_janitor_clean_temperature,
        reset_runtime_key,
    )

    reset_runtime_key(RUNTIME_KEY_JANITOR_TEMP)
    temp, src = effective_janitor_clean_temperature()
    await update.message.reply_text(
        f"Runtime janitor_clean_temperature cleared. Now using {temp} ({src}). "
        "Model keys unchanged."
    )


async def cmd_setmodel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /setmodel <role> <slug>\nRoles: librarian, retrieval, janitor, expand, embed"
        )
        return
    role = args[0]
    slug = " ".join(args[1:]).strip()
    from runtime_settings import (
        EMBED_REINDEX_REMINDER,
        MODEL_ROLE_TO_KEY,
        set_model,
        sync_embed_to_os_environ,
    )

    try:
        set_model(role, slug)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    if role.strip().lower() == "embed":
        sync_embed_to_os_environ()
    bot_cfg, agent = _reload_bot_config(context)
    key = MODEL_ROLE_TO_KEY[role.strip().lower()]
    extra = ""
    if key == "embed_model":
        extra = f"\n{EMBED_REINDEX_REMINDER}"
    await update.message.reply_text(
        f"Set {role} model to {slug!r} (saved). Active on this process.{extra}\n"
        f"Librarian: {agent.config.model}\n"
        f"Janitor clean: {bot_cfg.janitor_clean_model or '(unset)'}"
    )


async def cmd_resetmodel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    args = context.args or []
    if len(args) != 1:
        await update.message.reply_text(
            "Usage: /resetmodel <role>\nRoles: librarian, retrieval, janitor, expand, embed"
        )
        return
    from runtime_settings import reset_model_role, sync_embed_to_os_environ

    try:
        reset_model_role(args[0])
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    if args[0].strip().lower() == "embed":
        sync_embed_to_os_environ()
    bot_cfg, _ = _reload_bot_config(context)
    await update.message.reply_text(
        f"Runtime override cleared for {args[0]!r}. "
        f"Falls back to env if set.\nJanitor: {bot_cfg.janitor_clean_model or '(unset)'}"
    )


async def cmd_pull(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    from ops_runner import run_git_pull
    from ops_telegram import run_ops_job

    await run_ops_job(
        update.message,
        context.application.bot_data,
        _config(context).agent.vault_root,
        label="git pull",
        fn=run_git_pull,
        started="Pull started.",
    )


async def cmd_reindex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    from ops_runner import run_reindex_op
    from ops_telegram import run_ops_job

    await run_ops_job(
        update.message,
        context.application.bot_data,
        _config(context).agent.vault_root,
        label="reindex",
        fn=run_reindex_op,
        started="Reindex started.",
    )


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    from ops_runner import run_sync
    from ops_telegram import run_ops_job

    await run_ops_job(
        update.message,
        context.application.bot_data,
        _config(context).agent.vault_root,
        label="sync (pull + reindex)",
        fn=run_sync,
        started="Sync started.",
    )


async def cmd_push(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    from ops_runner import run_vault_push_op
    from ops_telegram import run_ops_job

    vault_root = _config(context).agent.vault_root
    await run_ops_job(
        update.message,
        context.application.bot_data,
        vault_root,
        label="vault push",
        fn=partial(run_vault_push_op, message="vault: push from Mac mini"),
        started="Push started (pull, commit, push)…",
    )


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    await update.message.reply_text(
        "Restarting in 2 seconds. launchd should start a fresh bot process. "
        "If nothing responds after ~30s, run services/telegram/deploy/restart-bot.sh on the Mac mini."
    )

    def _exit_process() -> None:
        os._exit(0)

    asyncio.get_running_loop().call_later(2.0, _exit_process)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    if not update.message or not update.message.text:
        return
    from settings_handlers import try_handle_awaiting_model_slug

    if await try_handle_awaiting_model_slug(update, context):
        return
    janitor = context.application.bot_data.get("janitor")
    if janitor is not None and janitor.is_active(update.effective_user.id):
        from janitor_handlers import on_janitor_text

        if await on_janitor_text(update, context):
            return
    text = update.message.text.strip()
    if text.startswith("/"):
        return
    await run_librarian_turn(update, context, text)
