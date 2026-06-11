"""Tap-to-change models from /settings (inline keyboards)."""

from __future__ import annotations

from functools import partial
from typing import Any

from callbacks import (
    CALLBACK_SET_OPS,
    CALLBACK_SET_STREAM,
    CALLBACK_SET_TEMP,
)
from context import (
    config as _config,
    reject_unauthorized as _reject_unauthorized,
    reload_bot_config as _reload_bot_config,
)
from model_presets import MODEL_PRESETS, ROLE_LABELS
from runtime_settings import (
    MODEL_ROLE_TO_KEY,
    EMBED_REINDEX_REMINDER,
    effective_stream_replies,
    format_settings_summary,
    load_runtime_settings,
    reset_model_role,
    set_model,
    set_stream_replies,
    sync_embed_to_os_environ,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from ui_keyboards import (
    CALLBACK_SETTINGS_MENU,
    back_to_settings_markup,
    back_to_settings_row,
)

AWAITING_MODEL_SLUG_KEY = "awaiting_model_slug"


def _stream_replies_button_label() -> str:
    enabled, _ = effective_stream_replies()
    return f"Stream replies: {'ON' if enabled else 'OFF'}"


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Librarian", callback_data="set:r:librarian"),
                InlineKeyboardButton("Janitor", callback_data="set:r:janitor"),
            ],
            [
                InlineKeyboardButton("Retrieval", callback_data="set:r:retrieval"),
                InlineKeyboardButton("Expand", callback_data="set:r:expand"),
            ],
            [InlineKeyboardButton("Embed", callback_data="set:r:embed")],
            [InlineKeyboardButton("Janitor temp", callback_data=CALLBACK_SET_TEMP)],
            [InlineKeyboardButton(_stream_replies_button_label(), callback_data=CALLBACK_SET_STREAM)],
            [InlineKeyboardButton("Ops", callback_data=CALLBACK_SET_OPS)],
        ]
    )


def _ops_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Sync", callback_data="set:op:sync"),
                InlineKeyboardButton("Pull", callback_data="set:op:pull"),
            ],
            [
                InlineKeyboardButton("Push", callback_data="set:op:push"),
                InlineKeyboardButton("Reindex", callback_data="set:op:reindex"),
            ],
            [
                InlineKeyboardButton("Restart", callback_data="set:op:restart"),
            ],
            back_to_settings_row(),
        ]
    )


def _role_preset_keyboard(role: str) -> InlineKeyboardMarkup:
    presets = MODEL_PRESETS.get(role, [])
    rows: list[list[InlineKeyboardButton]] = []
    for idx, (label, _slug) in enumerate(presets):
        rows.append(
            [InlineKeyboardButton(label, callback_data=f"set:p:{role}:{idx}")]
        )
    rows.append(
        [
            InlineKeyboardButton("Reset override", callback_data=f"set:x:{role}"),
            InlineKeyboardButton("Type custom slug…", callback_data=f"set:c:{role}"),
        ]
    )
    rows.append(back_to_settings_row())
    return InlineKeyboardMarkup(rows)


def _janitor_temp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("0", callback_data="set:t:0"),
                InlineKeyboardButton("0.1", callback_data="set:t:0.1"),
                InlineKeyboardButton("0.2", callback_data="set:t:0.2"),
            ],
            [
                InlineKeyboardButton("0.3", callback_data="set:t:0.3"),
                InlineKeyboardButton("0.5", callback_data="set:t:0.5"),
                InlineKeyboardButton("1.0", callback_data="set:t:1"),
            ],
            back_to_settings_row(),
        ]
    )


def _current_slug(role: str) -> str | None:
    key = MODEL_ROLE_TO_KEY.get(role)
    if not key:
        return None
    raw = load_runtime_settings().get(key)
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


async def send_settings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_cfg = _config(context)
    text = format_settings_summary(bot_cfg.agent, bot_cfg)
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if message is None:
        return
    await message.reply_text(text, reply_markup=settings_keyboard())


def _apply_model(role: str, slug: str) -> tuple[str, str]:
    set_model(role, slug)
    if role == "embed":
        sync_embed_to_os_environ()
    extra = ""
    if role == "embed":
        extra = f" {EMBED_REINDEX_REMINDER}"
    return slug, extra


