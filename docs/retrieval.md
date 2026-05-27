# Retrieval strategy

## v0 — Cursor + ripgrep (now)

- `@` mention episode folders
- `rg` over `content/`

## v1 — Chunk index (implemented)

- **Index:** `catalog/chunks.jsonl` via `ingestion/search/build_chunks.py`
- **Search:** `ingestion/search/search.py "query"`
- **Chunk id:** `{episode_id}#{section}#{start_line}` — stable for reindexing (`episode_id` is padded, e.g. `ep-0200`)
- **Sections:** `transcript:description`, `transcript:transcript`, `notes:raw_datapoints`, `post:body`, `expanded:*` (e.g. `expanded:expanded_datapoints` when canonical `.expanded.md` exists — from `build_chunks.py` content type `expanded`), etc.
- **source_path:** points at `{folder}.{type}.md` files (see [`docs/episode-id-rules.md`](episode-id-rules.md))
- **Per-chunk metadata** (from file frontmatter + catalog): `title`, `episode_number`, `content_type`, `published_at`, `founders_url`, `source`

Regenerate after bulk import, transcript fetch, or expanded promote:

```bash
cd ingestion && python search/build_chunks.py
```

## v2 — Telegram vault agent tools (planned)

**Not** a repo-wide embedding migration. The [Telegram vault agent](telegram-vault-agent.md) uses **tool-calling** so the model chooses when to search what.

| Mechanism | Where | Scope |
|-----------|--------|--------|
| Keyword search | `search_vault_parent`, `search_transcript` | `catalog/chunks.jsonl` |
| Parent-tier vectors | Inside `search_vault_parent` (hybrid with keyword) | Posts, raw notes, **canonical** `.expanded.md` only — not drafts |
| Full episode load | `load_episode` | Bounded post + notes + expanded for one `ep-NNNN` |
| Transcript search | `search_transcript` | Child-tier transcript sections only when needed |
| Web | `web_search` | **`/web` command only** — never mixed into default vault turns |

Master index: [`.cursor/plans/telegram_rag_bot_v0.plan.md`](../.cursor/plans/telegram_rag_bot_v0.plan.md). SP1 implementation: [`.cursor/plans/telegram_vault_sp1_tools.plan.md`](../.cursor/plans/telegram_vault_sp1_tools.plan.md). Bot stub: [`services/telegram/README.md`](../services/telegram/README.md).

Index refresh on the Mac mini host: `sync-and-index.sh` → `build_chunks.py` + `build_embeddings.py` (parent chunks only; `catalog/embeddings.npy` gitignored).

### Embeddings policy (two scopes)

| Scope | Rule |
|-------|------|
| **Repo / Cursor / maintain.py** | Do **not** add a general-purpose vector DB until grep + `search/search.py` fail your real queries ([AGENTS.md](../AGENTS.md)). |
| **Telegram agent only** | Parent-tier `embeddings.npy` is allowed **inside** `search_vault_parent` — hybrid retrieval as one tool, not the whole product. |

Re-embed from `chunks.jsonl` + on-disk markdown when embed models change. **Do not** store-only vectors without plain-text sources in git.

### What v1 preserves for agent tools

| Field | Use |
|-------|-----|
| `chunk_id` | Dedup across keyword ∪ semantic hits |
| `source_path` + `start_line` | Citations back to git files |
| `excerpt` | Tool result text + embed input |
| `section` | Source priority (expanded > notes > post > transcript) |
| `title`, `episode_number`, `content_type`, `published_at` | Display + `list_episode_ids` |

## Graduate to repo-wide embeddings when

Consider a **general** vector layer (beyond the Telegram parent index) only when **all** are true:

1. Post corpus is largely complete (today: **187 / 417** numbered posts imported; target ~400+)
2. `search/search.py` + `_corpus/all-posts.md` + vault agent tools routinely miss paraphrased or thematic queries
3. You want “find similar ideas” across episodes, not exact keyword match

Until then, v1 chunks + planned agent tools are sufficient for Cursor and Telegram.

## Open questions (agent / retrieval)

Locked in master plan for v0; revisit in SP3.1 / SP6:

1. **Web provider** — v0 stub (`not configured`); Tavily or Brave when `WEB_SEARCH_API_KEY` is wired.
2. **`load_episode`** — all on-disk sections, truncated; expanded sections ordered first when present.
3. **`/resume` + stale index** — v0 warn-only; auto-sync deferred.
4. **Hybrid quality** — optional golden query set in SP6 (MRR@8 vs keyword-only).
