---
name: Librarian Quality
overview: "Two focused improvements to the Telegram Librarian: (1) D1 — enrich the ambiguous-episode error with a `candidates` list so the model can self-correct in one turn, and (2) streaming synthesis replies to Telegram, off by default, toggleable from `/settings`. Clean up passed-on Librarian backlog noise in potential-ideas.md when shipping."
todos:
  - id: d1-candidates
    content: "D1: augment load_episode ambiguous error with candidates list in vault.py; add unit test fixture in test_vault_agent.py"
    status: pending
  - id: streaming-runtime
    content: "Streaming: add stream_replies bool to runtime_settings.py (RUNTIME_KEY, _resolve_bool, effective_stream_replies, set_stream_replies, format_settings_summary line)"
    status: pending
  - id: streaming-agent
    content: "Streaming: add on_chunk callback to run_turn in agent.py; branch final synthesis step on stream=True when on_chunk is provided"
    status: pending
  - id: streaming-handler
    content: "Streaming: wire on_chunk in handlers.py with throttled edit-message live preview; delete stream_msg before final reply_text_chunked"
    status: pending
  - id: streaming-settings
    content: "Streaming: add Stream replies toggle button in settings_handlers.py"
    status: pending
  - id: potential-ideas-hygiene
    content: "Remove passed-on Librarian quality bullets from potential-ideas.md; move shipped D1 + streaming to Shipped (reference)"
    status: pending
  - id: plan-commit
    content: Commit telegram_librarian_quality.plan.md with the code and potential-ideas.md changes per AGENTS.md
    status: pending
isProject: false
---

# Librarian Quality Plan

## Scope

Two implementation tasks, independent of each other:

- **D1** — `load_episode` disambiguation: return `candidates` in ambiguous error
- **Streaming** — synthesis turn token streaming, off by default, `/settings` toggle

**Docs hygiene (same PR):** prune the Librarian quality cluster in [`potential-ideas.md`](potential-ideas.md) — remove deferred items we explicitly passed on; after ship, record D1 + streaming under **Shipped (reference)** and drop the empty **Next** subsection.

Passed on (remove from `potential-ideas.md`, do not implement): D2, D3, D5, D6, D7, D9, D10, MRR@8.

---

## Task 1 — D1: candidates in ambiguous error

### What changes

**[`services/telegram/bot/tools/vault.py`](services/telegram/bot/tools/vault.py)**

In `load_episode` (L93–152), after the `resolve_episode_ref` fallback returns `None`, augment the error dict with a `candidates` list:

```python
# current (L102–107):
resolved = resolve_episode_ref(episode_id.strip())
if resolved:
    row = lookup_catalog_row(rows, resolved)
if row is None:
    return {"error": f"Episode not in catalog: {episode_id}"}

# new:
if row is None:
    candidates_result = list_episode_ids(episode_id.strip(), limit=5)
    return {
        "error": f"Episode not in catalog: {episode_id}",
        "candidates": candidates_result.get("episodes", []),
    }
```

The model already sees the `candidates` payload as a tool result — no prompt changes needed.

### Test

**[`tests/test_vault_agent.py`](tests/test_vault_agent.py)** — add one fixture:

```python
result = execute_tool("load_episode", {"episode_id": "Henry Ford"})
assert "error" in result
assert isinstance(result.get("candidates"), list)
assert len(result["candidates"]) > 0
```

---

## Task 2 — Streaming synthesis replies

### Overview

The synthesis final step streams token deltas via an `on_chunk` callback (same pattern as `on_tool_start`). Streaming is disabled by default; enabled via a `/settings` toggle persisted in `runtime.json`.

```
on_chunk (sync thread) ──call_soon_threadsafe──> _schedule_chunk_update (async)
                                                       ↓ throttled (≥500ms)
                                               edit_message_text(accumulated)
```

### Files and changes

**1. [`services/telegram/bot/runtime_settings.py`](services/telegram/bot/runtime_settings.py)**

- Add `RUNTIME_KEY_STREAM_REPLIES = "stream_replies"` (line ~25)
- Add to `_SEED_ENV_MAP`: `RUNTIME_KEY_STREAM_REPLIES: "TELEGRAM_STREAM_REPLIES"`
- Add `_resolve_bool(runtime_key, env_key, default) -> tuple[bool, str]` helper (analogous to `_resolve_float`)
- Add `effective_stream_replies() -> tuple[bool, str]` — defaults to `False`
- Add `set_stream_replies(enabled: bool) -> bool` setter
- Add line to `format_settings_summary`: `f"stream_replies: {stream} ({stream_src})"`

**2. [`services/telegram/bot/agent.py`](services/telegram/bot/agent.py)**

Add `on_chunk: Callable[[str], None] | None = None` to `run_turn` signature (L200–208).

