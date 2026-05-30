---
name: Telegram UI Overhaul
overview: "Rework the Telegram bot UI: curated BotFather menu, stats-only /start, Janitor inline navigation with overwrite confirm, quieter status/ops copy, and Ops panel under /settings. UI layer only; reuse repo studied-episode semantics."
todos:
  - id: trim-menu
    content: Trim set_my_commands in __main__.py to 7 commands; align BotCommand descriptions
    status: completed
  - id: gut-start
    content: Remove HELP_TEXT; extend vault_stats_text with studied count via count_phase2_coverage
    status: completed
  - id: slim-janitor-help
    content: Replace JANITOR_HELP with two-line prompt; merge Cancel into Exit Janitor
    status: completed
  - id: exit-button
    content: Add janitor:exit callback; Exit Janitor on all Janitor keyboards; keep /cancel as alias
    status: completed
  - id: confirm-overwrite
    content: CONFIRM_OVERWRITE phase; has_timestamp_datapoints gate; replace (not merge) on confirm
    status: completed
  - id: clean-status
    content: Drop model slug from clean status; Still working edit; remove _OPS_WARN from typed ops
    status: completed
  - id: ops-panel
    content: Ops inline panel in settings_handlers; shared async ops helper (avoid import cycles)
    status: completed
  - id: verify-harness-docs
    content: Update librarian basic_qa scenario, docs/telegram-vault-agent.md + janitor.md; pytest harness
    status: completed
isProject: false
---

# Telegram UI Overhaul

**Status:** Shipped on `main` (May 2026). Operator/docs: [`docs/telegram-vault-agent.md`](../../../docs/telegram-vault-agent.md), [`docs/janitor.md`](../../../docs/janitor.md). Do not implement from this archive unless restoring history.

## Success criteria

- `/start` shows **three lines only**: catalog episode count, **studied** count (timestamp bullets in `.notes.md`, same definition as `maintain.py` / Librarian corpus), chunks index mtime.
- BotFather menu lists **7** commands; power-user commands (`/clear`, `/resume`, `/setmodel`, …) still work when typed.
- Janitor: every step has **[Exit Janitor]**; no separate Cancel button; typing always works (inline keyboards only — **not** a reply keyboard; text input is never blocked).
- Approve on an episode with existing timestamp bullets → **confirm** → **replace** notes body (not silent merge).
- `/settings` → **Ops** → run sync/pull/reindex with in-message status edits; **Restart** is a special case (see §6).
- `pytest tests/test_harness_scenarios.py -q` passes after scenario/doc updates.

## Scope

UI + Janitor write semantics for the confirm path only. No retrieval, agent prompts, or catalog schema changes.

**From [potential-ideas.md](../../../potential-ideas.md) — in scope:** curated command menu (BotFather `setMyCommands`), Janitor audit/overwrite confirm, snappier clean feedback (not token streaming).

**Deferred (separate plans):** SP3.1 `/web` provider, Librarian quality cluster, true SSE streaming, `/resume` auto-sync, path-filtered reindex.

---

## 1. Trim BotFather command menu — [`__main__.py`](../../../services/telegram/bot/__main__.py)

Slim `_register_bot_commands` from 17 → **7**:

| Command | Description |
|---------|-------------|
| `start` | Vault stats |
| `janitor` | Notes ritual |
| `web` | Web search (add query) |
| `settings` | Models, steps, ops |
| `sync` | Pull + reindex |
| `newchat` | Export session, reset |
| `restart` | Restart bot |

**Removed from menu only** (still registered handlers): `librarian`, `cancel`, `clear`, `resume`, `pull`, `reindex`, `setmodel`, `resetmodel`, `setsteps`, `resetsteps`.

**Done when:** Mac mini bot restart shows 7 commands in Telegram menu; `/clear` still works when typed.

---

## 2. Gut `/start` — [`handlers.py`](../../../services/telegram/bot/handlers.py)

- Delete `HELP_TEXT`.
- `cmd_start` → `reply_text_chunked(update.message, vault_stats_text(vault_root))` only.

**Studied count (fix — do not use `chunks.jsonl`):**

