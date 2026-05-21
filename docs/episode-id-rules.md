# Episode ID and schema rules

## Episode IDs

| Case | `id` format | Example |
|------|-------------|---------|
| Numbered episode | `ep-{number}` | `ep-418` |
| Unnumbered (conversations, reposts, specials) | `ep-special-{slug}` | `ep-special-my-conversation-with-todd-graves` |

**Folder name:** `{id}-{slug}` where `slug` is the last path segment from founderspodcast.com (e.g. `418-phil-knight-founder-of-nike`).

Full path: `content/transcripts/ep-418-phil-knight-founder-of-nike/transcript.md`

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
