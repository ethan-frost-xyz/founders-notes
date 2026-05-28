---
name: expand_llm split
overview: One PR, one agent session — split expand_llm.py into openrouter_client + expand_validate + expand_promote + expand_run_log, thin expand_llm shim. Sync main first if behind origin.
todos:
  - id: sync-and-verify
    content: "git pull --ff-only if needed; confirm reindex_vault + vault cleanup plans on main"
    status: completed
  - id: split-modules
    content: "Create 4 lib modules, thin expand_llm re-exports, migrate Janitor/X imports, rename count_datapoint_headings"
    status: completed
  - id: test-and-docs
    content: "pytest tests -q + verify.py; update lib/README + vault_cleanup appendix; commit plan with code"
    status: completed
isProject: false
---

# expand_llm split — single PR

**Delivery:** one Agent session, **one commit/PR** on `main`. No multi-PR phases.

## Done when

- New files: `openrouter_client.py`, `expand_validate.py`, `expand_promote.py`, `expand_run_log.py`
- [`expand_llm.py`](ingestion/lib/expand_llm.py) ~200–350 lines (prompts, estimates, progress reporters, re-exports)
- `from expand_llm import …` still works everywhere (shim)
- `attribute_posts_llm` + `janitor_workflow` import `openrouter_client` directly
- `_count_datapoint_headings` → public `count_datapoint_headings` in `expand_validate`; callers updated
- `pytest tests -q` + `cd ingestion && python pipeline/verify.py` green
- This plan + [`ingestion/lib/README.md`](../../../ingestion/lib/README.md) updated; [`vault_cleanup_refactors.plan.md`](vault_cleanup_refactors.plan.md) appendix points here

**Not in scope:** `maintain.py` / `markdown_io` splits, `vault_subprocess.py`, shim removal pass.

---

## Agent checklist (run in order)

### 1. Sync

```bash
git pull --ff-only
```

Skip if `ingestion/lib/reindex_vault.py` already exists.

### 2. Split modules (implementation order avoids circular imports)

| Module | Move here |
|--------|-----------|
| **`openrouter_client.py`** | `OpenRouterCompletion`, `usage_from_response`, retry helpers, `call_openrouter`, `call_openrouter_streaming` |
| **`expand_validate.py`** | `validate_expanded_draft`, `parse_expanded_body`, `count_datapoint_headings` (+ partial helper) |
| **`expand_promote.py`** | `promote_draft`, `write_expanded_draft`, `resolve_draft_path`, `prompt_file_hash` |
| **`expand_run_log.py`** | jsonl log I/O, `log_expand_event`, format/print helpers, `openrouter_completion_log_fields` |
| **`expand_llm.py`** (keep) | prompts, `ExpandEstimate`, dry-run UX, progress reporters; **re-export all public symbols** |

**Import rules:** `openrouter_client` must not import expand_* modules. `expand_promote` may import `expand_validate`.

**Migrate in same diff:**

- [`attribute_posts_llm.py`](ingestion/x/attribute_posts_llm.py) → `openrouter_client`
- [`janitor_workflow.py`](services/telegram/bot/janitor_workflow.py) → `openrouter_client` (after sync)
- [`expand_datapoints_llm.py`](ingestion/notes/expand_datapoints_llm.py), [`expand_tune.py`](ingestion/notes/expand_tune.py) → `count_datapoint_headings` from `expand_validate`

**Keep in `expand_llm`:** `ExpandProgressReporter`, `TerminalExpandProgressReporter` (expand-specific UI).

### 3. Tests

```bash
cd ingestion && .venv/bin/python -m pytest ../tests -q
cd ingestion && .venv/bin/python pipeline/verify.py
```

Update `@patch("expand_llm.call_openrouter")` → `openrouter_client` where the implementation moved. Shim re-exports are fine for other patches.

### 4. Docs + commit

- [`ingestion/lib/README.md`](ingestion/lib/README.md) — module map
- [`vault_cleanup_refactors.plan.md`](vault_cleanup_refactors.plan.md) — appendix superseded
- Commit **this plan** with the code ([`AGENTS.md`](AGENTS.md))

---

## Shim contract (must not break)

All existing `from expand_llm import …` in `maintain.py`, `expand_datapoints.py`, `expand_datapoints_llm.py`, `expand_tune.py`, and tests must keep working via re-exports in `expand_llm.py`.

---

## Deferred

- `vault_subprocess.py` (_python/_tail dedupe)
- Removing shim / migrating every caller off `expand_llm`
