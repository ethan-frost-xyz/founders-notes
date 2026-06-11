# Catalog pipeline

Build and maintain `catalog/episodes.jsonl`, map Colossus URLs, and verify vault layout.

Run from `ingestion/`:

```bash
python pipeline/build_catalog.py
python pipeline/map_colossus.py
python pipeline/verify.py
```

## Scripts

| Script | Purpose |
|--------|---------|
| `build_catalog.py` | Paginate founderspodcast.com sitemap + RSS → `catalog/episodes.jsonl` (includes `duration_seconds` from RSS) |
| `backfill_catalog_duration.py` | Merge RSS `itunes:duration` into existing catalog rows without full rebuild |
| `map_colossus.py` | Resolve `colossus_url` for each catalog row |
| `sync_new.py` | Append new sitemap episodes; `--repair-urls --apply` fixes weak `founders_url` |
| `verify.py` | Regenerate `catalog/gaps.md`; **exit 1** on blocking layout/transcript gaps |

## Typical flow

**Initial / full rebuild:** `build_catalog.py` → `map_colossus.py` → `transcripts/fetch_transcripts.py` → `pipeline/verify.py`

**New episode on site:** `sync_new.py --apply` → `map_colossus.py` → `transcripts/fetch_transcripts.py --id ep-NNNN` → `notes/scaffold_notes.py --missing` → `verify.py`

## Downstream

- Transcripts: [`../transcripts/README.md`](../transcripts/README.md)
- Notes scaffolds: [`../notes/README.md`](../notes/README.md)
- Shared modules: [`../lib/README.md`](../lib/README.md)
