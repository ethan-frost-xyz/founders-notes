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
| Expand | 1 LLM call → standalone query + 5 Founders-tuned variants ([`prompts/query_expand.md`](../ingestion/prompts/query_expand.md)): synonym/reframe, operator mental model, biographical angle, contrasting case, cross-episode pattern; model: `retrieval_model` (falls back to `librarian_model`) |
| Search | 1 batched embed API call + **5 variants searched concurrently** (`ThreadPoolExecutor`); hybrid keyword/cosine per variant (`expanded` + `summary` tiers) |
| Merge | Dedupe by `chunk_id`, RRF across variants, cap ~40 |
| Rerank | 1 LLM call → top 10–12 with synthesis-usefulness scores ([`prompts/rerank_evidence.md`](../ingestion/prompts/rerank_evidence.md): 0–10 bands, conceptual over keyword match); same `retrieval_model` as expand |
| Fallback | Transcript keyword search when max rerank score &lt; 6 or quote-intent detected |
| Synthesize | 1 completion with evidence block — **no** synthesis-time `search_vault` tool loop (v3) |

**Prompt sources:** [`ingestion/prompts/query_expand.md`](../ingestion/prompts/query_expand.md), [`ingestion/prompts/rerank_evidence.md`](../ingestion/prompts/rerank_evidence.md). Synthesis persona: [`AGENTS.md`](../AGENTS.md).

**LLM calls per thematic turn:** 3 (expand, rerank, synthesize) + 1 batched embed request. Use a fast/cheap slug for expand + rerank (`/setmodel retrieval …`); keep `librarian_model` for synthesis only.

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

Same as before — see [repo-agent-guide.md](repo-agent-guide.md). Telegram parent-tier embed index (~1.2k vectors) stays in scope for the bot only.

## Related

- [telegram-vault-agent.md](telegram-vault-agent.md)
- [services/telegram/README.md](../services/telegram/README.md)
