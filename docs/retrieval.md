# Retrieval strategy

## Design rationale

The Telegram **Librarian** is a study partner over your vault—not a ranked excerpt dump. **v4** gives the model cold-start retrieval: it drives search via tools (`search_vault`, `search_vault_many`, `search_transcript`, `load_episode`, `list_episode_ids`) with no mandatory pre-pass. Retrieval **internals** (expand → hybrid search → rerank) live in v3 and are invoked per tool call.

Historical motivation for moving off pre-scripted RAG: [`.cursor/plans/archive/legacy/AGENTIC-VISION-BRIEF.md`](../.cursor/plans/archive/legacy/AGENTIC-VISION-BRIEF.md).

## v0 — Cursor + ripgrep (local workflow)

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

## v3 — Telegram Librarian orchestrator (retrieval core; superseded as turn driver)

**Scope:** Retrieval **internals** only — expand → hybrid search → RRF → rerank → transcript fallback in `services/telegram/lib/retrieval/orchestrator.py` (`retrieve_core`). The live Librarian no longer runs this as a mandatory pre-pass; see v4.

| Step | What |
|------|------|
| Expand | 1 LLM call → standalone query + 5 Founders-tuned variants ([`prompts/query_expand.md`](../ingestion/prompts/query_expand.md)); model: `retrieval_model` |
| Search | Batched embed + **variants searched concurrently**; hybrid keyword/cosine (`expanded` + `summary` tiers) |
| Merge | Dedupe by `chunk_id`, RRF across variants, cap ~40 |
| Rerank | 1 LLM call → top chunks with synthesis-usefulness scores ([`prompts/rerank_evidence.md`](../ingestion/prompts/rerank_evidence.md)); chunk IDs not in the candidate pool are ignored (unranked candidates keep score 0) |
| Fallback | Transcript keyword search when max rerank score &lt; 6 or quote-intent detected |

`search_vault_many` sub-queries skip LLM expansion (`expand_variants=0`) — the librarian model already decomposed the question.

## v4 — Agentic Librarian loop (implemented)

**Scope:** Telegram Librarian turn driver in `services/telegram/bot/agent.py`; tool adapters in `services/telegram/bot/search_turn.py`.

| What | Detail |
|------|--------|
| Cold start | No pre-retrieved evidence; the `librarian_model` drives retrieval via tools |
| Toolbox | `search_vault`, `search_vault_many`, `search_transcript`, `list_episode_ids`, `load_episode` |
| Loop | Model calls tools until it answers or **6 tool-call rounds** (cap forces final synthesis with honesty nudge) |
| Models | `librarian_model` — loop + synthesis; `retrieval_model` — expand + rerank inside each search |
| Trace | Per-round `tool_trace` + `trace_summary` (queries, episode_ids, scores, stop reason) |

**Prompt sources:** [`ingestion/prompts/query_expand.md`](../ingestion/prompts/query_expand.md), [`ingestion/prompts/rerank_evidence.md`](../ingestion/prompts/rerank_evidence.md). Persona + composition heuristics: [`AGENTS.md`](../AGENTS.md).

**Citable sources in synthesis:** `expanded:*` and `transcript:*` only. Summaries inform routing but are stripped from tool results.

**Defense in depth:** `episode_is_studied()` in `ingestion/lib/search_studied.py` filters at search time even if the index is stale.

### Embeddings

- Structured embed text per chunk type (`structured_embed_text()` in `ingestion/lib/search_embeddings.py`)
- Model slug: `runtime.json` `/setmodel embed`
- In-process matrix cache (invalidate on `embeddings.npy` mtime)
- Query embed LRU cache

## Module layout

Retrieval implementation lives under `ingestion/lib/search_*.py`:

| Module | Role |
|--------|------|
| `search_studied.py` | Studied-episode cache (timestamp bullets in notes) |
| `search_chunk_index.py` | `chunks.jsonl` load + parent/transcript tier split |
| `search_embeddings.py` | Embedding matrix store + query embed API |
| `search_hybrid.py` | Keyword + vector RRF hybrid search |
| `search_cache.py` | Cache invalidation hook for catalog writes |
| `search_retrieval.py` | Facade + `search_parent_evidence` / `search_transcript_evidence` |

Index-quality tests call `search_parent_evidence` / `search_transcript_evidence` via [`tests/search_test_helpers.py`](../tests/search_test_helpers.py). The live Librarian uses `search_vault` / `search_vault_many` (orchestrator-backed) instead. [`vault.py`](../services/telegram/bot/tools/vault.py) exposes episode tools only (`load_episode`, `list_episode_ids`).

## Graduate to repo-wide embeddings when

Same as before — see [repo-agent-guide.md](repo-agent-guide.md). Telegram parent-tier embed index (~1.2k vectors) stays in scope for the bot only.

## Related

- [telegram-vault-agent.md](telegram-vault-agent.md)
- [services/telegram/README.md](../services/telegram/README.md)
