# Search index

Build and query `catalog/chunks.jsonl` for cross-episode retrieval.

Run from `ingestion/`:

```bash
python search/build_chunks.py
python search/search.py "rockefeller"
```

See [`docs/retrieval.md`](../../docs/retrieval.md).

## Scripts

| Script | Purpose |
|--------|---------|
| `build_chunks.py` | Index transcripts, notes (datapoints), expanded notes, posts → `catalog/chunks.jsonl` |
| `build_embeddings.py` | Parent-tier vectors → `catalog/embeddings.npy` (requires `OPENROUTER_API_KEY` + `OPENROUTER_EMBED_MODEL`) |
| `search.py` | Query chunks; optional ripgrep fallback on corpus |

Parent-tier embeddings power hybrid search inside Telegram `search_vault_parent` only — not a repo-wide vector DB. See [`docs/retrieval.md`](../../docs/retrieval.md).

## When to rebuild

Run `build_chunks.py` after:

- Adding timestamp bullets to `.notes.md`
- Promoting `.expanded.md`
- New or updated posts in `content/posts/`

## Alternatives

Ripgrep over `content/transcripts/`, `content/notes/`, `content/posts/`, or `content/posts/_corpus/all-posts.md` — often enough without rebuilding chunks.
