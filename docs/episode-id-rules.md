# Episode ID and schema rules

## Rule 1 — Episode IDs (sort-safe)

| Case | `id` format | Example |
|------|-------------|---------|
| Numbered episode | `ep-{NNNN}` (4-digit zero-padded) | `ep-0418` |
| Unnumbered (conversations, reposts, specials) | `ep-special-{slug}` | `ep-special-my-conversation-with-todd-graves` |

**`episode_number`** in catalog and frontmatter is always an **integer** (`418`) for display and matching. **`id`** is the canonical padded string used in paths and chunk ids.

**`slug`** and `founders_url` stay **unpadded** (`418-phil-knight-founder-of-nike`) — they mirror founders.com URLs and must not be renamed.

**Folder name:** `{id}-` + slug without duplicate episode prefix. For numbered episodes, slug `418-phil-knight-founder-of-nike` with `id` `ep-0418` becomes folder `ep-0418-phil-knight-founder-of-nike`. Specials use full slug: `ep-special-{slug}`.

Padding width is `EPISODE_NUMBER_WIDTH = 4` in `ingestion/lib/episode_ids.py` (supports ep-0001 … ep-9999). Plain alphabetical sort of folders then matches episode order.

## Rule 2 — Per-episode filenames (`{folder}.{type}.md`)

Every episode uses the **same folder basename** under each content tree. Inside the folder, filenames are `{folder}.{type}.md`:

| Type | Path |
|------|------|
| Transcript | `content/transcripts/{folder}/{folder}.transcript.md` |
| Raw notes | `content/notes/{folder}/{folder}.notes.md` |
| Expanded datapoints (optional) | `content/notes/{folder}/{folder}.expanded.md` |
| Expanded draft (LLM staging, optional) | `content/notes/{folder}/{folder}.expanded.draft.md` |
| X post | `content/posts/{folder}/{folder}.post.md` |

Allowed `type` values: `transcript`, `notes`, `expanded`, `post`. `.md` remains the real extension. The `.expanded.draft.md` filename is a **layout exception** (not a `{type}` token); it is not indexed in `catalog/chunks.jsonl` until promoted to `.expanded.md`.

**Example (episode 418):**

```
content/transcripts/ep-0418-phil-knight-founder-of-nike/ep-0418-phil-knight-founder-of-nike.transcript.md
content/notes/ep-0418-phil-knight-founder-of-nike/ep-0418-phil-knight-founder-of-nike.notes.md
content/posts/ep-0418-phil-knight-founder-of-nike/ep-0418-phil-knight-founder-of-nike.post.md
```

All path helpers live in `ingestion/lib/paths.py` (`folder_name`, `content_filename`, `transcript_path`, `notes_file_path`, etc.). `ingestion/pipeline/verify.py` enforces layout, ids, and frontmatter schema.

## Canonical episode frontmatter (all types)

Every episode markdown file under `content/` shares a **core** YAML block (same field order). Type-specific fields follow. Frontmatter is always written by ingestion tooling — never by the expansion LLM.

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Canonical id (`ep-0418`) |
| `episode_number` | if numbered | Integer |
| `title` | yes | Display title from catalog |
| `content_type` | yes | `transcript`, `notes`, `post`, `expanded`, or `expanded.draft` |
| `source` | yes | Provenance (`colossus`, `vault_native`, `x_csv`, `expand_llm`, …) |
| `published_at` | if known | Episode date from catalog; for posts, X post date when set |
| `founders_url` | if known | From catalog |
| `created_at` | yes | ISO 8601 UTC — file creation or primary import time |

Example (expanded):

```yaml
---
id: "ep-0200"
episode_number: 200
title: "#200 …"
content_type: "expanded"
source: "expand_llm"
published_at: "2024-01-15"
founders_url: "https://www.founderspodcast.com/episodes/..."
created_at: "2026-05-26T14:37:02Z"
expanded_at: "2026-05-26T14:37:02Z"
expanded_model: "provider/model"
---
```

## Transcript file frontmatter

Core fields plus:

| Field | Required | Notes |
|-------|----------|-------|
| `colossus_url` | yes | Official transcript source |
| `fetched_at` | yes | ISO 8601 UTC when saved (also mirrored in `created_at` on fetch) |

`source` is always `colossus` for Phase 1 fetches.

Body structure:

1. `## Description` — Colossus episode blurb above the transcript
2. `## Transcript` — full transcript text

## `catalog/episodes.jsonl` columns

One JSON object per line:

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Canonical id |
| `episode_number` | int \| null | |
| `title` | string | |
| `published_at` | string \| null | `YYYY-MM-DD` |
| `founders_url` | string | |
| `colossus_url` | string \| null | Filled in mapping step |
| `slug` | string | URL slug for folder naming |
| `transcript_status` | string | `pending`, `complete`, `failed`, `no_transcript`, `coming_soon` |
| `transcript_path` | string \| null | Relative path when complete |
| `last_error` | string \| null | Last fetch error message |
| `fetched_at` | string \| null | ISO 8601 UTC |
| `duration_seconds` | int \| null | Episode length from RSS `itunes:duration` (`build_catalog.py` / `backfill_catalog_duration.py`) |

