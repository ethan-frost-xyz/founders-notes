# Retrieval strategy

## v0 — Cursor + ripgrep (now)

- `@` mention episode folders
- `rg` over `content/`

## v1 — Chunk index (implemented)

- **Index:** `catalog/chunks.jsonl` via `ingestion/search/build_chunks.py`
- **Search:** `ingestion/search/search.py "query"` (keyword CLI; unchanged)
- **Studied-only:** Episodes without timestamp bullets in `.notes.md` are excluded from the index entirely.
- **Parent search tiers:** `expanded:*` datapoints + `summary:episode` (routing layer). **`notes:*` and `post:*` are not indexed** — posts remain available via `load_episode`.
- **Transcripts:** `transcript:*` chunks for studied episodes only; used by orchestrator fallback, not default thematic search.

Regenerate after bulk import, expanded promote, or summary rebuild:

```bash
cd ingestion
python search/build_chunks.py
python search/build_summaries.py   # LLM summaries; incremental by content hash
python search/build_chunks.py      # pick up summary:* chunks
python search/build_embeddings.py
```

Or: `python lib/reindex_vault.py` / Telegram `/reindex` (runs all steps above).

## v3 — Telegram Librarian orchestrator (implemented)

**Scope:** Telegram Librarian only. Python orchestrator in `ingestion/lib/retrieval_orchestrator.py`; thin adapter `services/telegram/bot/retrieval.py`.

| Step | What |
|------|------|
| Intent | Rules-based (`meta` / `follow_up` / `thematic`) — no extra LLM |
| Expand | 1 LLM call → standalone query + 5 variants (`prompts/query_expand.md`) |
| Search | 1 batched embed API call + hybrid keyword/cosine per variant (`expanded` + `summary` tiers) |
| Merge | Dedupe by `chunk_id`, RRF across variants, cap ~40 |
| Rerank | 1 LLM call → top 10–12 with scores (`ingestion/lib/rerank_llm.py`) |
| Fallback | Transcript keyword search when max rerank score &lt; 6 or quote-intent detected |
| Synthesize | 1 DeepSeek completion with evidence block — **no** `search_vault_parent` tool loop |

**LLM calls per thematic turn:** 3 (expand, rerank, synthesize) + 1 batched embed request.

**Citable sources in synthesis:** `expanded:*` and `transcript:*` only. Summaries inform routing but are stripped from the evidence block.

**Defense in depth:** `episode_is_studied()` in `search_retrieval.py` filters at search time even if the index is stale.

### Embeddings

- Structured embed text per chunk type (`structured_embed_text()` in `search_retrieval.py`)
- Model slug: `runtime.json` `/setmodel embed`
- In-process matrix cache (invalidate on `embeddings.npy` mtime)
- Query embed LRU cache

## v2 — Legacy tool-calling path (superseded for Librarian)

`search_vault_parent` / `search_transcript` remain in `services/telegram/bot/tools/vault.py` for tests and CLI harnesses. The live Librarian agent uses the orchestrator instead.

## Graduate to repo-wide embeddings when

Same as before — see [AGENTS.md](../AGENTS.md). Telegram parent-tier embed index (~1.2k vectors) stays in scope for the bot only.

## Related

- [telegram-vault-agent.md](telegram-vault-agent.md)
- [services/telegram/README.md](../services/telegram/README.md)
