# X posts import

Sync your X timeline into a local CSV cache, then organize posts into `content/posts/`.

Run from `ingestion/`:

```bash
python x/sync_x_cache.py
python x/organize_posts_from_csv.py
python x/attribute_posts_llm.py --dry-run
python x/attribute_posts_llm.py --apply
```

See [`import/README.md`](../../import/README.md).

## Scripts

| Script | Purpose |
|--------|---------|
| `sync_x_cache.py` | API → append-only `import/x-posts-raw.csv` (`--full` for backfill) |
| `organize_posts_from_csv.py` | CSV → `content/posts/`; writes `catalog/post-mapping-review.jsonl` |
| `attribute_posts_llm.py` | OpenRouter attribution for ambiguous review rows |
| `assign_post_manual.py` | One-off manual post from `--body-file` |
| `dedupe_x_csv.py` | Dedupe CSV by `x_post_id` after overlapping `--full` syncs |

## Environment

| Variable | Purpose |
|----------|---------|
| `X_BEARER_TOKEN`, `X_USERNAME` | `sync_x_cache.py`, manual assign |
| `OPENROUTER_API_KEY` | `attribute_posts_llm.py` |
| `OPENROUTER_ATTRIBUTION_MODEL` | Optional (`--model` overrides) |

## Workflow

1. Post on X → `sync_x_cache.py`
2. `organize_posts_from_csv.py` (auto-maps high-confidence `#N` / `ep. N` tweets; skips native X articles)
3. Optional: `attribute_posts_llm.py` for `post-mapping-review.jsonl`
4. `pipeline/verify.py`

## Downstream

- `search/build_chunks.py` includes post chunks in the index.