On the final synthesis step only (`is_final=True`), branch on `on_chunk`:

```python
if is_final:
    if on_chunk is not None:
        full_text = ""
        for chunk in completion_fn(**request, stream=True):
            delta = (chunk.choices[0].delta.content or "")
            if delta:
                full_text += delta
                on_chunk(delta)
        text = full_text.strip() or fallback_msg
    else:
        response = completion_fn(**request)   # existing path
        text = (response.choices[0].message.content or "").strip() or fallback_msg
    return TurnResult(content=text, tool_trace=trace, steps=step + 1)
```

Non-final tool-call steps are unchanged.

**3. [`services/telegram/bot/handlers.py`](services/telegram/bot/handlers.py)**

In the Librarian turn handler (around L355–406):

```python
from runtime_settings import effective_stream_replies

stream_enabled, _ = effective_stream_replies()
stream_msg: Any | None = None
accumulated_text = ""
last_edit_at = 0.0

async def _flush_stream(text: str) -> None:
    nonlocal stream_msg, last_edit_at
    now = asyncio.get_event_loop().time()
    if stream_msg is None:
        stream_msg = await update.message.reply_text(text or "…")
        last_edit_at = now
    elif now - last_edit_at >= 0.5:
        try:
            await stream_msg.edit_text(text or "…")
        except Exception:
            pass
        last_edit_at = now

def on_chunk(delta: str) -> None:
    nonlocal accumulated_text
    accumulated_text += delta
    loop.call_soon_threadsafe(
        lambda t=accumulated_text: asyncio.create_task(_flush_stream(t))
    )

result = await asyncio.to_thread(
    agent.run_turn, ...,
    on_chunk=on_chunk if stream_enabled else None,
)

# Final flush / replace with reply_text_chunked
if stream_msg is not None:
    try:
        await stream_msg.delete()
    except Exception:
        pass
await reply_text_chunked(update.message, result.content)
```

The final `reply_text_chunked` always fires — streaming is a live preview only; the canonical send path is unchanged.

**4. [`services/telegram/bot/settings_handlers.py`](services/telegram/bot/settings_handlers.py)**

Add a toggle button to the settings panel. Import `effective_stream_replies`, `set_stream_replies`. Add a callback handler: toggle `stream_replies` and re-render the settings panel. Label: `Stream replies: ON` / `Stream replies: OFF`.

---

## Task 3 — `potential-ideas.md` hygiene

Edit [`potential-ideas.md`](potential-ideas.md) in the **same commit** as the code (not a follow-up).

### Remove from **Next → Librarian quality** (passed on — noise)

Delete these bullets entirely (no replacement in Next):

| ID | Bullet topic |
|----|----------------|
| D2 | Stricter tool schema |
| D3 | Stricter episode resolution |
| D5 | Shared episode ref helper in `ingestion/lib` |
| D6 | `tool_trace` resolved_from |
| D7 | Fuzzy `resolve_episode_ref` tuning |
| D9 | `RUN_LIVE_HARNESS=1` in CI |
| D10 | Ambiguous guest harness |
| — | Scenarios / MRR@8 |

Also remove the subsection intro line that only references the deferred table (`_From archived fix_bare_episode_refs…_`) unless you keep a shorter pointer under Shipped.

### After D1 + streaming ship

1. **Delete** the whole `### Librarian quality — telegram_librarian_quality.plan.md` block from **Next** (no remaining open items in that cluster).
2. **Add** under **Shipped (reference)** (two bullets, Jun 2026):
   - **`load_episode` disambiguation (D1)** — ambiguous refs return `candidates` from `list_episode_ids`; plan [`.cursor/plans/archive/telegram_librarian_quality.plan.md`](.cursor/plans/archive/telegram_librarian_quality.plan.md) after archive.
   - **Librarian reply streaming** — optional synthesis token streaming via `/settings` → `stream_replies` in `runtime.json`; default off; same plan link.

3. **Archive** this plan file to [`.cursor/plans/archive/telegram_librarian_quality.plan.md`](.cursor/plans/archive/telegram_librarian_quality.plan.md) per AGENTS.md.

Do **not** re-add skipped items elsewhere in the doc unless you have a new reason to track them.

---

## CI / tests

- `pytest tests/test_vault_agent.py tests/test_harness_scenarios.py -q` — existing suite + new D1 fixture
- Streaming is not exercised in CI (no live bot); manual smoke on Mac mini: send a Q&A message with setting toggled on and verify partial edits arrive before final reply
- No new YAML scenarios needed

## Commit

Commit [`.cursor/plans/telegram_librarian_quality.plan.md`](.cursor/plans/telegram_librarian_quality.plan.md) (then archive), code, and [`potential-ideas.md`](potential-ideas.md) in the same commit per AGENTS.md.
