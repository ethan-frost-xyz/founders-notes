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
| X sync | `sync_x_cache.py` | API → `import/x-posts-raw.csv` |
| X organize | `organize_posts_from_csv.py` | CSV → `content/posts/` (no API) |
| Search | `build_chunks.py` | → `catalog/chunks.jsonl` |
| Search | `search.py` | Query chunks (+ optional `rg`) |

Historical one-shots: [`migrations/`](migrations/) (do not re-run).

## Environment variables

| Variable | Used by |
|----------|---------|
| `COLOSSUS_EMAIL`, `COLOSSUS_PASSWORD` | `fetch_transcripts.py` |
| `COLOSSUS_COOKIES_FILE` | `fetch_transcripts.py` (alternative to login) |
| `X_BEARER_TOKEN`, `X_USERNAME` | `sync_x_cache.py`, `assign_post_manual.py` |

Copy `.env.example` to repo root `.env`.

## CLI conventions

| Flag pattern | Scripts | Meaning |
|--------------|---------|---------|
| `--id ep-NNNN` | `fetch_transcripts.py`, `scaffold_notes.py`, `expand_datapoints.py` | Canonical padded episode id |
| `--episode N` | `assign_post_manual.py` | Integer `episode_number` (not `ep-NNNN`) |
| `--dry-run` | Most writers | Report only |
| `--apply` | `sync_new.py` | Write catalog (default is dry-run) |
| `--force` | `fetch_transcripts.py`, `scaffold_notes.py` | Re-fetch / overwrite empty scaffold |

Legacy unpadded ids (`ep-200`) are accepted where `--id` is supported.

## Module layout

| Module | Role |
|--------|------|
| `paths.py`, `catalog.py`, `markdown_io.py` | Paths, catalog I/O, markdown |
| `colossus.py`, `sitemap.py` | External fetch helpers |
| `layout.py`, `gaps_report.py` | Used by `verify.py` |
| `x_posts_csv.py` | X CSV cache I/O and tweet → row conversion |
| `x_posts_match.py` | Episode attribution scoring |
| `x_posts_threads.py` | Thread grouping and reply filters |
| `cli_args.py` | Shared `--id` argparse helper |

## Tests

```bash
pip install -r requirements-dev.txt
pytest ../tests -q
python verify.py
```
