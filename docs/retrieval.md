# Retrieval strategy

## v0 — Cursor + ripgrep (now)

- `@` mention episode folders
- `rg` over `content/`

## v1 — Chunk index (implemented)

- **Index:** `catalog/chunks.jsonl` via `ingestion/build_chunks.py`
- **Search:** `ingestion/search.py "query"`
- **Chunk id:** `{episode_id}#{section}#{start_line}` — stable for reindexing (`episode_id` is padded, e.g. `ep-0200`)
- **Sections:** `transcript:description`, `transcript:transcript`, `notes:raw_datapoints`, `post:body`, etc.
- **source_path:** points at `{folder}.{type}.md` files (see [`docs/episode-id-rules.md`](episode-id-rules.md))

Regenerate after bulk import or transcript fetch:

```bash
cd ingestion && python build_chunks.py
```

## v2 — Embeddings (graduate when)

Consider embeddings when **all** are true:

1. Post corpus is largely complete (today: **187 / 417** numbered posts imported; target ~400+)
2. `search.py` + `_corpus/all-posts.md` routinely miss paraphrased or thematic queries
3. You want “find similar ideas” across episodes, not exact keyword match

### What v1 preserves for migration

| Field | Use in v2 |
|-------|-----------|
| `chunk_id` | Vector metadata / dedup |
| `source_path` + `start_line` | Citation back to git files |
| `excerpt` | Initial embedding text (or re-read from file) |
| `section` | Filter (notes vs transcript vs post) |

**Do not** store-only vectors without plain-text sources in git. Re-embed from `chunks.jsonl` + on-disk markdown when models change.

### Suggested v2 stack (later)

- Embed `excerpt` (or full section) with one provider
- Store ids in a local sqlite or sidecar JSONL with vectors
- Query → top-k chunk_ids → load full context from `content/` for LLM prompts

No vector DB is required until v1 search fails your real queries.
