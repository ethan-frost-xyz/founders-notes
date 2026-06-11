# Founders Notes

Personal knowledge vault for [@ethanfrost](https://x.com/ethanfrost)'s daily Founders podcast ritual — transcripts, study notes, and X posts in one queryable archive.

## Status

| Layer | Coverage | Notes |
|-------|----------|--------|
| **Transcripts** | See [`catalog/gaps.md`](catalog/gaps.md) | Phase 1 complete — Colossus archives in `content/transcripts/` |
| **Notes** | See [`catalog/gaps.md`](catalog/gaps.md) | **In progress (daily):** edit `.notes.md` in git (~1 episode/day); empty scaffolds = not listened yet |
| **X posts** | See [`catalog/gaps.md`](catalog/gaps.md) | CSV cache + attribute pipeline; manual gaps in [`catalog/import-review.md`](catalog/import-review.md) |
| **Search** | CLI keyword search + agentic Telegram Librarian | [`catalog/chunks.jsonl`](catalog/chunks.jsonl) — [`docs/retrieval.md`](docs/retrieval.md) |
| **Telegram** | Shipped | Librarian + Janitor on Mac mini; push-to-`main` webhook sync — see below |

Live counts: [`catalog/gaps.md`](catalog/gaps.md) (auto). Manual attributions: [`catalog/import-review.md`](catalog/import-review.md).

## Telegram vault agent (Mac mini)

Private **Telegram bot** on an always-on Mac mini (polling): **Librarian** as a study partner over your studied episodes (cross-episode synthesis, not ranked excerpt dumps — voice in [`AGENTS.md`](AGENTS.md)); **Janitor** for the daily notes ritual (paste → clean → expand → promote → reindex).

| Doc | Role |
|-----|------|
| [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md) | Overview for agents |
| [`docs/operations.md`](docs/operations.md) | Laptop, Mac mini, Telegram ops (merged runbooks) |
| [`docs/janitor.md`](docs/janitor.md) | Janitor workflow (daily ritual) |
| [`services/telegram/README.md`](services/telegram/README.md) | Deploy reference (install, env, commands) |
| [`docs/testing.md`](docs/testing.md) | CI, harness, v0 checklist tests |
| [`potential-ideas.md`](potential-ideas.md) | Deferred features and follow-ups |

**Implementation history:** [`.cursor/plans/archive/README.md`](.cursor/plans/archive/README.md) (completed plans in `archive/legacy/`, gitignored from agent context)

- **Librarian:** agentic retrieval loop (v4) — model-driven `search_vault` / `search_vault_many` / `search_transcript` + `load_episode` / `list_episode_ids` (≤6 tool rounds); synthesis **streaming** default off (`/settings` → Stream replies). Persona: [`AGENTS.md`](AGENTS.md).
- **Janitor:** `/janitor` → paste bullets → LLM clean → approve → file → expand → promote → reindex. See [`docs/janitor.md`](docs/janitor.md).
- **Ops:** GitHub webhook or `sync-and-index.sh` (cron / Telegram `/sync`); index refresh after promote on the bot host.

Expanded corpus quality: promote `.expanded.md`, then reindex — see [`docs/expanded-backfill.md`](docs/expanded-backfill.md).

## Phase 1: Transcripts

- **Metadata index:** [founderspodcast.com/episodes](https://www.founderspodcast.com/episodes) → `catalog/episodes.jsonl`
- **Transcript text:** [Colossus](https://colossus.com/series/founders/) → `content/transcripts/{folder}/{folder}.transcript.md` (description + full transcript)
- **Gap report:** `catalog/gaps.md` (auto-generated)

## Phase 2: Notes and posts

- **Notes:** `content/notes/{folder}/{folder}.notes.md` — timestamp bullets under `## Raw datapoints`, edited directly in the repo (see [docs/notes-pipeline.md](docs/notes-pipeline.md)). Coverage grows daily (~1 episode).
- **Posts:** `content/posts/{folder}/{folder}.post.md` — one Founders post per episode (threads + articles)
- **Corpus:** `content/posts/_corpus/all-posts.md` — all Founders posts for cross-episode search
- **X pipeline:** sync API → `import/x-posts-raw.csv` (gitignored) → attribute (no API on attribute)

```bash
cd ingestion
source .venv/bin/activate

# X: cache first, then attribute (requires .env)
python x/x_posts_sync.py --full      # one-time backfill
python x/x_posts_sync.py             # incremental
python x/x_posts_attribute.py        # map cache → .post.md

# Manual episode post (article text, wrong ep # on X, recap threads)
python x/assign_post_manual.py --episode 148 --x-post-id ID --published-at 2026-03-17 \
  --post-kind article --body-file ../import/body.txt

# Search index + verify
python search/build_chunks.py
python pipeline/verify.py
python search/search.py "rockefeller"
```

See [docs/episode-id-rules.md](docs/episode-id-rules.md), [docs/notes-pipeline.md](docs/notes-pipeline.md), [docs/datapoint-workflow.md](docs/datapoint-workflow.md), [docs/retrieval.md](docs/retrieval.md), [docs/repo-agent-guide.md](docs/repo-agent-guide.md).

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
services/telegram/              # Telegram vault agent (Librarian + Janitor)
```

## Querying in Cursor

- One episode: `@content/transcripts/ep-0418-.../ep-0418-....transcript.md` plus matching `.notes.md` / `.post.md` in sibling folders
- Catalog / missing: `catalog/episodes.jsonl` or `catalog/gaps.md`
- Cross-episode search: `python search/search.py "rockefeller"` or ripgrep `content/`
- Full post corpus: `content/posts/_corpus/all-posts.md`
- Vault study partner (Librarian prompt): `AGENTS.md`
- Repo maintenance / ingestion (Cursor): [docs/repo-agent-guide.md](docs/repo-agent-guide.md)

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
python x/x_posts_sync.py --full
python x/x_posts_attribute.py
python search/build_chunks.py
python pipeline/verify.py
```

Re-fetch one transcript: `python transcripts/fetch_transcripts.py --id ep-0418 --force`

## Completeness

Phase 1 is complete when `python pipeline/verify.py` reports no blocking transcript gaps.

Phase 2 progress is in `catalog/gaps.md` (notes files vs datapoints, posts). **Low datapoint/post counts are expected** while working through the catalog daily—not ingestion errors.

---

## Current priorities

Daily ritual work, ordered by impact:

### 1. Notes catch-up

Add timestamp bullets as you finish each episode (~1/day) via `/janitor` on Telegram or direct `.notes.md` edit in git. See [`docs/janitor.md`](docs/janitor.md), [`docs/notes-pipeline.md`](docs/notes-pipeline.md).

```bash
python notes/scaffold_notes.py --next   # path to next file to edit
python pipeline/verify.py
python search/build_chunks.py            # after adding bullets
```

**Done when:** `notes with datapoints` in [`catalog/gaps.md`](catalog/gaps.md) tracks how far you have listened—not all 417 overnight.

### 2. Incremental X posts

After each new post on X, sync and attribute. See [`ingestion/x/README.md`](ingestion/x/README.md).

```bash
python x/x_posts_sync.py
python x/x_posts_attribute.py
# ambiguous rows → catalog/post-mapping-review.jsonl; fix manually or assign_post_manual.py
```

Native X articles are skipped by attribute; use `assign_post_manual.py --body-file` for legacy article bodies (ep-0082, ep-0088, ep-0148).

**Done when:** Each new episode you publish gets a `.post.md` via attribute (`#N` in tweet) or manual assign—not when all 417 rows are filled.

### 3. Expanded backfill

For episodes with bullets but no `.expanded.md`, use [`docs/expanded-backfill.md`](docs/expanded-backfill.md) or Janitor expand/promote.

Engineering backlog: [`potential-ideas.md`](potential-ideas.md).
