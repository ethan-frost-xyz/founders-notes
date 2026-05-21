# Founders Notes

Personal knowledge vault for [@ethanfrost](https://x.com/ethanfrost)'s daily Founders podcast ritual — transcripts, notes, and posts in one queryable archive.

## Phase 1: Transcripts

- **Metadata index:** [founderspodcast.com/episodes](https://www.founderspodcast.com/episodes) → `catalog/episodes.jsonl`
- **Transcript text:** [Colossus](https://colossus.com/series/founders/) → `content/transcripts/{folder}/{folder}.md` (description + full transcript)
- **Gap report:** `catalog/gaps.md` (auto-generated)

## Layout

```
catalog/episodes.jsonl   # One JSON row per episode (status + URLs)
content/transcripts/     # One folder per episode id
content/notes/             # Phase 2
content/posts/             # Phase 3
ingestion/                 # Scripts to build and verify the catalog
```

## Querying in Cursor

- One episode: `@content/transcripts/ep-418-...`
- Catalog / missing: `catalog/episodes.jsonl` or `catalog/gaps.md`
- Cross-episode search: ripgrep `content/transcripts/`

## Ingestion

```bash
cd ingestion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Build metadata catalog from founderspodcast.com
python build_catalog.py

# 2. Map Colossus URLs (after catalog exists)
python map_colossus.py

# 3. Fetch transcripts (requires .env — see .env.example)
python fetch_transcripts.py

# Re-fetch all with description + full transcript (after schema changes)
python fetch_transcripts.py --force

# 4. Verify completeness
python verify.py
```

Re-fetch a single episode:

```bash
python fetch_transcripts.py --id ep-418 --force
```

## Completeness

Phase 1 is complete when `python verify.py` reports no blocking gaps in `catalog/gaps.md` (documented exceptions like `coming_soon` are OK).

See [docs/episode-id-rules.md](docs/episode-id-rules.md) for id and schema rules.
