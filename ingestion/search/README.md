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

## Unified reindex

[`lib/reindex_vault.py`](../lib/reindex_vault.py) runs `build_chunks.py` then `build_embeddings.py` with `cwd` under `ingestion/` and `VAULT_ROOT` set. Used by Janitor promote, `maintain.py` menu 8, and `services/telegram/deploy/sync-and-index.sh`.

```bash
python lib/reindex_vault.py   # from ingestion/
```

## When to rebuild

Run `build_chunks.py` (or `reindex_vault`) after:

- Adding timestamp bullets to `.notes.md`
- Promoting `.expanded.md`
- New or updated posts in `content/posts/`

## Alternatives

Ripgrep over `content/transcripts/`, `content/notes/`, `content/posts/`, or `content/posts/_corpus/all-posts.md` — often enough without rebuilding chunks.
