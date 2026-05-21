# Datapoint expansion workflow

Turn half-sentence timestamp bullets in `notes.md` into full transcript quotes and takeaways — without manually pasting the transcript.

## Files per episode

| File | Role |
|------|------|
| `content/notes/{folder}/notes.md` | Raw bullets (`12:34 — …`) |
| `content/transcripts/{folder}/{folder}.md` | Full transcript |
| `content/notes/{folder}/expanded.md` | Output (optional, commit when satisfied) |

## Quick start (Cursor)

1. `@content/notes/ep-200-.../notes.md`
2. `@content/transcripts/ep-200-.../ep-200-....md`
3. Paste the prompt from `python expand_datapoints.py --id ep-200` (or use the template below)
4. Save the model output as `expanded.md` in the same notes folder

## Quick start (Gemini / other)

```bash
cd ingestion
python expand_datapoints.py --id ep-200 --copy
```

Copies a single prompt (notes + transcript) to the clipboard on macOS, or prints to stdout.

## Prompt template

```
You are expanding Founders podcast study notes.

For each line under "## Raw datapoints" in NOTES:
- Find the matching moment in TRANSCRIPT using the timestamp (MM:SS or H:MM:SS).
- Quote the relevant transcript passage verbatim (1–3 sentences).
- Write one clear takeaway.

Output markdown:

## Expanded datapoints

### 12:34 — [original bullet text]
**Quote:** "…"
**Takeaway:** …

Repeat for every bullet. If timestamp is ambiguous, note uncertainty.
```

## CLI

```bash
python expand_datapoints.py --id ep-200          # print prompt
python expand_datapoints.py --id ep-200 --copy   # macOS clipboard
python expand_datapoints.py --id ep-200 --write  # scaffold expanded.md with prompt in HTML comment
```

## Quality tips

- Fix bad timestamps in `notes.md` before expanding.
- Prefer `expanded.md` only when you're happy — it's safe to regenerate.
- Cross-episode themes: use `python search.py` or `content/posts/_corpus/all-posts.md` after posts are imported.
