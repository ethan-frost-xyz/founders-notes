# Manual vault operations

How to run the Founders Notes vault when you are **not** using the Telegram bot on the Mac mini. For day-to-day study and filing, prefer **Janitor + Librarian** on the always-on host ([janitor.md](janitor.md), [services/telegram/README.md](../services/telegram/README.md), [telegram-vault-agent.md](telegram-vault-agent.md)).

## Primary path (Telegram)

| Role | What |
|------|------|
| **Janitor** | Paste bullets → clean → file `.notes.md` → expand → promote → reindex |
| **Librarian** | Q&A over the studied corpus (hybrid parent-tier search) |

Runbook: [services/telegram/README.md](../services/telegram/README.md). Janitor **Promote & reindex** usually refreshes the index on the Mac mini; if that fails or you pushed from the laptop, run `sync-and-index.sh` when the bot is idle — [When to refresh the index](#when-to-refresh-the-index). Model tuning (clean vs expand vs Librarian): [janitor.md § Model tuning playbook](janitor.md#model-tuning-playbook).

## Tactical backup (laptop / Cursor)

Use when batching expand/promote, fixing catalog gaps, or working without Telegram:

| Tool | Purpose |
|------|---------|
| `cd ingestion && python maintain.py` | Interactive menu: coverage, expand backlog, draft review, promote, index rebuild (menu 8), tune |
| `notes/expand_datapoints_llm.py` | OpenRouter → `.expanded.draft.md`; `--promote` → `.expanded.md` |
| `notes/expand_tune.py` | 23-episode prompt A/B sandbox (not production drafts) |
| `pipeline/verify.py` | Regenerate `catalog/gaps.md`; exit 1 on blocking transcript/layout gaps |

See [datapoint-workflow.md](datapoint-workflow.md), [expanded-backfill.md](expanded-backfill.md), [notes-pipeline.md](notes-pipeline.md).

**Do not** duplicate Janitor in `maintain.py` beyond the existing expand/promote/chunk menus — daily filing stays on Telegram.

## Index refresh

Canonical recipe: [`ingestion/lib/reindex_vault.py`](../ingestion/lib/reindex_vault.py) (`reindex_vault`) — runs `search/build_chunks.py` then `search/build_embeddings.py` under `{vault}/ingestion` with `VAULT_ROOT` set.

| Entry | How |
|-------|-----|
| Mac mini | `services/telegram/deploy/sync-and-index.sh` (`git pull` + `lib/reindex_vault.py`) |
| Laptop | `maintain.py` menu **8** (same subprocess recipe) |
| Janitor | **Promote & reindex** calls `janitor_workflow.run_reindex` → `reindex_vault` |

Embeddings require `OPENROUTER_API_KEY` and `OPENROUTER_EMBED_MODEL` in repo `.env` and/or `~/.config/founders-telegram/env`. If keys are missing, step 2 fails with the same message as running `build_embeddings.py` manually.

### When to refresh the index

v0 has **no file lock** between the bot and `sync-and-index.sh`. Run reindex when the Mac mini is **idle** (no active Librarian turn, no Janitor preview/draft in progress). Nightly cron (`install-cron.sh`, default 4:00) is the baseline; add manual sync when content changed on another machine.

| Situation | Action |
|-----------|--------|
| You **promoted on the Mac mini** (Janitor) | Usually automatic — **Promote & reindex** already runs `reindex_vault`. If that step failed, run `sync-and-index.sh` when idle. |
| You **committed notes/expanded on the laptop** and pushed | On Mac mini: `git pull` (or full `sync-and-index.sh`) when idle so Librarian sees new chunks/embeddings. |
| **Stale Librarian answers** after pull | Run `sync-and-index.sh` when idle; `/resume` may warn that the index is newer than the saved session — re-ask the question. |
| **During an active Telegram session** | Avoid `sync-and-index.sh` mid-turn; wait until the bot is idle or use `/clear` / finish Janitor first. |
| **Laptop-only** work (no bot) | `maintain.py` menu **8** or `python lib/reindex_vault.py` from `ingestion/` — no sync script needed unless you also want `git pull`. |

`/resume` does **not** auto-sync (warn-only). Deferred: optional auto-sync on resume — [`potential-ideas.md`](../potential-ideas.md).

From `ingestion/` without the menu:

```bash
python lib/reindex_vault.py
# or
python search/build_chunks.py && python search/build_embeddings.py
```

## Path bootstrap (`VAULT_ROOT`)

| Context | How repo root resolves |
|---------|-------------------------|
| `cd ingestion && python …` | Parent of `ingestion/` from each script’s `_bootstrap.setup_paths(__file__)` |
| Telegram bot / Janitor | `VAULT_ROOT` in `~/.config/founders-telegram/env` (required on Mac mini); else parent of `ingestion/` via [`ingestion/_bootstrap.py`](../ingestion/_bootstrap.py) |
| `pytest` | [`tests/conftest.py`](../tests/conftest.py) calls `setup_ingestion_paths(REPO, include_subpackages=True)` |

Shared helpers: `resolve_vault_root()`, `setup_ingestion_paths()` in [`ingestion/_bootstrap.py`](../ingestion/_bootstrap.py). Telegram code imports them after adding `{vault}/ingestion` to `sys.path` once.

Embeddings apply to **parent-tier** search inside the Telegram agent (`search_vault_parent`), not a repo-wide vector DB. See [retrieval.md](retrieval.md).

## Related

- [retrieval.md](retrieval.md) — chunk index, hybrid parent search, when to consider repo-wide vectors
- [ingestion/README.md](../ingestion/README.md) — full script index
