# Episode ID and schema rules

## Episode IDs

| Case | `id` format | Example |
|------|-------------|---------|
| Numbered episode | `ep-{number}` | `ep-418` |
| Unnumbered (conversations, reposts, specials) | `ep-special-{slug}` | `ep-special-my-conversation-with-todd-graves` |

**Folder name:** `{id}-` + slug without duplicate episode prefix. For numbered episodes, slug `418-phil-knight-founder-of-nike` becomes folder `ep-418-phil-knight-founder-of-nike`. Specials use full slug: `ep-special-{slug}`.

Full path: `content/transcripts/ep-418-phil-knight-founder-of-nike/ep-418-phil-knight-founder-of-nike.md` (filename matches folder name)

Body structure:

1. `## Description` — Colossus episode blurb above the transcript
2. `## Transcript` — full transcript text

## `transcript.md` frontmatter

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Canonical id |
| `episode_number` | if numbered | Integer |
| `title` | yes | Display title |
| `published_at` | yes | `YYYY-MM-DD` |
| `colossus_url` | yes | Official transcript source |
| `founders_url` | yes | Metadata source |
| `source` | yes | Always `colossus` for Phase 1 |
| `fetched_at` | yes | ISO 8601 UTC when saved |

Body: plain transcript text below the closing `---` of frontmatter.

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
- **complete** — `transcript.md` on disk
- **failed** — Fetch error; see `last_error`
- **coming_soon** — Colossus page has no transcript yet
- **no_transcript** — Confirmed no transcript exists for this entry
