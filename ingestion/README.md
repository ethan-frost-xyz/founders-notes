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
| [`maintain.py`](maintain.py) | Interactive console for notes, expansion, promote, index rebuild, tune |
| [`lib/`](lib/README.md) | Shared Python modules (no CLI) |
| [`prompts/`](prompts/) | LLM prompt templates for expansion |
| [`fixtures/`](fixtures/) | Test fixtures (`chunks_parent_slice.jsonl`) |

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
| Expand (prompt A/B tune) | `notes/expand_tune.py` | Ad-hoc sandbox under `fixtures/expand-runs/` (not committed) |
| **Recovery console** | `python maintain.py` | Laptop fallback: coverage, expand, promote, reindex (Telegram is primary) |
| X sync | `x/x_posts_sync.py` | API → `import/x-posts-raw.csv` + pending queue |
| X attribute | `x/x_posts_attribute.py` | Pending queue → `content/posts/` (rules → chrono → LLM review) |
| X status | `x/x_posts_status.py` | Zero-API pipeline status |
| Search | `search/build_chunks.py` | → `catalog/chunks.jsonl` |
| Search | `search/search.py` | Query chunks (+ optional `rg`) |

## Recovery / tactical console

Laptop fallback when Telegram is unavailable (coverage, next notes, expand backlog, draft review, promote, reindex via menu 8, expand-run log):

```bash
cd ingestion
python maintain.py
```

Bulk expanded-notes backfill: [`docs/expanded-backfill.md`](../docs/expanded-backfill.md). **Operator paths:** primary Telegram — [`docs/operations.md`](../docs/operations.md); tactical `maintain.py` (this menu). **Telegram vault agent:** [`services/telegram/README.md`](../services/telegram/README.md); overview [`docs/telegram-vault-agent.md`](../docs/telegram-vault-agent.md); retrieval in `lib/search_*.py` (facade: `search_retrieval.py`; hybrid RRF in `search_hybrid.py`).

Individual scripts (`pipeline/verify.py`, `notes/expand_datapoints_llm.py`, etc.) remain available for automation and CI.

## Path bootstrap

CLI scripts call [`_bootstrap.setup_paths(__file__)`](_bootstrap.py) (adds `ingestion/` + `lib/`). Telegram and `pytest` share [`resolve_vault_root`](_bootstrap.py) / [`setup_ingestion_paths`](_bootstrap.py) — see [`docs/operations.md`](../docs/operations.md#path-bootstrap-vault_root).

## Environment variables

| Variable | Used by |
|----------|---------|
| `COLOSSUS_EMAIL`, `COLOSSUS_PASSWORD` | `transcripts/fetch_transcripts.py` |
| `COLOSSUS_COOKIES_FILE` | `transcripts/fetch_transcripts.py` (alternative to login) |
| `X_BEARER_TOKEN`, `X_USERNAME` | `x/x_posts_sync.py`, `x/assign_post_manual.py` (mini: `founders-telegram/env`) |
| `OPENROUTER_API_KEY`, `X_ATTRIBUTION_MODEL` | `x/x_posts_attribute.py --llm-review` |
| `OPENROUTER_API_KEY` | `notes/expand_datapoints_llm.py`, `notes/expand_tune.py`, `search/build_embeddings.py` |
| `OPENROUTER_MODEL` | `notes/expand_datapoints_llm.py`, `notes/expand_tune.py` — any [OpenRouter](https://openrouter.ai/models) slug; `--model` overrides; `OPENROUTER_BASE_URL` optional |

Copy `.env.example` to repo root `.env`. Model choice lives only in `.env` / CLI flags (not in repo docs).

## CLI conventions

| Flag pattern | Scripts | Meaning |
|--------------|---------|---------|
| `--id ep-NNNN` | `transcripts/fetch_transcripts.py`, `notes/scaffold_notes.py`, `notes/expand_datapoints*.py` | Canonical padded episode id |
| `--episode N` | `x/assign_post_manual.py` | Integer `episode_number` (not `ep-NNNN`) |
| `--dry-run` | Most writers; `notes/expand_datapoints_llm.py` | Report only |
| `--apply` | `pipeline/sync_new.py`, `notes/expand_datapoints_llm.py` | Write side effects |
| `--force` | `transcripts/fetch_transcripts.py`, `notes/scaffold_notes.py`, `notes/expand_datapoints_llm.py` | Re-fetch / overwrite empty scaffold / regenerate draft |

## Tests

See [`docs/testing.md`](../docs/testing.md). From repo root (same as CI):

```bash
pip install -r requirements-dev.txt
pytest tests -q
cd ingestion && python pipeline/verify.py
```
