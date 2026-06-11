# Ingestion library modules

Shared Python modules imported by CLI scripts under `pipeline/`, `notes/`, `x/`, etc. Not run directly.

Run scripts from `ingestion/`; each script calls `_bootstrap.setup_paths(__file__)`. Telegram and tests use `resolve_vault_root()` / `setup_ingestion_paths()` from [`../_bootstrap.py`](../_bootstrap.py) (see [`docs/operations.md`](../../docs/operations.md)).

## Module map

| Module | Role |
|--------|------|
| `paths.py` | Repo root, ingestion dir, content paths, `folder_name`, file path helpers |
| `catalog.py` | `load_catalog`, `save_catalog`, `resolve_catalog_row`, `load_jsonl`, `clear_jsonl_cache` |
| `markdown_io.py` | Frontmatter read/write, timestamp datapoint detection, notes/post/transcript writers |
| `episode_ids.py` | `format_episode_id`, `make_id`, padded id parsing |
| `colossus.py` | Colossus login, session, HTML extractors |
| `sitemap.py` | `iter_sitemap_episodes`, slug → episode number |
| `layout.py` | Filesystem layout and catalog id consistency (used by `pipeline/verify.py`) |
| `gaps_report.py` | `catalog/gaps.md` generation and Phase 2 coverage stats |
| `cli_args.py` | Shared `--id ep-NNNN` argparse helpers |
| `openrouter_client.py` | OpenRouter sync/streaming completions, retries (expand, Janitor clean, X attribution) |
| `expand_validate.py` | Parse and validate `.expanded.draft.md` bodies |
| `expand_promote.py` | Write drafts, promote to `.expanded.md` |
| `expand_run_log.py` | `catalog/expand-run.jsonl` logging and CLI progress output |
| `expand_prompt.py` | Prompt templates, cost estimates, progress reporters |
| `expanded_timestamp_lint.py` | Timestamp meta validation on expanded drafts (used by promote) |
| `rss_duration.py` | Parse RSS `itunes:duration` → seconds for catalog backfill |
| `timestamp_estimate.py` | Estimate `MM:00` for lost-timestamp note bullets from transcript position |
| `search_retrieval.py` | Parent/transcript chunk filters, keyword + hybrid RRF (Telegram tools) |
| `openrouter_pricing.py` | OpenRouter model pricing helpers for expand cost estimates |
| `reindex_vault.py` | Subprocess orchestrator: `build_chunks.py` + `build_embeddings.py` (Janitor, maintain menu 8, `sync-and-index.sh`) |
| `vault_subprocess.py` | Shared `python_executable` / `tail_output` for reindex and Janitor expand subprocesses |
| `x_sync_fetch.py` | Windowed X timeline fetch (`since_id`, catch-up expansion) |
| `x_posts_csv.py` | X CSV cache I/O, tweet → row conversion |
| `x_posts_pending.py` | Pending attribution queue (`catalog/x-posts-pending.jsonl`) |
| `x_posts_chrono.py` | Chronological gap-fill for recap posts without `#N` |
| `x_post_attribution.py` | Attribution cascade + vault writes, corpus regen |
| `x_posts_match.py` | Episode attribution scoring |
| `x_posts_threads.py` | Thread grouping, reply filters, article skip |
