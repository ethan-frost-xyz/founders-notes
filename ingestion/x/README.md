# X posts import

Sync your X timeline into a local CSV cache, then organize posts into `content/posts/`.

Run from `ingestion/`:

```bash
python x/sync_x_cache.py
python x/organize_posts_from_csv.py
```

See [`import/README.md`](../../import/README.md).

## Scripts

| Script | Purpose |
|--------|---------|
| `sync_x_cache.py` | API → append-only `import/x-posts-raw.csv` (`--full` for backfill) |
| `organize_posts_from_csv.py` | CSV → `content/posts/`; writes `catalog/post-mapping-review.jsonl` for low-confidence rows |
| `assign_post_manual.py` | One-off manual post from `--body-file` |

## Environment

| Variable | Purpose |
|----------|---------|
| `X_BEARER_TOKEN`, `X_USERNAME` | `sync_x_cache.py`, `assign_post_manual.py` |

## Workflow

1. Post on X (include `#N` episode marker) → `sync_x_cache.py`
2. `organize_posts_from_csv.py` (auto-maps high-confidence `#N` / `ep. N` tweets; skips native X articles)
3. `pipeline/verify.py`

Ambiguous rows land in `catalog/post-mapping-review.jsonl` or `content/posts/_other/` — fix attribution manually or via `assign_post_manual.py`.

## Downstream

- `search/build_chunks.py` includes post chunks in the index.
