"""Telegram handlers for Janitor mode (/janitor daily ritual workflow)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from auth import is_allowed
from config import BotConfig
from janitor_notes import parse_episode_id
from janitor_store import JanitorPhase, JanitorStore
from janitor_workflow import (
    draft_excerpt,
    file_notes,
    llm_clean_pasted_notes,
    resolve_catalog_row,
    run_expand,
    run_promote,
    run_reindex,
)
from messaging import reply_text_chunked
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from telegram import Message

JANITOR_HELP = """Janitor — paste episode + bullets to file notes.
Send an episode number to begin, or tap Exit Janitor to return to Q&A."""

_PREVIEW_FOOTER = (
    "\n\n_Reply with edits to revise this clean, or use Retry / Approve / Exit Janitor._"
)

_STILL_WORKING_DELAY_S = 20.0


def _config(context: ContextTypes.DEFAULT_TYPE) -> BotConfig:
    return context.application.bot_data["config"]


def _janitor_store(context: ContextTypes.DEFAULT_TYPE) -> JanitorStore:
    return context.application.bot_data["janitor"]


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


def _folder_name(row: dict) -> str:
    import paths as vault_paths

    return vault_paths.folder_name(row["id"], row["slug"], row.get("episode_number"))


async def _reject_unauthorized(update: Update, config: BotConfig) -> bool:
    user = update.effective_user
    if is_allowed(user.id if user else None, config):
        return False
    if update.message:
        await update.message.reply_text("Unauthorized.")
    return True


def _exit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Exit Janitor", callback_data="janitor:exit")]]
    )


def _preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Retry", callback_data="janitor:retry"),
                InlineKeyboardButton("Approve", callback_data="janitor:approve"),
            ],
            [InlineKeyboardButton("Exit Janitor", callback_data="janitor:exit")],
        ]
    )


def _confirm_overwrite_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Confirm overwrite", callback_data="janitor:confirm_overwrite"
                ),
            ],
            [InlineKeyboardButton("Exit Janitor", callback_data="janitor:exit")],
        ]
    )


def _review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Promote & reindex", callback_data="janitor:promote"),
                InlineKeyboardButton("Retry expand", callback_data="janitor:retry_expand"),
            ],
            [InlineKeyboardButton("Exit Janitor", callback_data="janitor:exit")],
        ]
    )


async def _janitor_exit(uid: int, store: JanitorStore, message: Message, *, edit: bool = False) -> None:
    store.reset(uid)
    text = "Back to Librarian."
    if edit:
        await message.edit_text(text)
    else:
        await message.reply_text(text)


def _needs_overwrite_confirm(vault_root, row: dict) -> bool:
    from markdown_io import has_timestamp_datapoints

    npath = _notes_path(vault_root, row)
    return npath.is_file() and has_timestamp_datapoints(npath)


async def _prompt_overwrite_confirm(
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
    markup = _confirm_overwrite_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)


async def _run_llm_clean(
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
            reply_markup=_exit_keyboard(),
        )
        return

    if not session.raw_paste:
        await message.reply_text(
            "Nothing to clean — /janitor to restart.",
            reply_markup=_exit_keyboard(),
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
    msg += _PREVIEW_FOOTER
    await reply_text_chunked(message, msg, reply_markup=_preview_keyboard())


async def _file_and_expand(
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
            reply_markup=_exit_keyboard(),
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
                reply_markup=_review_keyboard(),
            )
            return
        session.phase = JanitorPhase.REVIEW_DRAFT
        excerpt = await asyncio.to_thread(draft_excerpt, vault_root, row)
        await reply_text_chunked(
            message,
            f"Draft ready for **{session.episode_id}**:\n\n{excerpt}",
            reply_markup=_review_keyboard(),
        )
    except Exception as e:
        session.last_error = str(e)
        await message.reply_text(f"Error: {e}", reply_markup=_exit_keyboard())


async def _begin_approve(
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
            await message.edit_text(text, reply_markup=_exit_keyboard())
        else:
            await message.reply_text(text, reply_markup=_exit_keyboard())
        return
    row = resolve_catalog_row(vault_root, session.episode_id)
    if _needs_overwrite_confirm(vault_root, row):
        await _prompt_overwrite_confirm(
            message, session, vault_root=vault_root, row=row, edit=edit,
        )
        return
    if edit:
        await message.edit_text(f"Approved — filing {session.episode_id}…")
    await _file_and_expand(
        message, session, vault_root=vault_root, uid=uid, store=store,
    )


async def cmd_janitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    uid = update.effective_user.id
    store = _janitor_store(context)
    store.reset(uid)
    session = store.get(uid)
    session.phase = JanitorPhase.AWAIT_EPISODE
    await reply_text_chunked(
        update.message, JANITOR_HELP, reply_markup=_exit_keyboard(),
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


async def _build_preview(message: Message, session, raw_notes: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    session.raw_paste = raw_notes
    bot_cfg = _config(context)
    vault_root = bot_cfg.agent.vault_root
    try:
        await _run_llm_clean(message, session, bot_cfg=bot_cfg, vault_root=vault_root)
    except Exception as e:
        session.last_error = str(e)
        await message.reply_text(f"Clean failed: {e}", reply_markup=_exit_keyboard())


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

    if session.phase in (JanitorPhase.REVIEW_DRAFT, JanitorPhase.CONFIRM_OVERWRITE):
        await update.message.reply_text(
            "Use the buttons below, or tap Exit Janitor.",
            reply_markup=_exit_keyboard()
            if session.phase == JanitorPhase.CONFIRM_OVERWRITE
            else _review_keyboard(),
        )
        return True

    if session.phase == JanitorPhase.PREVIEW:
        lowered = text.lower()
        if lowered in ("approve", "yes", "ok", "lgtm"):
            await _begin_approve(
                update.message, session, vault_root=vault_root, uid=uid, store=store,
            )
            return True
        if lowered in ("retry", "again"):
            try:
                await _run_llm_clean(
                    update.message,
                    session,
                    bot_cfg=bot_cfg,
                    vault_root=vault_root,
                    status_prefix="Retrying",
                )
            except Exception as e:
                session.last_error = str(e)
                await update.message.reply_text(f"Retry failed: {e}")
            return True
        try:
            await _run_llm_clean(
                update.message,
                session,
                bot_cfg=bot_cfg,
                vault_root=vault_root,
                status_prefix="Revising",
                feedback=text,
            )
        except Exception as e:
            session.last_error = str(e)
            await update.message.reply_text(f"Revision failed: {e}")
        return True

    if session.phase == JanitorPhase.AWAIT_EPISODE:
        ep_id = parse_episode_id(text)
        if not ep_id:
            await update.message.reply_text(
                "Send an episode number (e.g. 191, 200, or ep-0200), then paste bullets.",
                reply_markup=_exit_keyboard(),
            )
            return True
        lines = text.strip().splitlines()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        session.episode_id = ep_id
        if body:
            await _build_preview(update.message, session, text, context)
            return True
        session.phase = JanitorPhase.AWAIT_NOTES
        await update.message.reply_text(
            f"Episode {ep_id}. Paste your notes (any common format).",
            reply_markup=_exit_keyboard(),
        )
        return True

    if session.phase == JanitorPhase.AWAIT_NOTES:
        if not session.episode_id:
            session.phase = JanitorPhase.AWAIT_EPISODE
            await update.message.reply_text(
                "Episode lost — send episode number again.",
                reply_markup=_exit_keyboard(),
            )
            return True
        await _build_preview(update.message, session, text, context)
        return True

    await update.message.reply_text(
        "Unexpected state — /cancel and /janitor to restart.",
        reply_markup=_exit_keyboard(),
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

    if data in ("janitor:exit", "janitor:cancel"):
        await _janitor_exit(uid, store, query.message, edit=True)
        return

    if data == "janitor:confirm_overwrite":
        if session.phase != JanitorPhase.CONFIRM_OVERWRITE:
            await query.edit_message_text(
                "Nothing to confirm — /janitor to restart.",
                reply_markup=_exit_keyboard(),
            )
            return
        await query.edit_message_text(f"Overwriting {session.episode_id}…")
        await _file_and_expand(
            query.message,
            session,
            vault_root=vault_root,
            uid=uid,
            store=store,
            replace=True,
        )
        return

    if data in ("janitor:retry", "janitor:reclean", "janitor:llm_clean"):
        if session.phase != JanitorPhase.PREVIEW:
            await query.edit_message_text(
                "Nothing to retry — /janitor to restart.",
                reply_markup=_exit_keyboard(),
            )
            return
        try:
            await _run_llm_clean(
                query.message,
                session,
                bot_cfg=bot_cfg,
                vault_root=vault_root,
                status_prefix="Retrying",
            )
        except Exception as e:
            session.last_error = str(e)
            await query.edit_message_text(f"Retry failed: {e}")
        return

    if data in ("janitor:approve", "janitor:file_expand"):
        if session.phase != JanitorPhase.PREVIEW:
            await query.edit_message_text(
                "Nothing to approve — /janitor to restart.",
                reply_markup=_exit_keyboard(),
            )
            return
        await _begin_approve(
            query.message,
            session,
            vault_root=vault_root,
            uid=uid,
            store=store,
            edit=True,
        )
        return

    if data == "janitor:retry_expand":
        if not session.episode_id:
            await query.edit_message_text(
                "No episode — /janitor to restart.",
                reply_markup=_exit_keyboard(),
            )
            return
        await query.edit_message_text(f"Re-expanding {session.episode_id}…")
        code, log_tail = await asyncio.to_thread(
            run_expand, vault_root, session.episode_id, force=True,
        )
        if code != 0:
            await reply_text_chunked(query.message, f"Expand failed:\n{log_tail}")
            return
        row = resolve_catalog_row(vault_root, session.episode_id)
        excerpt = await asyncio.to_thread(draft_excerpt, vault_root, row)
        session.phase = JanitorPhase.REVIEW_DRAFT
        await reply_text_chunked(
            query.message,
            f"Draft updated:\n\n{excerpt}",
            reply_markup=_review_keyboard(),
        )
        return

    if data == "janitor:promote":
        if not session.episode_id:
            await query.edit_message_text(
                "No episode — /janitor to restart.",
                reply_markup=_exit_keyboard(),
            )
            return
        await query.edit_message_text(f"Promoting {session.episode_id}…")
        code, msg, _warnings = await asyncio.to_thread(
            run_promote, vault_root, session.episode_id,
        )
        if code != 0:
            await reply_text_chunked(
                query.message, f"Promote failed:\n{msg}", reply_markup=_exit_keyboard(),
            )
            return
        row = resolve_catalog_row(vault_root, session.episode_id)
        folder = _folder_name(row)
        notes_rel = f"content/notes/{folder}/{folder}.notes.md"
        expanded_rel = f"content/notes/{folder}/{folder}.expanded.md"
        audit = f"Wrote: {notes_rel} → promoted {expanded_rel}"
        idx_code, idx_msg = await asyncio.to_thread(run_reindex, vault_root)
        store.reset(uid)
        if idx_code != 0:
            await reply_text_chunked(
                query.message,
                f"{msg}\n{audit}\n\nReindex failed:\n{idx_msg}\n\n"
                "Run sync-and-index.sh on the Mac mini.",
            )
            return
        await reply_text_chunked(
            query.message,
            f"Done. {msg}\n{audit}\n{idx_msg}\n\n"
            "Back in Librarian mode — vault search includes this episode.",
        )
