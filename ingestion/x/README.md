# X posts import

Sync your X timeline into a local CSV cache, then attribute posts into `content/posts/`.

Run from `ingestion/`:

```bash
python x/x_posts_sync.py
python x/x_posts_attribute.py
python x/x_posts_status.py
```

See [`import/README.md`](../../import/README.md).

## Scripts

| Script | Purpose |
|--------|---------|
| `x_posts_sync.py` | API → `import/x-posts-raw.csv` + `catalog/x-posts-pending.jsonl` (windowed fetch; `--backfill` for full timeline) |
| `x_posts_attribute.py` | Pending queue → `content/posts/` (default); `--rebuild` for full CSV scan |
| `x_posts_status.py` | Zero-API status: vault max ep, pending count, last sync |
| `assign_post_manual.py` | One-off manual post from `--body-file` |
| `sync_x_cache.py` | **Deprecated** — use `x_posts_sync.py` |
| `organize_posts_from_csv.py` | **Deprecated** — use `x_posts_attribute.py --rebuild` |

## Environment

| Variable | Purpose |
|----------|---------|
| `X_BEARER_TOKEN`, `X_USERNAME` | `x_posts_sync.py`, `assign_post_manual.py` |
| `OPENROUTER_API_KEY` | `x_posts_attribute.py --llm-review` |
| `X_ATTRIBUTION_MODEL` | Optional LLM model override (default `deepseek/deepseek-v4-flash`) |

On the Mac mini, set `X_BEARER_TOKEN` in `~/.config/founders-telegram/env` (see [`docs/operations.md`](../../docs/operations.md)).

## Workflow

1. Post on X (include `#N` episode marker when possible) → `x_posts_sync.py`
2. `x_posts_attribute.py` (rules → chronological gap-fill → optional LLM for review band)
3. `pipeline/verify.py`

Ambiguous rows land in `catalog/post-mapping-review.jsonl` or `content/posts/_other/` — fix via `assign_post_manual.py` or re-run attribute after editing.

**Mac mini weekly cron:** `services/telegram/deploy/install-x-posts-cron.sh`

## Downstream

- `search/build_chunks.py` includes post chunks in the index.