async def on_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if await _reject_unauthorized(update, _config(context)):
        await query.answer("Unauthorized.", show_alert=True)
        return

    data = (query.data or "").strip()
    await query.answer()

    bot_cfg = _config(context)

    if data == CALLBACK_SETTINGS_MENU:
        context.user_data.pop(AWAITING_MODEL_SLUG_KEY, None)
        text = format_settings_summary(bot_cfg.agent, bot_cfg)
        await query.edit_message_text(text, reply_markup=settings_keyboard())
        return

    if data == CALLBACK_SET_STREAM:
        enabled, _ = effective_stream_replies()
        set_stream_replies(not enabled)
        text = format_settings_summary(bot_cfg.agent, bot_cfg)
        state = "on" if not enabled else "off"
        text += f"\n\nStream replies turned {state}."
        await query.edit_message_text(text, reply_markup=settings_keyboard())
        return

    if data == CALLBACK_SET_OPS:
        await query.edit_message_text("Vault ops:", reply_markup=_ops_keyboard())
        return

    if data.startswith("set:op:"):
        from ops_runner import run_git_pull, run_reindex_op, run_sync, run_vault_push_op
        from ops_telegram import run_ops_job_edit, run_ops_restart

        vault_root = bot_cfg.agent.vault_root
        op = data.split(":", 2)[2]
        msg = query.message
        if msg is None:
            return
        if op == "restart":
            await run_ops_restart(msg)
            return
        ops_map = {
            "sync": (
                "sync (pull + reindex)",
                run_sync,
                "Sync running… (may take a few minutes)",
            ),
            "pull": ("git pull", run_git_pull, "Pull running…"),
            "reindex": (
                "reindex",
                run_reindex_op,
                "Reindex running… (may take a few minutes)",
            ),
            "push": (
                "vault push",
                partial(run_vault_push_op, message="vault: push from Mac mini"),
                "Push running… (pull, commit, push)",
            ),
        }
        if op not in ops_map:
            return
        label, fn, running = ops_map[op]
        await run_ops_job_edit(
            msg,
            context.application.bot_data,
            vault_root,
            label=label,
            fn=fn,
            running_text=running,
        )
        return

    if data == CALLBACK_SET_TEMP:
        await query.edit_message_text(
            "Choose Janitor clean temperature (LLM paste normalization):",
            reply_markup=_janitor_temp_keyboard(),
        )
        return

    if data.startswith("set:t:"):
        from runtime_settings import set_janitor_clean_temperature

        try:
            value = float(data.split(":", 2)[2])
            temp = set_janitor_clean_temperature(value)
        except (ValueError, IndexError) as exc:
            await query.edit_message_text(str(exc), reply_markup=_janitor_temp_keyboard())
            return
        text = format_settings_summary(bot_cfg.agent, bot_cfg)
        text += f"\n\njanitor_clean_temperature set to {temp}."
        await query.edit_message_text(text, reply_markup=settings_keyboard())
        return

    if data.startswith("set:r:"):
        role = data.split(":", 2)[2]
        if role not in MODEL_ROLE_TO_KEY:
            return
        current = _current_slug(role)
        title = ROLE_LABELS.get(role, role)
        hint = f"Current: {current}" if current else "Current: (unset)"
        await query.edit_message_text(
            f"{title}\n{hint}\n\nPick a model:",
            reply_markup=_role_preset_keyboard(role),
        )
        return

    if data.startswith("set:p:"):
        parts = data.split(":")
        if len(parts) != 4:
            return
        role, idx_s = parts[2], parts[3]
        presets = MODEL_PRESETS.get(role, [])
        try:
            idx = int(idx_s)
            _label, slug = presets[idx]
        except (ValueError, IndexError):
            await query.edit_message_text(
                "Invalid preset.",
                reply_markup=_role_preset_keyboard(role) if role in MODEL_ROLE_TO_KEY else settings_keyboard(),
            )
            return
        try:
            _apply_model(role, slug)
        except ValueError as exc:
            await query.edit_message_text(
                str(exc),
                reply_markup=_role_preset_keyboard(role),
            )
            return
        bot_cfg, agent = _reload_bot_config(context)
        title = ROLE_LABELS.get(role, role)
        msg = f"{title} → {slug!r} (saved)."
        if role == "embed":
            msg += f" {EMBED_REINDEX_REMINDER}"
        elif role == "librarian":
            msg += f"\nActive librarian: {agent.config.model}"
        text = format_settings_summary(bot_cfg.agent, bot_cfg)
        await query.edit_message_text(f"{msg}\n\n{text}", reply_markup=settings_keyboard())
        return

    if data.startswith("set:x:"):
        role = data.split(":", 2)[2]
        try:
            reset_model_role(role)
        except ValueError as exc:
            markup = (
                _role_preset_keyboard(role)
                if role in MODEL_ROLE_TO_KEY
                else settings_keyboard()
            )
            await query.edit_message_text(str(exc), reply_markup=markup)
            return
        if role == "embed":
            sync_embed_to_os_environ()
        bot_cfg, _ = _reload_bot_config(context)
        text = format_settings_summary(bot_cfg.agent, bot_cfg)
        await query.edit_message_text(
            f"Cleared runtime override for {role!r}.\n\n{text}",
            reply_markup=settings_keyboard(),
        )
        return

    if data.startswith("set:c:"):
        role = data.split(":", 2)[2]
        if role not in MODEL_ROLE_TO_KEY:
            return
        context.user_data[AWAITING_MODEL_SLUG_KEY] = role
        title = ROLE_LABELS.get(role, role)
        await query.edit_message_text(
            f"{title}\n\nSend the **full OpenRouter slug** in your next message "
            f"(e.g. `anthropic/claude-sonnet-4.6`).\n\nTap ← Back or send /settings to cancel.",
            reply_markup=back_to_settings_markup(),
        )
        return


async def try_handle_awaiting_model_slug(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """If user is picking a custom slug after tapping, apply it. Returns True if handled."""
    role = context.user_data.pop(AWAITING_MODEL_SLUG_KEY, None)
    if not role or not update.message or not update.message.text:
        return False
    if await _reject_unauthorized(update, _config(context)):
        return True
    slug = update.message.text.strip()
    if not slug or slug.startswith("/"):
        context.user_data[AWAITING_MODEL_SLUG_KEY] = role
        await update.message.reply_text("Send a model slug, or /settings to cancel.")
        return True
    try:
        _apply_model(role, slug)
    except ValueError as exc:
        context.user_data[AWAITING_MODEL_SLUG_KEY] = role
        await update.message.reply_text(str(exc))
        return True
    bot_cfg, agent = _reload_bot_config(context)
    extra = ""
    if role == "embed":
        extra = f" {EMBED_REINDEX_REMINDER}"
    await update.message.reply_text(
        f"Set {role} to {slug!r} (saved).{extra}\n"
        f"Librarian active: {agent.config.model}",
        reply_markup=settings_keyboard(),
    )
    return True
