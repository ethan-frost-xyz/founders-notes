# Manual vault operations

How to run the Founders Notes vault when you are **not** using the Telegram bot on the Mac mini. For day-to-day study and filing, prefer **Janitor + Librarian** on the always-on host ([janitor.md](janitor.md), [services/telegram/README.md](../services/telegram/README.md), [telegram-vault-agent.md](telegram-vault-agent.md)).

## Primary path (Telegram)

| Role | What |
|------|------|
| **Janitor** | Paste bullets → clean → file `.notes.md` → expand → promote → reindex |
| **Librarian** | Q&A over the studied corpus (hybrid parent-tier search) |

Runbook: [services/telegram/README.md](../services/telegram/README.md). After promote on the Mac mini, refresh the index with `services/telegram/deploy/sync-and-index.sh` (`git pull` + `build_chunks.py` + `build_embeddings.py`). Requires `OPENROUTER_API_KEY` and `OPENROUTER_EMBED_MODEL` for the embedding step.

## Tactical backup (laptop / Cursor)

Use when batching expand/promote, fixing catalog gaps, or working without Telegram:

| Tool | Purpose |
|------|---------|
| `cd ingestion && python maintain.py` | Interactive menu: coverage, expand backlog, draft review, promote, chunk rebuild, tune |
| `notes/expand_datapoints_llm.py` | OpenRouter → `.expanded.draft.md`; `--promote` → `.expanded.md` |
| `notes/expand_tune.py` | 23-episode prompt A/B sandbox (not production drafts) |
| `pipeline/verify.py` | Regenerate `catalog/gaps.md`; exit 1 on blocking transcript/layout gaps |

See [datapoint-workflow.md](datapoint-workflow.md), [expanded-backfill.md](expanded-backfill.md), [notes-pipeline.md](notes-pipeline.md).

**Do not** duplicate Janitor in `maintain.py` beyond the existing expand/promote/chunk menus — daily filing stays on Telegram.

## Index refresh

Canonical on the Mac mini: `sync-and-index.sh` (chunks + parent-tier embeddings).

From `ingestion/` on any machine:

```bash
python search/build_chunks.py
python search/build_embeddings.py   # needs OPENROUTER_API_KEY + OPENROUTER_EMBED_MODEL
```

`maintain.py` menu **8** currently rebuilds **chunks only**; run `build_embeddings.py` separately when the Telegram agent host needs updated vectors. PR3 of [vault cleanup](../.cursor/plans/vault_cleanup_refactors.plan.md) will unify this recipe.

Embeddings apply to **parent-tier** search inside the Telegram agent (`search_vault_parent`), not a repo-wide vector DB. See [retrieval.md](retrieval.md).

## Related

- [retrieval.md](retrieval.md) — chunk index, hybrid parent search, when to consider repo-wide vectors
- [ingestion/README.md](../ingestion/README.md) — full script index
