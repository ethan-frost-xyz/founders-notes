"""Tap-to-change models from /settings (inline keyboards)."""

from __future__ import annotations

from typing import Any

from auth import is_allowed
from config import BotConfig
from model_presets import MODEL_PRESETS, ROLE_LABELS
from runtime_settings import (
    MODEL_ROLE_TO_KEY,
    format_settings_summary,
    load_runtime_settings,
    reset_model_role,
    set_model,
    sync_embed_to_os_environ,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

AWAITING_MODEL_SLUG_KEY = "awaiting_model_slug"


def _config(context: ContextTypes.DEFAULT_TYPE) -> BotConfig:
    return context.application.bot_data["config"]


def _reload_bot_config(context: ContextTypes.DEFAULT_TYPE):
    from agent import VaultAgent
    from config import load_bot_config

    bot_config = load_bot_config()
    agent = VaultAgent(bot_config.agent)
    context.application.bot_data["config"] = bot_config
    context.application.bot_data["agent"] = agent
    return bot_config, agent


async def _reject_unauthorized(update: Update, config: BotConfig) -> bool:
    user = update.effective_user
    if is_allowed(user.id if user else None, config):
        return False
    if update.callback_query:
        await update.callback_query.answer("Unauthorized.", show_alert=True)
    elif update.message:
        await update.message.reply_text("Unauthorized.")
    return True


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Librarian", callback_data="set:r:librarian"),
                InlineKeyboardButton("Janitor", callback_data="set:r:janitor"),
            ],
            [
                InlineKeyboardButton("Expand", callback_data="set:r:expand"),
                InlineKeyboardButton("Embed", callback_data="set:r:embed"),
            ],
            [
                InlineKeyboardButton("max_steps", callback_data="set:steps"),
            ],
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
    rows.append([InlineKeyboardButton("← Back", callback_data="set:menu")])
    return InlineKeyboardMarkup(rows)


def _steps_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("3", callback_data="set:s:3"),
                InlineKeyboardButton("5", callback_data="set:s:5"),
                InlineKeyboardButton("8", callback_data="set:s:8"),
            ],
            [
                InlineKeyboardButton("10", callback_data="set:s:10"),
                InlineKeyboardButton("15", callback_data="set:s:15"),
                InlineKeyboardButton("20", callback_data="set:s:20"),
            ],
            [InlineKeyboardButton("← Back", callback_data="set:menu")],
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
    text += "\n\nTap a role below to change its model (no typing required)."
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
        extra = " Run /reindex or /sync before trusting search."
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

    if data == "set:menu":
        text = format_settings_summary(bot_cfg.agent, bot_cfg)
        text += "\n\nTap a role below to change its model."
        await query.edit_message_text(text, reply_markup=settings_keyboard())
        return

    if data == "set:steps":
        await query.edit_message_text(
            "Choose max tool steps for Librarian:",
            reply_markup=_steps_keyboard(),
        )
        return

    if data.startswith("set:s:"):
        from runtime_settings import set_max_steps

        try:
            value = int(data.split(":", 2)[2])
            set_max_steps(value)
        except (ValueError, IndexError) as exc:
            await query.edit_message_text(str(exc))
            return
        _, agent = _reload_bot_config(context)
        text = format_settings_summary(bot_cfg.agent, bot_cfg)
        text += f"\n\nmax_steps set to {agent.config.max_steps}."
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
            await query.edit_message_text("Invalid preset.")
            return
        try:
            _apply_model(role, slug)
        except ValueError as exc:
            await query.edit_message_text(str(exc))
            return
        bot_cfg, agent = _reload_bot_config(context)
        title = ROLE_LABELS.get(role, role)
        msg = f"{title} → {slug!r} (saved)."
        if role == "embed":
            msg += " Run /reindex or /sync before trusting search."
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
            await query.edit_message_text(str(exc))
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
            f"(e.g. `anthropic/claude-sonnet-4`).\n\n/cancel does not clear this — "
            f"send /settings to go back."
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
        extra = " Run /reindex or /sync before trusting search."
    await update.message.reply_text(
        f"Set {role} to {slug!r} (saved).{extra}\n"
        f"Librarian active: {agent.config.model}",
        reply_markup=settings_keyboard(),
    )
    return True
