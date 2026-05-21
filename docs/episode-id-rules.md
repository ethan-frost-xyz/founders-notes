# Episode ID and schema rules

## Rule 1 — Episode IDs (sort-safe)

| Case | `id` format | Example |
|------|-------------|---------|
| Numbered episode | `ep-{NNNN}` (4-digit zero-padded) | `ep-0418` |
| Unnumbered (conversations, reposts, specials) | `ep-special-{slug}` | `ep-special-my-conversation-with-todd-graves` |

**`episode_number`** in catalog and frontmatter is always an **integer** (`418`) for display, matching, and X/Apple Notes import. **`id`** is the canonical padded string used in paths and chunk ids.

**`slug`** and `founders_url` stay **unpadded** (`418-phil-knight-founder-of-nike`) — they mirror founders.com URLs and must not be renamed.

**Folder name:** `{id}-` + slug without duplicate episode prefix. For numbered episodes, slug `418-phil-knight-founder-of-nike` with `id` `ep-0418` becomes folder `ep-0418-phil-knight-founder-of-nike`. Specials use full slug: `ep-special-{slug}`.

Padding width is `EPISODE_NUMBER_WIDTH = 4` in `ingestion/vault_lib.py` (supports ep-0001 … ep-9999). Plain alphabetical sort of folders then matches episode order.

## Rule 2 — Per-episode filenames (`{folder}.{type}.md`)

Every episode uses the **same folder basename** under each content tree. Inside the folder, filenames are `{folder}.{type}.md`:

| Type | Path |
|------|------|
| Transcript | `content/transcripts/{folder}/{folder}.transcript.md` |
| Raw notes | `content/notes/{folder}/{folder}.notes.md` |
| Expanded datapoints (optional) | `content/notes/{folder}/{folder}.expanded.md` |
| X post | `content/posts/{folder}/{folder}.post.md` |

Allowed `type` values: `transcript`, `notes`, `expanded`, `post`. `.md` remains the real extension.

**Example (episode 418):**

```
content/transcripts/ep-0418-phil-knight-founder-of-nike/ep-0418-phil-knight-founder-of-nike.transcript.md
content/notes/ep-0418-phil-knight-founder-of-nike/ep-0418-phil-knight-founder-of-nike.notes.md
content/posts/ep-0418-phil-knight-founder-of-nike/ep-0418-phil-knight-founder-of-nike.post.md
```

All path helpers live in `ingestion/vault_lib.py` (`folder_name`, `content_filename`, `transcript_path`, `notes_file_path`, etc.). `ingestion/verify.py` enforces both rules on every run.

## Transcript file frontmatter

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Canonical id (`ep-0418`) |
| `episode_number` | if numbered | Integer |
| `title` | yes | Display title |
| `published_at` | yes | `YYYY-MM-DD` |
| `colossus_url` | yes | Official transcript source |
| `founders_url` | yes | Metadata source |
| `source` | yes | Always `colossus` for Phase 1 |
| `fetched_at` | yes | ISO 8601 UTC when saved |

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
| X post | `content/posts/{folder}/{folder}.post.md` |
| Expanded datapoints (optional) | `content/notes/{folder}/{folder}.expanded.md` |
| All posts corpus | `content/posts/_corpus/all-posts.md` |

### `{folder}.notes.md` frontmatter

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Canonical id |
| `episode_number` | if numbered | Integer |
| `title` | yes | From catalog |
| `source` | yes | e.g. `apple_notes_import` |
| `imported_at` | yes | ISO 8601 UTC |

Body must include `## Raw datapoints` with timestamp bullets:

```markdown
## Raw datapoints
- 12:34 — half sentence reference
- 1:05:00 — another bullet
```

Timestamps use `MM:SS` or `H:MM:SS` before the em dash.

### `{folder}.post.md` frontmatter

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Canonical id |
| `episode_number` | if numbered | Integer |
| `title` | yes | From catalog |
| `x_url` | yes | Canonical X URL |
| `x_post_id` | yes | X post id |
| `published_at` | if known | `YYYY-MM-DD` |
| `source` | yes | `x_csv`, `manual_attribution`, or legacy `x_api` |
| `imported_at` | yes | ISO 8601 UTC |
| `post_kind` | no | `tweet`, `article`, `quote`, `reply` |
| `attribution_note` | no | Manual mapping notes (wrong ep number on X, recap thread, etc.) |
| `alt_source` | no | e.g. `google_doc` when merged |

Body: full post text (thread + self-replies merged). Native X articles may publish as a link tweet only in the API — paste full article text manually when needed (`assign_post_manual.py`).

### `{folder}.expanded.md` (optional)

Generated by datapoint workflow. Sections: `## Expanded datapoints` with quote + takeaway per bullet.

### Catalog sidecars

| File | Purpose |
|------|---------|
| `catalog/unmapped-posts.jsonl` | X posts that could not be matched to an episode |
| `catalog/import-review.md` | Human review queue for ambiguous imports |