## `transcript_status` meanings

- **pending** — Not fetched yet
- **complete** — transcript markdown on disk (`{folder}.transcript.md`)
- **failed** — Fetch error; see `last_error`
- **coming_soon** — Colossus page has no transcript yet
- **no_transcript** — Confirmed no transcript exists for this entry

---

## Phase 2: Notes and posts

Per-episode folders mirror transcripts: same `{folder}` basename under each tree.

| Content | Path |
|---------|------|
| Raw notes | `content/notes/{folder}/{folder}.notes.md` |
| Expanded draft (optional) | `content/notes/{folder}/{folder}.expanded.draft.md` |
| Expanded datapoints (optional) | `content/notes/{folder}/{folder}.expanded.md` |
| X post | `content/posts/{folder}/{folder}.post.md` |
| All posts corpus | `content/posts/_corpus/all-posts.md` |

### `{folder}.notes.md` frontmatter

Core fields plus:

| Field | Required | Notes |
|-------|----------|-------|
| `imported_at` | yes | ISO 8601 UTC (legacy field; `created_at` uses the same timestamp for new scaffolds) |

`source`: `vault_native` for new notes; legacy `apple_notes_import` on older files.

Body must include `## Raw datapoints` with timestamp bullets:

```markdown
## Raw datapoints
- 12:34 — half sentence reference
- 1:05:00 — another bullet
```

Timestamps use `MM:SS` or `H:MM:SS` before the em dash.

### `{folder}.post.md` frontmatter

Core fields plus:

| Field | Required | Notes |
|-------|----------|-------|
| `x_url` | yes | Canonical X URL |
| `x_post_id` | yes | X post id |
| `imported_at` | yes | ISO 8601 UTC |
| `post_kind` | no | `tweet`, `article`, `quote`, `reply` |
| `attribution_note` | no | Manual mapping notes (wrong ep number on X, recap thread, etc.) |
| `alt_source` | no | e.g. `google_doc` when merged |

`source`: `x_csv`, `manual_attribution`, or legacy `x_api`. `published_at` in core is the X post date when known.

Body: full post text (thread + self-replies merged). Native X articles may publish as a link tweet only in the API — paste full article text manually when needed (`x/assign_post_manual.py`).

### `{folder}.expanded.draft.md` (optional)

Written by `expand_datapoints_llm.py --apply`. **LLM output is body-only** (`## Expanded datapoints` …); Python adds frontmatter. Core fields plus:

| Field | Required | Notes |
|-------|----------|-------|
| `model` | yes | OpenRouter model slug |
| `generated_at` | yes | ISO 8601 UTC |
| `prompt_path` | yes | Relative path under repo root |
| `prompt_hash` | yes | SHA-256 prefix of prompt file |
| `tune_variant` | no | `A` / `B` when run from `expand_tune.py` |

Run `expand_datapoints_llm.py --promote --apply` after review; promotion deletes the draft.

### `{folder}.expanded.md` (optional)

Promoted from draft or written manually. Core fields plus:

| Field | Required | Notes |
|-------|----------|-------|
| `expanded_at` | yes | ISO 8601 UTC when promoted |
| `expanded_model` | no | Model from draft |
| `prompt_hash` | no | From draft when available |

Body: `## Expanded datapoints`; per bullet `### {timestamp} — {bullet}`, then Context, Quote, Key takeaway.

### Catalog sidecars

| File | Purpose |
|------|---------|
| `catalog/unmapped-posts.jsonl` | X posts that could not be matched to an episode |
| `catalog/import-review.md` | Human review queue for ambiguous imports |
| `catalog/post-mapping-review.jsonl` | Auto-generated by `x/x_posts_attribute.py` (medium-confidence matches) |

## CLI episode selectors

| Script | Flag | Value | Notes |
|--------|------|-------|-------|
| `transcripts/fetch_transcripts.py` | `--id` | `ep-0200` | Canonical padded id; legacy `ep-200` also resolves |
| `notes/scaffold_notes.py` | `--id` | `ep-0200` | Single episode; also `--from` / `--to` (integers), `--missing`, `--next` |
| `notes/expand_datapoints.py` | `--id` | `ep-0200` | Required; optional `--prompt` |
| `notes/expand_datapoints_llm.py` | `--id`, `--from` / `--to`, `--missing-expanded`, `--promote` | — | Always with `--dry-run` or `--apply`; see `docs/datapoint-workflow.md` |
| `x/assign_post_manual.py` | `--episode` | `148` | Integer `episode_number`, **not** `ep-0148` |

Path helpers: `ingestion/lib/paths.py`.

Historical Apple Notes import: one-shot bulk import (episodes 1–189); importer removed — see git history before `2fb9d22`.
