# Ingestion library modules

Shared Python modules imported by CLI scripts under `pipeline/`, `notes/`, `x/`, etc. Not run directly.

Run scripts from `ingestion/`; each script bootstraps `ingestion/` and `ingestion/lib/` onto `sys.path`.

## Module map

| Module | Role |
|--------|------|
| `paths.py` | Repo root, ingestion dir, content paths, `folder_name`, file path helpers |
| `catalog.py` | `load_catalog`, `save_catalog`, `resolve_catalog_row`, `load_jsonl` |
| `markdown_io.py` | Frontmatter read/write, timestamp datapoint detection, notes/post/transcript writers |
| `episode_ids.py` | `format_episode_id`, `make_id`, padded id parsing |
| `colossus.py` | Colossus login, session, HTML extractors |
| `sitemap.py` | `iter_sitemap_episodes`, slug → episode number |
| `layout.py` | Filesystem layout and catalog id consistency (used by `pipeline/verify.py`) |
| `gaps_report.py` | `catalog/gaps.md` generation and Phase 2 coverage stats |
| `cli_args.py` | Shared `--id ep-NNNN` argparse helpers |
| `expand_llm.py` | OpenRouter calls, draft validation, promote to `.expanded.md` |
| `expanded_timestamp_lint.py` | Timestamp meta validation on expanded drafts (used by promote) |
| `search_retrieval.py` | Parent/transcript chunk filters, keyword + hybrid RRF (Telegram tools) |
| `openrouter_pricing.py` | OpenRouter model pricing helpers for expand cost estimates |
| `x_posts_csv.py` | X CSV cache I/O, tweet → row conversion |
| `x_posts_match.py` | Episode attribution scoring |
| `x_posts_threads.py` | Thread grouping, reply filters, article skip |
