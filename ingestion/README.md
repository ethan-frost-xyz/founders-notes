# Ingestion scripts

Run from this directory with the venv active:

```bash
cd ingestion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional: pip install -r requirements-dev.txt  # pytest
```

See also [`docs/episode-id-rules.md`](../docs/episode-id-rules.md), [`import/README.md`](../import/README.md).

## Pipeline order

| Step | Script | Notes |
|------|--------|-------|
| 1 | `build_catalog.py` | Sitemap + RSS → `catalog/episodes.jsonl` |
| 2 | `map_colossus.py` | Fill `colossus_url` per row |
| 3 | `fetch_transcripts.py` | Colossus → `content/transcripts/` (needs `.env`) |
| 4 | `verify.py` | Regenerates `catalog/gaps.md`; exits 1 on blocking gaps |
| Ongoing | `sync_new.py` | New sitemap episodes; `--repair-urls --apply` |
| Notes | `scaffold_notes.py` | Empty `{folder}.notes.md` scaffolds |
| Expand (prompt) | `expand_datapoints.py` | Print/copy prompt from notes + transcript |
| Expand (OpenRouter) | `expand_datapoints_llm.py` | `.expanded.draft.md` → `--promote` → `.expanded.md` |
| Expand (prompt A/B tune) | `expand_tune.py` | 10-ep sandbox under `fixtures/expand-runs/`; subprocess per episode |
| X sync | `sync_x_cache.py` | API → `import/x-posts-raw.csv` |
| X organize | `organize_posts_from_csv.py` | CSV → `content/posts/` (skips articles) |
| X LLM match | `attribute_posts_llm.py` | Review queue via OpenRouter (`OPENROUTER_API_KEY`) |
| Search | `build_chunks.py` | → `catalog/chunks.jsonl` |
| Search | `search.py` | Query chunks (+ optional `rg`) |

Historical one-shots: [`migrations/`](migrations/) (do not re-run).

## Environment variables

| Variable | Used by |
|----------|---------|
| `COLOSSUS_EMAIL`, `COLOSSUS_PASSWORD` | `fetch_transcripts.py` |
| `COLOSSUS_COOKIES_FILE` | `fetch_transcripts.py` (alternative to login) |
| `X_BEARER_TOKEN`, `X_USERNAME` | `sync_x_cache.py`, `assign_post_manual.py`, `attribute_posts_llm.py` |
| `OPENROUTER_API_KEY` | `attribute_posts_llm.py`, `expand_datapoints_llm.py` |
| `OPENROUTER_ATTRIBUTION_MODEL` | `attribute_posts_llm.py` (`--model` overrides) |
| `OPENROUTER_MODEL` | `expand_datapoints_llm.py` (`--model` overrides; `OPENROUTER_BASE_URL` optional) |

Copy `.env.example` to repo root `.env`.

## CLI conventions

| Flag pattern | Scripts | Meaning |
|--------------|---------|---------|
| `--id ep-NNNN` | `fetch_transcripts.py`, `scaffold_notes.py`, `expand_datapoints.py`, `expand_datapoints_llm.py` | Canonical padded episode id |
| `--episode N` | `assign_post_manual.py` | Integer `episode_number` (not `ep-NNNN`) |
| `--dry-run` | Most writers; `attribute_posts_llm.py`, `expand_datapoints_llm.py` | Report only |
| `--apply` | `sync_new.py`, `attribute_posts_llm.py`, `expand_datapoints_llm.py` | Write side effects |
| `--force` | `fetch_transcripts.py`, `scaffold_notes.py`, `expand_datapoints_llm.py` | Re-fetch / overwrite empty scaffold / regenerate draft |

Legacy unpadded ids (`ep-200`) are accepted where `--id` is supported.

## Module layout

| Module | Role |
|--------|------|
| `paths.py`, `catalog.py`, `markdown_io.py` | Paths, catalog I/O, markdown |
| `colossus.py`, `sitemap.py` | External fetch helpers |
| `layout.py`, `gaps_report.py` | Used by `verify.py` |
| `x_posts_csv.py` | X CSV cache I/O and tweet → row conversion |
| `x_posts_match.py` | Episode attribution scoring |
| `x_posts_threads.py` | Thread grouping, reply filters, article skip |
| `attribute_posts_llm.py` | LLM attribution for `post-mapping-review.jsonl` |
| `expand_llm.py`, `expand_datapoints_llm.py`, `expand_tune.py` | OpenRouter expansion + draft promote + 10-ep A/B tune sandbox |
| `cli_args.py` | Shared `--id` argparse helper |

## Tests

```bash
pip install -r requirements-dev.txt
pytest ../tests -q
python verify.py
```
