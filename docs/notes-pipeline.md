# Notes pipeline (vault-native)

Daily study notes for Founders episodes: timestamp bullets in git, edited on phone or Mac.

## Intentional incompleteness

This vault is **actively being filled in**, not fully backfilled. As of each `verify.py` run, many episodes have an empty `{folder}.notes.md` scaffold (header + `## Raw datapoints` only) because that episode has not been listened to yet.

- **`catalog/gaps.md` “notes without datapoints”** = backlog / not started, **not** a broken import.
- **Progress metric:** `notes with datapoints` count should climb over weeks as you listen (~1 episode per day).
- Agents and tools should use `scaffold_notes.py --next` and help with the **current** episode, not bulk-generate bullets for hundreds of episodes.

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
source: "vault_native"
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
python scaffold_notes.py --next
```

Prints the relative path to the first numbered episode missing a notes file (or the next empty slot in your workflow).

## Mac / Cursor

```bash
git pull
# edit content/notes/ep-NNNN-.../ep-NNNN-....notes.md
cd ingestion && python verify.py
python build_chunks.py   # refresh search index after adding bullets
```

In Cursor: `@content/notes/ep-0200-.../ep-0200-....notes.md` plus the matching transcript.

## Scaffolding empty notes

Episodes **0190+** ship with empty scaffolds (`source: vault_native`). To create scaffolds for new catalog rows:

```bash
cd ingestion
python scaffold_notes.py --missing    # any complete transcript without .notes.md
python scaffold_notes.py --id ep-0200 # single episode
python scaffold_notes.py --dry-run    # preview
```

New episodes (after `sync_new.py --apply`):

```bash
python map_colossus.py
python fetch_transcripts.py --id ep-0418
python scaffold_notes.py --missing
python verify.py
```

## Apple Notes import (archived)

Episodes 1–189 were bulk-imported once from Apple Notes (`source: apple_notes_import` in frontmatter). **Going forward, edit notes only in this repo** — Working Copy on phone, Cursor on Mac.

Recovery only (overwrites `catalog/import-review.md` if run without `--dry-run`): [`ingestion/migrations/import_notes_apple.py`](../ingestion/migrations/import_notes_apple.py). See [`ingestion/migrations/README.md`](../ingestion/migrations/README.md).

## Datapoint expansion

When raw bullets are done, expand quotes + takeaways: [datapoint-workflow.md](datapoint-workflow.md).

```bash
python expand_datapoints.py --id ep-0200
```

## Coverage in gaps.md

`python verify.py` reports two note metrics:

| Metric | Meaning |
|--------|---------|
| **Notes files** | `{folder}.notes.md` exists (includes empty scaffolds) |
| **Notes with datapoints** | At least one `MM:SS —` bullet (episode actually noted) |

Empty scaffolds count as files but not as datapoints until you add bullets after listening. The long “notes without datapoints” list in `catalog/gaps.md` is **expected** during daily catch-up.
