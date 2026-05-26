# Founders Notes

Personal knowledge vault for [@ethanfrost](https://x.com/ethanfrost)'s daily Founders podcast ritual — transcripts, study notes, and X posts in one queryable archive.

## Status (2026-05-21)

| Layer | Coverage | Notes |
|-------|----------|--------|
| **Transcripts** | 417 / 417 numbered | Phase 1 complete — Colossus archives in `content/transcripts/` |
| **Notes** | 417 files / 176 datapoints | **In progress (daily):** edit `.notes.md` in git (~1 episode/day); empty scaffolds = not listened yet |
| **X posts** | 187 / 417 | CSV cache + organizer; 2 documented gaps (ep-0159 skipped, ep-0189 not posted) |
| **Search** | v1 | `catalog/chunks.jsonl` + `ingestion/search/search.py` |

Details: `catalog/gaps.md` (auto), `catalog/import-review.md` (manual attributions).

## Phase 1: Transcripts

- **Metadata index:** [founderspodcast.com/episodes](https://www.founderspodcast.com/episodes) → `catalog/episodes.jsonl`
- **Transcript text:** [Colossus](https://colossus.com/series/founders/) → `content/transcripts/{folder}/{folder}.transcript.md` (description + full transcript)
- **Gap report:** `catalog/gaps.md` (auto-generated)

## Phase 2: Notes and posts

- **Notes:** `content/notes/{folder}/{folder}.notes.md` — timestamp bullets under `## Raw datapoints`, edited directly in the repo (see [docs/notes-pipeline.md](docs/notes-pipeline.md)). Coverage grows daily (~1 episode).
- **Posts:** `content/posts/{folder}/{folder}.post.md` — one Founders post per episode (threads + articles)
- **Corpus:** `content/posts/_corpus/all-posts.md` — all Founders posts for cross-episode search
- **X pipeline:** sync API → `import/x-posts-raw.csv` (gitignored) → organize (no API on organize)

```bash
cd ingestion
source .venv/bin/activate

# X: cache first, then organize (requires .env)
python x/sync_x_cache.py --full    # one-time backfill
python x/sync_x_cache.py           # incremental
python x/organize_posts_from_csv.py

# Manual episode post (article text, wrong ep # on X, recap threads)
python x/assign_post_manual.py --episode 148 --x-post-id ID --published-at 2026-03-17 \
  --post-kind article --body-file ../import/body.txt

# Search index + verify
python search/build_chunks.py
python pipeline/verify.py
python search/search.py "rockefeller"
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
import/                         # Gitignored exports (x-posts-raw.csv, manual post bodies)
ingestion/                      # Build, import, verify scripts (see ingestion/README.md)
```

## Querying in Cursor

- One episode: `@content/transcripts/ep-0418-.../ep-0418-....transcript.md` plus matching `.notes.md` / `.post.md` in sibling folders
- Catalog / missing: `catalog/episodes.jsonl` or `catalog/gaps.md`
- Cross-episode search: `python search/search.py "rockefeller"` or ripgrep `content/`
- Full post corpus: `content/posts/_corpus/all-posts.md`
- Agent entrypoint: `AGENTS.md`

## Ingestion (full pipeline)

```bash
cd ingestion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Phase 1 — transcripts
python pipeline/build_catalog.py
python pipeline/map_colossus.py
python transcripts/fetch_transcripts.py          # requires .env
python pipeline/verify.py

# Ongoing — new episodes / URL repair
python pipeline/sync_new.py --repair-urls --apply
# after map_colossus + fetch_transcripts for new rows:
python notes/scaffold_notes.py --missing

# Phase 2 — notes and posts (notes: edit .notes.md directly; see docs/notes-pipeline.md)
python x/sync_x_cache.py --full
python x/organize_posts_from_csv.py
python search/build_chunks.py
python pipeline/verify.py
```

Re-fetch one transcript: `python transcripts/fetch_transcripts.py --id ep-0418 --force`

## Completeness

Phase 1 is complete when `python pipeline/verify.py` reports no blocking transcript gaps.

Phase 2 progress is in `catalog/gaps.md` (notes files vs datapoints, posts). **Low datapoint/post counts are expected** while working through the catalog daily—not ingestion errors.

---

## What to build next

Three high-leverage options, ordered by impact on the daily ritual:

### 1. Notes catch-up (episodes 0190–0417, in progress)

**Primary workflow:** vault-native notes in git — see [docs/notes-pipeline.md](docs/notes-pipeline.md) (Working Copy on phone, Cursor on Mac).

176 episodes have datapoints (see `catalog/gaps.md`). Ep 0190–0417 have **empty scaffolds** (`python notes/scaffold_notes.py`); add timestamp bullets as you finish each episode (~1/day).

```bash
python notes/scaffold_notes.py --next   # path to next file to edit
python pipeline/verify.py                  # notes files vs notes with datapoints
python search/build_chunks.py            # after adding bullets
```

**Also:** Replace ep-0021 `XYZ` placeholder when that note exists.

**Done when:** `notes with datapoints` in `catalog/gaps.md` tracks how far you have listened—not all 417 overnight.

### 2. X posts (recurring, not bulk backfill)

**Why:** ~187 posts match episodes you have published on X through ~ep-0188. **Missing posts from ep-0190 onward are expected**—you have not posted those episodes yet. Native X articles are skipped by `organize_posts_from_csv.py`; use `assign_post_manual.py --body-file` for legacy article bodies (ep-0082, ep-0088, ep-0148).

**After each X post:**

```bash
python x/sync_x_cache.py
python x/organize_posts_from_csv.py
python x/attribute_posts_llm.py --dry-run   # optional: ambiguous review queue
python x/attribute_posts_llm.py --apply
```

**Done when:** Each new episode you publish gets a `.post.md` via organize (explicit `#`) or LLM/manual—not when all 417 rows are filled.

### 3. Datapoint expansion at scale

**Why:** 176 episodes have raw timestamp bullets but almost no `{folder}.expanded.md`. This is the highest-value daily workflow after import — quotes + takeaways from transcript without hand-copying.

**Shipped:** `expand_datapoints_llm.py` (OpenRouter → `.expanded.draft.md`, `--promote` → `.expanded.md`), tunable prompt in `ingestion/prompts/expand_datapoints.md`, coverage lines in `catalog/gaps.md`. Chunk index includes expanded sections when `.expanded.md` exists (`build_chunks.py`).

**Done when:** Expanded notes exist for episodes you actively study; search surfaces expanded sections.

---

**Defer for now:** Vector embeddings ([docs/retrieval.md](docs/retrieval.md) v2) until the post corpus is much fuller and `search.py` misses real queries. X posts: `sync_x_cache.py` then `organize_posts_from_csv.py` (see `import/README.md`).
