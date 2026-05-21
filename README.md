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
content/notes/             # Phase 2 — raw datapoints per episode
content/posts/             # Phase 2 — X posts per episode + _corpus/all-posts.md
ingestion/                 # Scripts to build and verify the catalog
```

## Querying in Cursor

- One episode: `@content/transcripts/ep-418-...` plus matching `content/notes/` and `content/posts/` folders
- Catalog / missing: `catalog/episodes.jsonl` or `catalog/gaps.md`
- Cross-episode search: `python search.py "rockefeller"` or ripgrep `content/`
- Full post corpus: `content/posts/_corpus/all-posts.md`
- Agent entrypoint: `AGENTS.md`

## Phase 2: Notes and posts

```bash
cd ingestion
source .venv/bin/activate

# Import Apple Notes export (see import/README.md)
python import_notes.py --input ../import/apple-notes.txt

# X posts: cache to CSV first, then organize (requires .env)
python sync_x_cache.py --full    # once
python sync_x_cache.py           # incremental
python organize_posts_from_csv.py

# Regenerate search chunk index
python build_chunks.py

# Expand datapoints prompt pack for one episode
python expand_datapoints.py --id ep-200
```

See [docs/episode-id-rules.md](docs/episode-id-rules.md) and [docs/datapoint-workflow.md](docs/datapoint-workflow.md).

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

# 5. Sync new episodes / repair catalog URLs
python sync_new.py --repair-urls --apply

# 6. Phase 2 imports (see import/README.md)
python import_notes.py -i ../import/apple-notes.txt
python import_posts_x.py
python build_chunks.py
```

Re-fetch a single episode:

```bash
python fetch_transcripts.py --id ep-418 --force
```

## Completeness

Phase 1 is complete when `python verify.py` reports no blocking gaps in `catalog/gaps.md` (documented exceptions like `coming_soon` are OK).

See [docs/episode-id-rules.md](docs/episode-id-rules.md) for id and schema rules.
