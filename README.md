# Founders Notes

Personal knowledge vault for [@ethanfrost](https://x.com/ethanfrost)'s daily Founders podcast ritual — transcripts, study notes, and X posts in one queryable archive.

## Status (2026-05-21)

| Layer | Coverage | Notes |
|-------|----------|--------|
| **Transcripts** | 417 / 417 numbered | Phase 1 complete — Colossus archives in `content/transcripts/` |
| **Notes** | 417 files / 189 datapoints | Ep 1–189 have timestamp bullets; ep 0190–0417 scaffolded empty — fill as you listen (~1/day) |
| **X posts** | 187 / 417 | CSV cache + organizer; 2 documented gaps (ep-0159 skipped, ep-0189 not posted) |
| **Search** | v1 | `catalog/chunks.jsonl` + `ingestion/search.py` |

Details: `catalog/gaps.md` (auto), `catalog/import-review.md` (manual attributions).

## Phase 1: Transcripts

- **Metadata index:** [founderspodcast.com/episodes](https://www.founderspodcast.com/episodes) → `catalog/episodes.jsonl`
- **Transcript text:** [Colossus](https://colossus.com/series/founders/) → `content/transcripts/{folder}/{folder}.transcript.md` (description + full transcript)
- **Gap report:** `catalog/gaps.md` (auto-generated)

## Phase 2: Notes and posts

- **Notes:** `content/notes/{folder}/{folder}.notes.md` — timestamp bullets under `## Raw datapoints`. Historical batch: ep 1–189. Ep 190+ fills in over time as you finish each episode (~1/day).
- **Posts:** `content/posts/{folder}/{folder}.post.md` — one Founders post per episode (threads + articles)
- **Corpus:** `content/posts/_corpus/all-posts.md` — all Founders posts for cross-episode search
- **X pipeline:** sync API → `import/x-posts-raw.csv` (gitignored) → organize (no API on organize)

```bash
cd ingestion
source .venv/bin/activate

# Apple Notes (see import/README.md)
python import_notes.py -i ../import/apple-notes.txt
python import_notes.py -i ../import/apple-notes.txt --merge   # append new bullets

# X: cache first, then organize (requires .env)
python sync_x_cache.py --full    # one-time backfill
python sync_x_cache.py           # incremental
python organize_posts_from_csv.py

# Manual episode post (article text, wrong ep # on X, recap threads)
python assign_post_manual.py --episode 148 --x-post-id ID --published-at 2026-03-17 \
  --post-kind article --body-file ../import/body.txt

# Search index + verify
python build_chunks.py
python verify.py
python search.py "rockefeller"
```

See [docs/episode-id-rules.md](docs/episode-id-rules.md), [docs/notes-pipeline.md](docs/notes-pipeline.md), [docs/datapoint-workflow.md](docs/datapoint-workflow.md), [docs/retrieval.md](docs/retrieval.md), [AGENTS.md](AGENTS.md).

## Layout

```
catalog/episodes.jsonl          # One JSON row per episode (status + URLs)
catalog/gaps.md                 # Auto-generated coverage report
catalog/import-review.md        # Manual import / attribution notes
catalog/chunks.jsonl            # Chunk index for search.py
content/transcripts/            # Colossus transcript per episode
content/notes/                  # Raw datapoints per episode
content/posts/                  # X post per episode + _corpus/ + _other/
import/                         # Gitignored exports (apple-notes.txt, x-posts-raw.csv)
ingestion/                      # Build, import, verify scripts
```

## Querying in Cursor

- One episode: `@content/transcripts/ep-0418-.../ep-0418-....transcript.md` plus matching `.notes.md` / `.post.md` in sibling folders
- Catalog / missing: `catalog/episodes.jsonl` or `catalog/gaps.md`
- Cross-episode search: `python search.py "rockefeller"` or ripgrep `content/`
- Full post corpus: `content/posts/_corpus/all-posts.md`
- Agent entrypoint: `AGENTS.md`

## Ingestion (full pipeline)

```bash
cd ingestion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Phase 1 — transcripts
python build_catalog.py
python map_colossus.py
python fetch_transcripts.py          # requires .env
python verify.py

# Ongoing — new episodes / URL repair
python sync_new.py --repair-urls --apply
# after map_colossus + fetch_transcripts for new rows:
python scaffold_notes.py --missing

# Phase 2 — notes and posts
python import_notes.py -i ../import/apple-notes.txt
python sync_x_cache.py --full
python organize_posts_from_csv.py
python build_chunks.py
python verify.py
```

Re-fetch one transcript: `python fetch_transcripts.py --id ep-0418 --force`

## Completeness

Phase 1 is complete when `python verify.py` reports no blocking transcript gaps.

Phase 2 progress is in `catalog/gaps.md` (notes files vs datapoints, posts, missing lists).

---

## What to build next

Three high-leverage options, ordered by impact on the daily ritual:

### 1. Notes catch-up (episodes 0190–0417, in progress)

**Primary workflow:** vault-native notes in git — see [docs/notes-pipeline.md](docs/notes-pipeline.md) (Working Copy on phone, Cursor on Mac).

Ep 1–189 have datapoints from Apple Notes import. Ep 0190–0417 have **empty scaffolds** (`python scaffold_notes.py`); add timestamp bullets as you finish each episode (~1/day).

```bash
python scaffold_notes.py --next   # path to next file to edit
python verify.py                  # notes files vs notes with datapoints
python build_chunks.py            # after adding bullets
```

**Also:** Replace ep-0021 `XYZ` placeholder when that note exists. Optional Apple Notes merge: `import_notes.py --merge` for stragglers only.

**Done when:** `notes with datapoints` in `catalog/gaps.md` tracks how far you have listened—not all 417 overnight.

### 2. X post corpus completion + native articles

**Why:** Posts are at 187 / 417. The CSV cache (~433 rows) is not full history. Link-only tweets (native X articles) do not carry body text in the API — ep-0148 required manual paste. Three rows sit in `catalog/post-mapping-review.jsonl`.

**Build:** Deeper `sync_x_cache.py --full` backfill; optional article-body fetch for `x.com/i/article/…` URLs; work through review queue; `assign_post_manual.py` for gaps; assign ep-189 when published. Re-run organize + corpus.

**Done when:** ~400+ `{folder}.post.md` files (minus documented skips like ep-0159) and review queue empty.

### 3. Datapoint expansion at scale

**Why:** 189 episodes have raw timestamp bullets but almost no `{folder}.expanded.md`. This is the highest-value daily workflow after import — quotes + takeaways from transcript without hand-copying.

**Build:** Batch driver around `expand_datapoints.py` (episode list, optional `--write` scaffolds), quality checklist in `docs/datapoint-workflow.md`, chunk index includes `notes:expanded_datapoints` when present.

**Done when:** Expanded notes exist for episodes you actively study; search surfaces expanded sections.

---

**Defer for now:** Vector embeddings ([docs/retrieval.md](docs/retrieval.md) v2) until the post corpus is much fuller and `search.py` misses real queries. X posts: `sync_x_cache.py` then `organize_posts_from_csv.py` (see `import/README.md`).
