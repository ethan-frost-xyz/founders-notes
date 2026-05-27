# Ingestion scripts

Run from this directory with the venv active:

```bash
cd ingestion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional: pip install -r requirements-dev.txt  # pytest
```

See also [`docs/episode-id-rules.md`](../docs/episode-id-rules.md), [`docs/ingestion-pipeline.md`](../docs/ingestion-pipeline.md), [`import/README.md`](../import/README.md).

## Sections

| Folder | README | Purpose |
|--------|--------|---------|
| [`pipeline/`](pipeline/README.md) | Catalog build, Colossus URL map, gaps verify |
| [`transcripts/`](transcripts/README.md) | Fetch transcripts from Colossus |
| [`notes/`](notes/README.md) | Note scaffolds and datapoint expansion |
| [`x/`](x/README.md) | X cache sync and post organization |
| [`search/`](search/README.md) | Chunk index and search |
| [`maintain.py`](maintain.py) | Interactive console for notes, expansion, promote, chunks, tune |
| [`lib/`](lib/README.md) | Shared Python modules (no CLI) |
| [`migrations/`](migrations/README.md) | Historical one-shots (do not re-run) |
| [`prompts/`](prompts/) | LLM prompt templates for expansion |
| [`fixtures/`](fixtures/) | Test fixtures and committed expand-tune A/B outputs |

## Pipeline order

| Step | Script | Notes |
|------|--------|-------|
| 1 | `pipeline/build_catalog.py` | Sitemap + RSS → `catalog/episodes.jsonl` |
| 2 | `pipeline/map_colossus.py` | Fill `colossus_url` per row |
| 3 | `transcripts/fetch_transcripts.py` | Colossus → `content/transcripts/` (needs `.env`) |
| 4 | `pipeline/verify.py` | Regenerates `catalog/gaps.md`; exits 1 on blocking gaps |
| Ongoing | `pipeline/sync_new.py` | New sitemap episodes; `--repair-urls --apply` |
| Notes | `notes/scaffold_notes.py` | Empty `{folder}.notes.md` scaffolds |
| Expand (prompt) | `notes/expand_datapoints.py` | Print/copy prompt from notes + transcript |
| Expand (OpenRouter) | `notes/expand_datapoints_llm.py` | `.expanded.draft.md` → `--promote` → `.expanded.md` |
| Expand (prompt A/B tune) | `notes/expand_tune.py` | 23-ep A/B under `fixtures/expand-runs/` (tracked; default `baseline/`) |
| **Maintenance console** | `python maintain.py` | Menu wrapper for coverage, expand, promote, chunks, tune (see below) |
| X sync | `x/sync_x_cache.py` | API → `import/x-posts-raw.csv` |
| X organize | `x/organize_posts_from_csv.py` | CSV → `content/posts/` (skips articles) |
| X LLM match | `x/attribute_posts_llm.py` | Review queue via OpenRouter |
| Search | `search/build_chunks.py` | → `catalog/chunks.jsonl` |
| Search | `search/search.py` | Query chunks (+ optional `rg`) |

## Maintenance console

Primary interactive entry for ongoing vault work (coverage, next notes path, expand backlog, draft review, promote, chunk rebuild, prompt A/B tune, expand-run log):

```bash
cd ingestion
python maintain.py
```

Bulk expanded-notes backfill: [`docs/expanded-backfill.md`](../docs/expanded-backfill.md). **Telegram vault agent (planned):** [`services/telegram/README.md`](../services/telegram/README.md); SP1 [`.cursor/plans/telegram_vault_sp1_tools.plan.md`](../.cursor/plans/telegram_vault_sp1_tools.plan.md) (`search_retrieval.py`, hybrid RRF); master index [`.cursor/plans/telegram_rag_bot_v0.plan.md`](../.cursor/plans/telegram_rag_bot_v0.plan.md).

Individual scripts (`pipeline/verify.py`, `notes/expand_datapoints_llm.py`, etc.) remain available for automation and CI.

## Environment variables

| Variable | Used by |
|----------|---------|
| `COLOSSUS_EMAIL`, `COLOSSUS_PASSWORD` | `transcripts/fetch_transcripts.py` |
| `COLOSSUS_COOKIES_FILE` | `transcripts/fetch_transcripts.py` (alternative to login) |
| `X_BEARER_TOKEN`, `X_USERNAME` | `x/sync_x_cache.py`, `x/assign_post_manual.py`, `x/attribute_posts_llm.py` |
| `OPENROUTER_API_KEY` | `x/attribute_posts_llm.py`, `notes/expand_datapoints_llm.py` |
| `OPENROUTER_ATTRIBUTION_MODEL` | `x/attribute_posts_llm.py` — optional; `--model` overrides |
| `OPENROUTER_MODEL` | `notes/expand_datapoints_llm.py`, `notes/expand_tune.py` — any [OpenRouter](https://openrouter.ai/models) slug; `--model` overrides; `OPENROUTER_BASE_URL` optional |

Copy `.env.example` to repo root `.env`. Model choice lives only in `.env` / CLI flags (not in repo docs).

## CLI conventions

| Flag pattern | Scripts | Meaning |
|--------------|---------|---------|
| `--id ep-NNNN` | `transcripts/fetch_transcripts.py`, `notes/scaffold_notes.py`, `notes/expand_datapoints*.py` | Canonical padded episode id |
| `--episode N` | `x/assign_post_manual.py` | Integer `episode_number` (not `ep-NNNN`) |
| `--dry-run` | Most writers; `x/attribute_posts_llm.py`, `notes/expand_datapoints_llm.py` | Report only |
| `--apply` | `pipeline/sync_new.py`, `x/attribute_posts_llm.py`, `notes/expand_datapoints_llm.py` | Write side effects |
| `--force` | `transcripts/fetch_transcripts.py`, `notes/scaffold_notes.py`, `notes/expand_datapoints_llm.py` | Re-fetch / overwrite empty scaffold / regenerate draft |

Legacy unpadded ids (`ep-200`) are accepted where `--id` is supported.

## Tests

See [`docs/testing.md`](../docs/testing.md). From repo root (same as CI):

```bash
pip install -r requirements-dev.txt
pytest tests -q
cd ingestion && python pipeline/verify.py
```
