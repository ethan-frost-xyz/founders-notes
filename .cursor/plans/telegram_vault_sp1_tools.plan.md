---
name: Telegram Vault SP1 — Tools + indexes
overview: "Vault search backends and parent-tier embeddings. No Telegram, no agent loop. Prerequisite for SP2."
todos:
  - id: search-retrieval
    content: ingestion/lib/search_retrieval.py — parent/transcript filters, keyword, vector, RRF hybrid, load_chunk_source_excerpt
    status: pending
  - id: build-embeddings
    content: ingestion/search/build_embeddings.py — incremental parent-only vectors + manifest
    status: pending
  - id: vault-tools
    content: services/telegram/bot/tools/vault.py — JSON evidence functions (no OpenRouter)
    status: pending
  - id: fixture-tests
    content: ingestion/fixtures/chunks_parent_slice.jsonl + ingestion/tests/test_search_retrieval.py for filters, hybrid, embed skip
    status: pending
  - id: gitignore
    content: Gitignore catalog/embeddings.npy and catalog/embeddings-manifest.jsonl
    status: pending
isProject: false
---

# SP1 — Vault tools + indexes

**Master (contracts only):** [telegram_rag_bot_v0.plan.md](telegram_rag_bot_v0.plan.md)  
**Next after this:** [telegram_vault_sp2_agent.plan.md](telegram_vault_sp2_agent.plan.md)  
**Branch:** `feature/telegram-vault-bot` · **Commit:** SP1 only (one focused commit)

## Agent handoff

Read **this file only** for implementation. Skim master § Shared contracts for evidence JSON shape. Do **not** implement Telegram, `agent.py`, or `vault_agent.md`.

**Prerequisites:** `catalog/chunks.jsonl` exists (`ingestion/search/build_chunks.py`).  
**Out of scope:** `python-telegram-bot`, OpenRouter chat loop, `launchd`, web search provider.

## Goal

Tool backends + indexes testable without API keys. Pure Python functions in `vault.py` return JSON-serializable evidence.

## Deliverables

| Path | Purpose |
|------|---------|
| [`ingestion/lib/search_retrieval.py`](../../ingestion/lib/search_retrieval.py) | `is_parent_chunk`, `is_transcript_chunk`, keyword search, vector search, `load_chunk_source_excerpt`, `hybrid_search_parent(query, k)` |
| [`ingestion/search/build_embeddings.py`](../../ingestion/search/build_embeddings.py) | Incremental parent-only vectors |
| [`services/telegram/bot/tools/vault.py`](../../services/telegram/bot/tools/vault.py) | `search_vault_parent`, `search_transcript`, `load_episode`, `list_episode_ids` |
| [`ingestion/fixtures/chunks_parent_slice.jsonl`](../../ingestion/fixtures/chunks_parent_slice.jsonl) | Synthetic rows incl. one `expanded:*` (no live corpus dependency) |
| [`ingestion/tests/test_search_retrieval.py`](../../ingestion/tests/test_search_retrieval.py) | pytest — parent filter, hybrid ordering, embed incremental skip |
| `.gitignore` | `catalog/embeddings.npy`, `catalog/embeddings-manifest.jsonl` |

**Dependency:** `numpy` for embeddings (add to `ingestion/requirements.txt` if missing).

## Acceptance criteria

| Item | Spec |
|------|------|
| `is_parent_chunk` | `section` matches `^(post\|notes\|expanded):` |
| `is_transcript_chunk` | `section` matches `^transcript:` |
| Keyword leg | Reuse/extend [`search.py`](../../ingestion/search/search.py) `search_chunks` — case-insensitive substring + hit-count rank (**not** BM25 in v0) |
| Vector leg | Cosine similarity over parent-tier rows in `catalog/embeddings.npy` aligned to `chunk_id` |
| Hybrid merge | **RRF** on keyword rank + cosine rank; dedupe by `chunk_id`; optional score boost: `expanded:*` > `notes:*` > `post:*` (+0.1 tier steps) |
| Evidence JSON | Every hit: `episode_id` (= chunk `id`), `chunk_id`, `section`, `source_path`, `start_line`, `excerpt`, metadata when present |
| `list_episode_ids` | Fuzzy match on `catalog/episodes.jsonl` `title` + numeric episode number → `ep-NNNN` |
| `load_episode` | All on-disk sections truncated; when `.expanded.md` exists, **expanded sections first** in combined blob (~30k char cap total) |

### Evidence shape (implement against master § Shared contracts — canonical)

Reproduced here for the implementing agent:

```json
{
  "hits": [
    {
      "chunk_id": "ep-0022#notes:raw_datapoints#12",
      "episode_id": "ep-0022",
      "section": "notes:raw_datapoints",
      "title": "...",
      "source_path": "content/notes/.../....notes.md",
      "start_line": 42,
      "excerpt": "...",
      "founders_url": "https://..."
    }
  ],
  "meta": { "query": "...", "tier": "parent", "k": 8 }
}
```

`load_episode` returns `{ "episode_id": "...", "sections": { "post": "...", "notes": "...", "expanded": "..." } }` — only sections present on disk; expanded sections listed first; truncated to ~30k chars total.

## Tool functions (v0)

| Function | Tier | Notes |
|----------|------|-------|
| `search_vault_parent` | post, notes, expanded | Hybrid keyword ∪ embed; **no** separate semantic tool |
| `search_transcript` | transcript child chunks | Keyword only |
| `load_episode` | per-type files | Bounded chars |
| `list_episode_ids` | catalog | Resolve “episode 22”, title fuzzy match |

## Verify before commit

```bash
cd ingestion && pytest -q
python pipeline/verify.py
# Spot-check hybrid on fixture (no full corpus required in CI)
```

## Commit message

`feat(telegram): SP1 vault search tools and parent-tier embeddings`
