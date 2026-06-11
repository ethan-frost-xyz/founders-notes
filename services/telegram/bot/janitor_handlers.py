"""Telegram handlers for Janitor mode (/janitor daily ritual workflow)."""

from __future__ import annotations

import asyncio

from callbacks import (
    CALLBACK_JANITOR_APPROVE,
    CALLBACK_JANITOR_CANCEL,
    CALLBACK_JANITOR_CONFIRM_OVERWRITE,
    CALLBACK_JANITOR_PROMOTE,
    CALLBACK_JANITOR_PUSH,
    CALLBACK_JANITOR_PUSH_SKIP,
    CALLBACK_JANITOR_RETRY,
    CALLBACK_JANITOR_RETRY_EXPAND,
)
from context import (
    config as _config,
    janitor_store as _janitor_store,
    reject_unauthorized as _reject_unauthorized,
)
from janitor_notes import parse_episode_id
from janitor_phases import (
    begin_approve,
    build_preview,
    exit_keyboard,
    file_and_expand,
    folder_name,
    janitor_exit,
    post_promote_keyboard,
    review_keyboard,
    run_llm_clean,
)
from janitor_store import JanitorPhase
from janitor_workflow import (
    draft_excerpt,
    resolve_catalog_row,
    run_expand,
    run_promote,
    run_reindex,
)
from messaging import reply_text_chunked
from ops_runner import release_ops_lock, run_vault_push_op, try_acquire_ops_lock
from telegram import Message, Update
from telegram.ext import ContextTypes

from config import BotConfig

JANITOR_HELP = """Janitor — paste episode + bullets to file notes.
Send an episode number to begin, or tap ← Back to return to Q&A."""


async def _run_clean_action(
    message: Message,
    session,
    *,
    bot_cfg: BotConfig,
    vault_root,
    feedback: str | None = None,
    edit_on_error: bool = False,
) -> None:
    revising = bool(feedback)
    status_prefix = "Revising" if revising else "Retrying"
    fail_label = "Revision failed" if revising else "Retry failed"
    try:
        await run_llm_clean(
            message,
            session,
            bot_cfg=bot_cfg,
            vault_root=vault_root,
            status_prefix=status_prefix,
            feedback=feedback,
        )
    except Exception as e:
        session.last_error = str(e)
        if edit_on_error:
            await message.edit_text(
                f"{fail_label}: {e}",
                reply_markup=exit_keyboard(),
            )
        else:
            await message.reply_text(f"{fail_label}: {e}")


async def cmd_janitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    uid = update.effective_user.id
    store = _janitor_store(context)
    store.reset(uid)
    session = store.get(uid)
    session.phase = JanitorPhase.AWAIT_EPISODE
    await reply_text_chunked(
        update.message, JANITOR_HELP, reply_markup=exit_keyboard(),
    )


