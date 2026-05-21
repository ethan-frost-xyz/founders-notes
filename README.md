# Founders Notes

Personal knowledge vault for [@ethanfrost](https://x.com/ethanfrost)'s daily Founders podcast ritual — transcripts, study notes, and X posts in one queryable archive.

## Status (2026-05-21)

| Layer | Coverage | Notes |
|-------|----------|--------|
| **Transcripts** | 417 / 417 numbered | Phase 1 complete — Colossus archives in `content/transcripts/` |
| **Notes** | 189 / 417 | Ep 1–189 imported from Apple Notes; **ep 190–417 not written yet** (~1 new note/day as you listen) |
| **X posts** | 187 / 417 | CSV cache + organizer; 2 documented gaps (ep-159 skipped, ep-189 not posted) |
| **Search** | v1 | `catalog/chunks.jsonl` + `ingestion/search.py` |

Details: `catalog/gaps.md` (auto), `catalog/import-review.md` (manual attributions).

## Phase 1: Transcripts

- **Metadata index:** [founderspodcast.com/episodes](https://www.founderspodcast.com/episodes) → `catalog/episodes.jsonl`
- **Transcript text:** [Colossus](https://colossus.com/series/founders/) → `content/transcripts/{folder}/{folder}.md` (description + full transcript)
- **Gap report:** `catalog/gaps.md` (auto-generated)

## Phase 2: Notes and posts

- **Notes:** `content/notes/{folder}/notes.md` — timestamp bullets under `## Raw datapoints`. Historical batch: ep 1–189. Ep 190+ fills in over time as you finish each episode (~1/day).
- **Posts:** `content/posts/{folder}/post.md` — one Founders post per episode (threads + articles)
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

See [docs/episode-id-rules.md](docs/episode-id-rules.md), [docs/datapoint-workflow.md](docs/datapoint-workflow.md), [docs/retrieval.md](docs/retrieval.md), [AGENTS.md](AGENTS.md).

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

- One episode: `@content/transcripts/ep-418-...` plus matching `content/notes/` and `content/posts/` folders
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

# Phase 2 — notes and posts
python import_notes.py -i ../import/apple-notes.txt
python sync_x_cache.py --full
python organize_posts_from_csv.py
python build_chunks.py
python verify.py
```

Re-fetch one transcript: `python fetch_transcripts.py --id ep-418 --force`

## Completeness

Phase 1 is complete when `python verify.py` reports no blocking transcript gaps.

Phase 2 progress is in `catalog/gaps.md` (notes/posts counts and missing episode lists).

---

## What to build next

Three high-leverage options, ordered by impact on the daily ritual:

### 1. Notes catch-up plan (episodes 190–417, in progress)

**Why:** Notes are the study spine. Ep 1–189 are in the vault from a one-time Apple Notes export. You have **not** started notes for ep 190 yet; you add roughly **one episode per day** as you listen, so ep 190–417 will grow over months—not as a single missing export.

**Recommended workflow (pick one and stay consistent):**

| Approach | How it works | Best if |
|----------|----------------|---------|
| **A. Periodic Apple Notes merge** | Keep writing in Apple Notes (one note per episode, `#N` title). Every week or after every N episodes: export → `import/apple-notes.txt` → `python import_notes.py -i ../import/apple-notes.txt --merge` → `python build_chunks.py` | You want to keep your current Notes habit unchanged |
| **B. Vault-native notes** | Create `content/notes/ep-NNN-.../notes.md` directly in git (same `## Raw datapoints` bullets). No export step for new episodes | You are fine leaving Apple Notes for old eps only |
| **C. Hybrid** | New episodes in the vault (B); occasionally merge an Apple Notes export for anything you still capture there (A) | Transitioning off Notes without retyping 1–189 |

**Operational checklist (after each batch or new ep):**

1. Ensure the episode block has a clear `#N` / title header (import parser keys off episode number).
2. `import_notes.py --merge` (A/C) or commit `notes.md` directly (B).
3. `python verify.py` — watch the notes count climb in `catalog/gaps.md`.
4. `python build_chunks.py` so `search.py` sees new bullets.

**Also:** Replace ep-21 `XYZ` placeholder when that note shows up in an export or you add it manually.

**Done when:** Notes count tracks how far you have listened (not 417 overnight)—treat 190–417 as a living tail, not a backfill dump.

### 2. X post corpus completion + native articles

**Why:** Posts are at 187 / 417. The CSV cache (~433 rows) is not full history. Link-only tweets (native X articles) do not carry body text in the API — ep-148 required manual paste. Three rows sit in `catalog/post-mapping-review.jsonl`.

**Build:** Deeper `sync_x_cache.py --full` backfill; optional article-body fetch for `x.com/i/article/…` URLs; work through review queue; `assign_post_manual.py` for gaps; assign ep-189 when published. Re-run organize + corpus.

**Done when:** ~400+ `post.md` files (minus documented skips like ep-159) and review queue empty.

### 3. Datapoint expansion at scale

**Why:** 189 episodes have raw timestamp bullets but almost no `expanded.md`. This is the highest-value daily workflow after import — quotes + takeaways from transcript without hand-copying.

**Build:** Batch driver around `expand_datapoints.py` (episode list, optional `--write` scaffolds), quality checklist in `docs/datapoint-workflow.md`, chunk index includes `notes:expanded_datapoints` when present.

**Done when:** Expanded notes exist for episodes you actively study; search surfaces expanded sections.

---

**Defer for now:** Vector embeddings ([docs/retrieval.md](docs/retrieval.md) v2) until the post corpus is much fuller and `search.py` misses real queries. Legacy `import_posts_x.py` remains for Google Doc fallback; prefer CSV-first sync + organize.
