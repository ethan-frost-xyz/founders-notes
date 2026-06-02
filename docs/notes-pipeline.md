# Notes pipeline (vault-native)

Daily study notes for Founders episodes: timestamp bullets in git, edited on phone or Mac.

## Intentional incompleteness

This vault is **actively being filled in**, not fully backfilled. As of each `verify.py` run, many episodes have an empty `{folder}.notes.md` scaffold (header + `## Raw datapoints` only) because that episode has not been listened to yet.

- **`catalog/gaps.md` “notes without datapoints”** = backlog / not started, **not** a broken import.
- **Progress metric:** `notes with datapoints` count should climb over weeks as you listen (~1 episode per day).
- Agents and tools should use `notes/scaffold_notes.py --next` and help with the **current** episode, not bulk-generate bullets for hundreds of episodes.

## File layout

Per episode (padded id, unified filename):

```
content/notes/ep-0200-{slug}/ep-0200-{slug}.notes.md
```

See [episode-id-rules.md](episode-id-rules.md) for frontmatter and bullet format.

## Format

```markdown
---
id: "ep-0200"
episode_number: 200
title: "…"
content_type: "notes"
source: "vault_native"
published_at: "2024-06-01"
founders_url: "https://www.founderspodcast.com/episodes/..."
created_at: "2026-05-21T12:00:00Z"
imported_at: "2026-05-21T12:00:00Z"
---

## Raw datapoints

- 12:34 — half-sentence hook from the episode
- 1:05:00 — another moment
```

- Use em dash (`—`) after the timestamp.
- Timestamps: `MM:SS` or `H:MM:SS`.
- `episode_number` in frontmatter is an integer; `id` is always 4-digit padded (`ep-0200`).

## Phone: Working Copy (recommended)

1. Install [Working Copy](https://workingcopy.app/) and clone this repo.
2. After listening, open the episode’s `.notes.md` (folders sort in episode order: `ep-0190` … `ep-0417`).
3. Append bullets under `## Raw datapoints`.
4. Commit and push (after each episode or end of day).

Optional: open the file in Runestone or iA Writer via Working Copy’s “Open in…” for a richer editor.

**Avoid** the GitHub mobile app for daily edits — it is not built for nested markdown files.

### Find the next episode file

```bash
cd ingestion
python notes/scaffold_notes.py --next
```

Prints the relative path to the first numbered episode missing a notes file (or the next empty slot in your workflow).

## Mac / Cursor

```bash
git pull
# edit content/notes/ep-NNNN-.../ep-NNNN-....notes.md
cd ingestion && python pipeline/verify.py
python search/build_chunks.py   # refresh search index after adding bullets
```

In Cursor: `@content/notes/ep-0200-.../ep-0200-....notes.md` plus the matching transcript.

## Scaffolding empty notes

Episodes **0190+** ship with empty scaffolds (`source: vault_native`). To create scaffolds for new catalog rows:

```bash
cd ingestion
python notes/scaffold_notes.py --missing    # any complete transcript without .notes.md
python notes/scaffold_notes.py --id ep-0200 # single episode
python notes/scaffold_notes.py --dry-run    # preview
```

New episodes (after `sync_new.py --apply`):

```bash
python pipeline/map_colossus.py
python transcripts/fetch_transcripts.py --id ep-0418
python notes/scaffold_notes.py --missing
python pipeline/verify.py
```

## Apple Notes import (historical)

Episodes 1–189 were bulk-imported once from Apple Notes (`source: apple_notes_import` in frontmatter). **Going forward, edit notes only in this repo** — Working Copy on phone, Cursor on Mac. The one-shot importer was removed; see git history before commit `2fb9d22` if needed.

## Datapoint expansion

When raw bullets are done, expand quotes + takeaways: [datapoint-workflow.md](datapoint-workflow.md). For Telegram-first vs `maintain.py` backfill, see [operations.md](operations.md).

```bash
python notes/expand_datapoints.py --id ep-0200                    # print prompt (manual / Cursor)
python notes/expand_datapoints_llm.py --id ep-0200 --apply        # OpenRouter → .expanded.draft.md
python notes/expand_datapoints_llm.py --promote --id ep-0200 --apply
```

## Coverage in gaps.md

`python pipeline/verify.py` reports note metrics and optional expansion progress:

| Metric | Meaning |
|--------|---------|
| **Notes files** | `{folder}.notes.md` exists (includes empty scaffolds) |
| **Notes with datapoints** | At least one `MM:SS —` bullet (episode actually noted) |
| **Expanded notes** | `{folder}.expanded.md` exists |
| **Expanded drafts** | `{folder}.expanded.draft.md` exists (pending promote) |

Empty scaffolds count as files but not as datapoints until you add bullets after listening. The long “notes without datapoints” list in `catalog/gaps.md` is **expected** during daily catch-up.