Distinct episodes in the chunk index ≠ studied. Studied = `has_timestamp_datapoints(notes_path)` per [`build_chunks.py`](../../../ingestion/search/build_chunks.py) `episode_is_listened`.

In `vault_stats_text(vault_root)`:

1. `setup_ingestion_paths(vault_root)` (same pattern as Janitor).
2. `load_catalog()` from `catalog/episodes.jsonl`.
3. `count_phase2_coverage(rows)` from [`ingestion/lib/gaps_report.py`](../../../ingestion/lib/gaps_report.py) → use `notes_with_datapoints` (complete-transcript episodes with timestamp bullets).
4. Keep existing catalog row count + `chunks.jsonl` mtime.

Example output:

```text
Episodes in catalog: 417
Studied (timestamp bullets): 203
Chunks index updated: 2026-05-29 14:32 UTC
```

**Done when:** `/start` no longer contains "Founders vault agent" or command list.

---

## 3. Janitor help + Exit button — [`janitor_handlers.py`](../../../services/telegram/bot/janitor_handlers.py)

Replace `JANITOR_HELP` with:

```text
Janitor — paste episode + bullets to file notes.
Send an episode number to begin, or tap Exit Janitor to return to Q&A.
```

- `_exit_keyboard()` helper with `janitor:exit`.
- Handler `janitor:exit` → `store.reset(uid)` + `"Back to Librarian."`
- **Merge Cancel → Exit Janitor** on PREVIEW / REVIEW_DRAFT keyboards; remove `janitor:cancel` handler (or one-line alias to exit for backward compatibility).
- Add Exit row to entry, AWAIT_NOTES, AWAIT_EPISODE nudges.
- **Keep** `CommandHandler("cancel", cmd_cancel)` and `cmd_librarian` — only removed from menu, not from code.
- Update `_PREVIEW_FOOTER` to mention **Exit Janitor** instead of Cancel.

**Done when:** harness Janitor scenarios still pass; no UI label "Cancel".

---

## 4. Overwrite confirmation — [`janitor_store.py`](../../../services/telegram/bot/janitor_store.py), [`janitor_handlers.py`](../../../services/telegram/bot/janitor_handlers.py), [`janitor_workflow.py`](../../../services/telegram/bot/janitor_workflow.py)

### Phase

```python
CONFIRM_OVERWRITE = "confirm_overwrite"
```

`on_janitor_text` in this phase: nudge to use buttons (same as REVIEW_DRAFT).

### Gate (both Approve button and text `approve`/`yes`/`ok`)

Before `file_notes`, after resolving row:

- `npath = notes_file_path(...)`
- If `has_timestamp_datapoints(npath)` ([`markdown_io.has_timestamp_datapoints`](../../../ingestion/lib/markdown_io.py)) → `session.phase = CONFIRM_OVERWRITE`, message:

  `Overwriting {rel} — this replaces existing notes.`

  Buttons: `[Confirm overwrite]` (`janitor:confirm_overwrite`), `[Exit Janitor]`.

- Else (missing file or scaffold only) → proceed without prompt.

### Replace semantics (blocker fix)

Today [`file_notes`](../../../services/telegram/bot/janitor_workflow.py) **merges** bullets via `merge_notes_body`. That contradicts "overwrite" copy.

- Add `file_notes(..., *, replace: bool = False)`.
- `replace=False` (default): current merge behavior (unchanged for non-confirm paths if any).
- `replace=True`: write `cleaned_body` only via `write_notes_md` — **no merge**.
- `janitor:confirm_overwrite` calls `file_notes(..., replace=True)` then expand as today.

### Post-promote audit line

Append to promote success message:

`Wrote: content/notes/{folder}/{folder}.notes.md → promoted {folder}.expanded.md`

(use resolved paths from row).

**Done when:** re-filing ep with existing bullets shows confirm; confirm replaces file content; scaffold-only skips confirm.

Optional harness: `dev/scenarios/janitor/overwrite_confirm.yaml` (sandbox episode with pre-seeded bullets).

---

## 5. Status noise — [`janitor_handlers.py`](../../../services/telegram/bot/janitor_handlers.py), [`handlers.py`](../../../services/telegram/bot/handlers.py)

