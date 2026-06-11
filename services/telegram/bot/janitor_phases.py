"""Janitor workflow phase helpers (clean, preview, file, expand, approve)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from callbacks import (
    CALLBACK_JANITOR_APPROVE,
    CALLBACK_JANITOR_CONFIRM_OVERWRITE,
    CALLBACK_JANITOR_PROMOTE,
    CALLBACK_JANITOR_PUSH,
    CALLBACK_JANITOR_PUSH_SKIP,
    CALLBACK_JANITOR_RETRY,
    CALLBACK_JANITOR_RETRY_EXPAND,
)
from config import BotConfig
from janitor_store import JanitorPhase, JanitorStore
from janitor_workflow import (
    draft_excerpt,
    file_notes,
    llm_clean_pasted_notes,
    resolve_catalog_row,
    run_expand,
)
from messaging import reply_text_chunked
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from ui_keyboards import janitor_back_markup, janitor_back_row

if TYPE_CHECKING:
    from telegram import Message

PREVIEW_FOOTER = (
    "\n\n_Reply with edits to revise this clean, or use Retry / Approve / ← Back._"
)

_STILL_WORKING_DELAY_S = 20.0


def _require_clean_model(bot_cfg: BotConfig) -> str | None:
    return bot_cfg.janitor_clean_model or None


def _episode_title(vault_root, episode_id: str | None) -> str | None:
    if not episode_id:
        return None
    try:
        row = resolve_catalog_row(vault_root, episode_id)
        return row.get("title") or None
    except SystemExit:
        return None
    except Exception:
        return None


def _notes_path(vault_root, row: dict):
    import paths as vault_paths

    return vault_paths.notes_file_path(row["id"], row["slug"], row.get("episode_number"))


def folder_name(row: dict) -> str:
    import paths as vault_paths

    return vault_paths.folder_name(row["id"], row["slug"], row.get("episode_number"))


def exit_keyboard() -> InlineKeyboardMarkup:
    return janitor_back_markup()


def preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Retry", callback_data=CALLBACK_JANITOR_RETRY),
                InlineKeyboardButton("Approve", callback_data=CALLBACK_JANITOR_APPROVE),
            ],
            janitor_back_row(),
        ]
    )


def confirm_overwrite_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Confirm overwrite", callback_data=CALLBACK_JANITOR_CONFIRM_OVERWRITE
                ),
            ],
            janitor_back_row(),
        ]
    )


def review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Promote & reindex", callback_data=CALLBACK_JANITOR_PROMOTE),
                InlineKeyboardButton("Retry expand", callback_data=CALLBACK_JANITOR_RETRY_EXPAND),
            ],
            janitor_back_row(),
        ]
    )


def post_promote_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Push to GitHub", callback_data=CALLBACK_JANITOR_PUSH),
                InlineKeyboardButton("Skip", callback_data=CALLBACK_JANITOR_PUSH_SKIP),
            ],
            janitor_back_row(),
        ]
    )


async def janitor_exit(uid: int, store: JanitorStore, message: Message, *, edit: bool = False) -> None:
    store.reset(uid)
    text = "Back to Librarian."
    if edit:
        await message.edit_text(text)
    else:
        await message.reply_text(text)


def needs_overwrite_confirm(vault_root, row: dict) -> bool:
    from markdown_io import has_timestamp_datapoints

    npath = _notes_path(vault_root, row)
    return npath.is_file() and has_timestamp_datapoints(npath)


async def prompt_overwrite_confirm(
    message: Message,
    session,
    *,
    vault_root,
    row: dict,
    edit: bool = False,
) -> None:
    rel = _notes_path(vault_root, row).relative_to(vault_root)
    session.phase = JanitorPhase.CONFIRM_OVERWRITE
    text = f"Overwriting {rel} — this replaces existing notes."
    markup = confirm_overwrite_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)


async def run_llm_clean(
    message: Message,
    session,
    *,
    bot_cfg: BotConfig,
    vault_root,
    status_prefix: str = "Cleaning",
    feedback: str | None = None,
) -> None:
    clean_model = _require_clean_model(bot_cfg)
    if not clean_model:
        await message.reply_text(
            "Janitor clean model not set. Use /setmodel janitor <openrouter-slug> "
            "(see /settings).",
            reply_markup=exit_keyboard(),
        )
        return

    if not session.raw_paste:
        await message.reply_text(
            "Nothing to clean — /janitor to restart.",
            reply_markup=exit_keyboard(),
        )
        return

    agent_cfg = bot_cfg.agent
    title = _episode_title(vault_root, session.episode_id)
    status_msg = await message.reply_text(f"{status_prefix}…")
    still_task: asyncio.Task | None = None

    async def _still_working() -> None:
        await asyncio.sleep(_STILL_WORKING_DELAY_S)
        try:
            await status_msg.edit_text("Still working…")
        except Exception:
            pass

    still_task = asyncio.create_task(_still_working())

    try:
        body, warnings = await asyncio.to_thread(
            llm_clean_pasted_notes,
            session.raw_paste,
            api_key=agent_cfg.api_key,
            model=clean_model,
            base_url=agent_cfg.openrouter_base_url,
            vault_root=vault_root,
            episode_id=session.episode_id,
            episode_title=title,
            current_draft=session.cleaned_body if feedback else None,
            feedback=feedback,
        )
    finally:
        if still_task is not None:
            still_task.cancel()
            try:
                await still_task
            except asyncio.CancelledError:
                pass
        try:
            await status_msg.delete()
        except Exception:
            pass

    session.cleaned_body = body
    session.phase = JanitorPhase.PREVIEW
    warn_text = "\n".join(f"• {w}" for w in warnings) if warnings else ""
    preview = body if len(body) < 2800 else body[:2800] + "\n…"
    ep_label = session.episode_id or "episode"
    msg = f"**{ep_label}** — cleaned preview\n\n{preview}"
    if warn_text:
        msg += f"\n\n{warn_text}"
    msg += PREVIEW_FOOTER
    await reply_text_chunked(message, msg, reply_markup=preview_keyboard())


async def file_and_expand(
    message: Message,
    session,
    *,
    vault_root,
    uid: int,
    store: JanitorStore,
    replace: bool = False,
) -> None:
    if not session.episode_id or not session.cleaned_body:
        await message.reply_text(
            "Nothing to file — /janitor to restart.",
            reply_markup=exit_keyboard(),
        )
        return
    await message.reply_text(f"Filing notes for {session.episode_id}…")
    try:
        row = resolve_catalog_row(vault_root, session.episode_id)
        path = await asyncio.to_thread(
            file_notes, vault_root, row, session.cleaned_body, replace=replace,
        )
        rel = path.relative_to(vault_root)
        await message.reply_text(
            f"Notes saved ({rel}). Expanding via OpenRouter (may take several minutes)…"
        )
        code, log_tail = await asyncio.to_thread(
            run_expand, vault_root, session.episode_id, force=False,
        )
        if code != 0:
            session.last_error = log_tail
            session.phase = JanitorPhase.REVIEW_DRAFT
            await reply_text_chunked(
                message,
                f"Expand failed (exit {code}):\n{log_tail}",
                reply_markup=review_keyboard(),
            )
            return
        session.phase = JanitorPhase.REVIEW_DRAFT
        excerpt = await asyncio.to_thread(draft_excerpt, vault_root, row)
        await reply_text_chunked(
            message,
            f"Draft ready for **{session.episode_id}**:\n\n{excerpt}",
            reply_markup=review_keyboard(),
        )
    except Exception as e:
        session.last_error = str(e)
        await message.reply_text(f"Error: {e}", reply_markup=exit_keyboard())


async def begin_approve(
    message: Message,
    session,
    *,
    vault_root,
    uid: int,
    store: JanitorStore,
    edit: bool = False,
) -> None:
    if not session.episode_id or not session.cleaned_body:
        text = "Nothing to approve — /janitor to restart."
        if edit:
            await message.edit_text(text, reply_markup=exit_keyboard())
        else:
            await message.reply_text(text, reply_markup=exit_keyboard())
        return
    row = resolve_catalog_row(vault_root, session.episode_id)
    if needs_overwrite_confirm(vault_root, row):
        await prompt_overwrite_confirm(
            message, session, vault_root=vault_root, row=row, edit=edit,
        )
        return
    if edit:
        await message.edit_text(f"Approved — filing {session.episode_id}…")
    await file_and_expand(
        message, session, vault_root=vault_root, uid=uid, store=store,
    )


async def build_preview(message: Message, session, raw_notes: str, bot_cfg: BotConfig) -> None:
    session.raw_paste = raw_notes
    vault_root = bot_cfg.agent.vault_root
    try:
        await run_llm_clean(message, session, bot_cfg=bot_cfg, vault_root=vault_root)
    except Exception as e:
        session.last_error = str(e)
        await message.reply_text(f"Clean failed: {e}", reply_markup=exit_keyboard())