async def cmd_librarian(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    _janitor_store(context).reset(update.effective_user.id)
    await update.message.reply_text("Back to Librarian mode. Ask a vault question anytime.")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    _janitor_store(context).reset(update.effective_user.id)
    await update.message.reply_text("Back to Librarian.")


async def on_janitor_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text while in Janitor mode. Returns True if consumed."""
    if not update.message or not update.message.text:
        return False
    text = update.message.text.strip()
    if await _reject_unauthorized(update, _config(context)):
        return True
    uid = update.effective_user.id
    store = _janitor_store(context)
    if not store.is_active(uid):
        return False

    session = store.get(uid)
    bot_cfg = _config(context)
    vault_root = bot_cfg.agent.vault_root

    if session.phase == JanitorPhase.AWAIT_PUSH:
        await update.message.reply_text(
            "Promote complete. Tap Push to GitHub or Skip.",
            reply_markup=post_promote_keyboard(),
        )
        return True

    if session.phase in (JanitorPhase.REVIEW_DRAFT, JanitorPhase.CONFIRM_OVERWRITE):
        await update.message.reply_text(
            "Use the buttons below, or tap ← Back.",
            reply_markup=exit_keyboard()
            if session.phase == JanitorPhase.CONFIRM_OVERWRITE
            else review_keyboard(),
        )
        return True

    if session.phase == JanitorPhase.PREVIEW:
        lowered = text.lower()
        if lowered in ("approve", "yes", "ok", "lgtm"):
            await begin_approve(
                update.message, session, vault_root=vault_root, uid=uid, store=store,
            )
            return True
        if lowered in ("retry", "again"):
            await _run_clean_action(
                update.message,
                session,
                bot_cfg=bot_cfg,
                vault_root=vault_root,
            )
            return True
        await _run_clean_action(
            update.message,
            session,
            bot_cfg=bot_cfg,
            vault_root=vault_root,
            feedback=text,
        )
        return True

    if session.phase == JanitorPhase.AWAIT_EPISODE:
        ep_id = parse_episode_id(text)
        if not ep_id:
            await update.message.reply_text(
                "Send an episode number (e.g. 191, 200, or ep-0200), then paste bullets.",
                reply_markup=exit_keyboard(),
            )
            return True
        lines = text.strip().splitlines()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        session.episode_id = ep_id
        if body:
            await build_preview(update.message, session, text, bot_cfg)
            return True
        session.phase = JanitorPhase.AWAIT_NOTES
        await update.message.reply_text(
            f"Episode {ep_id}. Paste your notes (any common format).",
            reply_markup=exit_keyboard(),
        )
        return True

    if session.phase == JanitorPhase.AWAIT_NOTES:
        if not session.episode_id:
            session.phase = JanitorPhase.AWAIT_EPISODE
            await update.message.reply_text(
                "Episode lost — send episode number again.",
                reply_markup=exit_keyboard(),
            )
            return True
        await build_preview(update.message, session, text, bot_cfg)
        return True

    await update.message.reply_text(
        "Unexpected state — /cancel and /janitor to restart.",
        reply_markup=exit_keyboard(),
    )
    return True


async def on_janitor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    if await _reject_unauthorized(update, _config(context)):
        return

    uid = update.effective_user.id
    store = _janitor_store(context)
    session = store.get(uid)
    bot_cfg = _config(context)
    vault_root = bot_cfg.agent.vault_root
    data = query.data

    if data in ("janitor:exit", CALLBACK_JANITOR_CANCEL):
        await janitor_exit(uid, store, query.message, edit=True)
        return

    if data == CALLBACK_JANITOR_CONFIRM_OVERWRITE:
        if session.phase != JanitorPhase.CONFIRM_OVERWRITE:
            await query.edit_message_text(
                "Nothing to confirm — /janitor to restart.",
                reply_markup=exit_keyboard(),
            )
            return
        await query.edit_message_text(f"Overwriting {session.episode_id}…")
        await file_and_expand(
            query.message,
            session,
            vault_root=vault_root,
            uid=uid,
            store=store,
            replace=True,
        )
        return

    if data == CALLBACK_JANITOR_RETRY:
        if session.phase != JanitorPhase.PREVIEW:
            await query.edit_message_text(
                "Nothing to retry — /janitor to restart.",
                reply_markup=exit_keyboard(),
            )
            return
        await _run_clean_action(
            query.message,
            session,
            bot_cfg=bot_cfg,
            vault_root=vault_root,
            edit_on_error=True,
        )
        return

    if data == CALLBACK_JANITOR_APPROVE:
        if session.phase != JanitorPhase.PREVIEW:
            await query.edit_message_text(
                "Nothing to approve — /janitor to restart.",
                reply_markup=exit_keyboard(),
            )
            return
        await begin_approve(
            query.message,
            session,
            vault_root=vault_root,
            uid=uid,
            store=store,
            edit=True,
        )
        return

    if data == CALLBACK_JANITOR_RETRY_EXPAND:
        if not session.episode_id:
            await query.edit_message_text(
                "No episode — /janitor to restart.",
                reply_markup=exit_keyboard(),
            )
            return
        await query.edit_message_text(f"Re-expanding {session.episode_id}…")
        code, log_tail = await asyncio.to_thread(
            run_expand, vault_root, session.episode_id, force=True,
        )
        if code != 0:
            await reply_text_chunked(
                query.message,
                f"Expand failed:\n{log_tail}",
                reply_markup=exit_keyboard(),
            )
            return
        row = resolve_catalog_row(vault_root, session.episode_id)
        excerpt = await asyncio.to_thread(draft_excerpt, vault_root, row)
        session.phase = JanitorPhase.REVIEW_DRAFT
        await reply_text_chunked(
            query.message,
            f"Draft updated:\n\n{excerpt}",
            reply_markup=review_keyboard(),
        )
        return

    if data == CALLBACK_JANITOR_PROMOTE:
        if not session.episode_id:
            await query.edit_message_text(
                "No episode — /janitor to restart.",
                reply_markup=exit_keyboard(),
            )
            return
        await query.edit_message_text(f"Promoting {session.episode_id}…")
        code, msg, _warnings = await asyncio.to_thread(
            run_promote, vault_root, session.episode_id,
        )
        if code != 0:
            await reply_text_chunked(
                query.message, f"Promote failed:\n{msg}", reply_markup=exit_keyboard(),
            )
            return
        row = resolve_catalog_row(vault_root, session.episode_id)
        folder = folder_name(row)
        notes_rel = f"content/notes/{folder}/{folder}.notes.md"
        expanded_rel = f"content/notes/{folder}/{folder}.expanded.md"
        audit = f"Wrote: {notes_rel} → promoted {expanded_rel}"
        idx_code, idx_msg = await asyncio.to_thread(run_reindex, vault_root)
        if idx_code != 0:
            store.reset(uid)
            await reply_text_chunked(
                query.message,
                f"{msg}\n{audit}\n\nReindex failed:\n{idx_msg}\n\n"
                "Run sync-and-index.sh on the Mac mini.",
                reply_markup=exit_keyboard(),
            )
            return
        session.phase = JanitorPhase.AWAIT_PUSH
        await reply_text_chunked(
            query.message,
            f"Done. {msg}\n{audit}\n{idx_msg}\n\n"
            "Vault search includes this episode. Push notes to GitHub?",
            reply_markup=post_promote_keyboard(),
        )
        return

    if data == CALLBACK_JANITOR_PUSH_SKIP:
        if session.phase != JanitorPhase.AWAIT_PUSH:
            await query.edit_message_text(
                "Nothing to skip — /janitor to restart.",
                reply_markup=exit_keyboard(),
            )
            return
        store.reset(uid)
        await query.edit_message_text(
            "Skipped push. Back in Librarian mode.",
            reply_markup=exit_keyboard(),
        )
        return

    if data == CALLBACK_JANITOR_PUSH:
        if session.phase != JanitorPhase.AWAIT_PUSH or not session.episode_id:
            await query.edit_message_text(
                "Nothing to push — /janitor to restart.",
                reply_markup=exit_keyboard(),
            )
            return
        bot_data = context.application.bot_data
        if not try_acquire_ops_lock(bot_data):
            await query.edit_message_text(
                "Another op is already running. Try again later.",
                reply_markup=post_promote_keyboard(),
            )
            return
        ep_id = session.episode_id
        await query.edit_message_text(f"Pushing {ep_id} to GitHub…")
        try:
            code, push_log = await asyncio.to_thread(
                run_vault_push_op,
                vault_root,
                message=f"vault: Janitor promote {ep_id}",
                episode_id=ep_id,
                skip_verify=True,
            )
        finally:
            release_ops_lock(bot_data)
        store.reset(uid)
        if code != 0:
            await reply_text_chunked(
                query.message,
                f"Push failed (exit {code}).\n\n{push_log}\n\n"
                "Use /push later or push from SSH.",
                reply_markup=exit_keyboard(),
            )
            return
        await reply_text_chunked(
            query.message,
            f"Pushed {ep_id} to GitHub.\n\n{push_log}\n\nBack in Librarian mode.",
            reply_markup=exit_keyboard(),
        )