- Clean status: `f"{status_prefix}…"` — **no model slug**.
- `_run_llm_clean`: after posting status, `asyncio.create_task` sleeps 20s then edits to `"Still working…"` if message still exists; cancel task in `finally` after clean completes (avoid editing deleted messages).
- Delete `_OPS_WARN`; typed `/pull`, `/reindex`, `/sync` → short start line (`"Sync started."`) or jump straight to result (match ops panel tone).

**Done when:** no OpenRouter slug in Janitor clean status.

---

## 6. Ops panel — [`settings_handlers.py`](../../../services/telegram/bot/settings_handlers.py) + shared helper

Add **[Ops]** to `settings_keyboard()`.

`set:ops` → edit message to:

```text
[Sync]  [Pull]
[Reindex]  [Restart]
[← Back]
```

Callbacks: `set:op:sync`, `set:op:pull`, `set:op:reindex`, `set:op:restart`.

**In-place status (sync/pull/reindex):**

1. Edit message → `"Sync running… (may take a few minutes)"`
2. `asyncio.to_thread(fn, vault_root)` with **same lock** as [`ops_runner.try_acquire_ops_lock`](../../../services/telegram/bot/ops_runner.py)
3. Edit message → truncated result + `[← Back to Settings]` (`set:menu`)

**Avoid circular imports:** move async wrapper out of `handlers.py` into new **[`services/telegram/bot/ops_telegram.py`](../../../services/telegram/bot/ops_telegram.py)** (thin module):

```python
async def run_ops_job(message, bot_data, vault_root, *, label, fn) -> None
```

Both `handlers._run_ops_command` and `settings_handlers` import from `ops_telegram`.

**Restart special case:** process exits — cannot edit message after. Flow: edit to `"Restarting…"`, schedule `os._exit` like `cmd_restart`, **do not** expect a follow-up edit.

**Done when:** `/settings` → Ops → Sync works; concurrent op shows lock message.

---

## 7. Verification and docs

| Check | Command |
|-------|---------|
| Harness (CI) | `pytest tests/test_harness_scenarios.py -q` |
| Janitor suite | `python dev/mock_telegram_cli.py --stub-llm --suite janitor` |
| Update scenario | [`dev/scenarios/librarian/basic_qa.yaml`](../../../dev/scenarios/librarian/basic_qa.yaml) — expect `Studied` or `Episodes in catalog`, not `Founders vault agent` |
| Docs | [`docs/telegram-vault-agent.md`](../../../docs/telegram-vault-agent.md) command table + menu note; [`docs/janitor.md`](../../../docs/janitor.md) Exit + overwrite confirm |
| Backlog | Move shipped Janitor UX bullets in [`potential-ideas.md`](../../../potential-ideas.md) to § Shipped when done |

---

## Files touched

| File | Change |
|------|--------|
| `__main__.py` | Trim `set_my_commands` |
| `handlers.py` | `/start`, `vault_stats_text`, drop `_OPS_WARN`, delegate ops to `ops_telegram` |
| `janitor_store.py` | `CONFIRM_OVERWRITE` |
| `janitor_handlers.py` | Help, Exit, confirm, status |
| `janitor_workflow.py` | `file_notes(..., replace=)` |
| `settings_handlers.py` | Ops panel callbacks |
| `ops_telegram.py` | **New** — shared async ops + lock |
| `dev/scenarios/librarian/basic_qa.yaml` | Expectations |
| `docs/telegram-vault-agent.md`, `docs/janitor.md` | Operator docs |

---

## What this is NOT

- **Reply keyboard** (persistent bottom button bar that replaces typing) — excluded. Inline keyboards under messages only; user can always type.
- Librarian answer format / post-answer buttons
- Retrieval, agent prompts, `web_search` provider wiring
- Token-by-token streaming (only "Still working…" edit)

---

## Implementation order

1. `ops_telegram.py` + ops panel (unblocks settings without handler cycles)
2. `/start` stats + menu trim
3. Janitor Exit + help slim
4. Overwrite confirm + `replace=True`
5. Status cleanup
6. Scenarios + docs + `potential-ideas.md`

---

## Plan file hygiene

**Archived May 2026** — shipped; see status header above. Historical plan path: `.cursor/plans/archive/telegram_ui_overhaul.plan.md`.
