# Datapoint expansion workflow

Turn half-sentence timestamp bullets in `{folder}.notes.md` into full transcript quotes and takeaways — without manually pasting the transcript.

## Files per episode

| File | Role |
|------|------|
| `content/notes/{folder}/{folder}.notes.md` | Raw bullets (`12:34 — …`) |
| `content/transcripts/{folder}/{folder}.transcript.md` | Full transcript |
| `content/notes/{folder}/{folder}.expanded.draft.md` | LLM staging output (review before indexing) |
| `content/notes/{folder}/{folder}.expanded.md` | Canonical expanded notes (optional; indexed for search) |

## Tunable prompt (source of truth)

Instructions live in [`ingestion/prompts/expand_datapoints.md`](../ingestion/prompts/expand_datapoints.md):

- `<<<SYSTEM>>>` … role, quoting rules, output shape.
- `<<<USER>>>` … template with `{notes}` and `{transcript}` placeholders.

Edit that file to change behavior for both the manual CLI and OpenRouter runs.

## Quick start (Cursor / manual)

1. `@content/notes/ep-0200-.../ep-0200-....notes.md`
2. `@content/transcripts/ep-0200-.../ep-0200-....transcript.md`
3. Paste the prompt from `python expand_datapoints.py --id ep-0200` (optional `--prompt path/to.md`)
4. Save the model output as `{folder}.expanded.md` in the same notes folder (or use the draft → promote flow below)

## Quick start (OpenRouter)

Set in repo root `.env` (see [`.env.example`](../.env.example)):

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (e.g. provider slug from OpenRouter’s model list)
- Optional: `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`)

**Expand** (one stateless API call per episode — notes + transcript only; no cross-episode context):

```bash
cd ingestion
python expand_datapoints_llm.py --id ep-0200 --dry-run    # char estimates, no API
python expand_datapoints_llm.py --id ep-0200 --apply     # writes .expanded.draft.md
python expand_datapoints_llm.py --missing-expanded --apply --limit 5
python expand_datapoints_llm.py --from 1 --to 50 --apply --subprocess   # one process per episode
```

**Promote** draft → canonical `.expanded.md` (validates structure vs raw bullets; deletes draft on success):

```bash
python expand_datapoints_llm.py --promote --id ep-0200 --dry-run
python expand_datapoints_llm.py --promote --id ep-0200 --apply
python expand_datapoints_llm.py --promote --all-ready --apply
```

After promoting, refresh search chunks:

```bash
python build_chunks.py
```

Runs append to `catalog/expand-run.jsonl` (gitignored) for resume / debugging.

## CLI (prompt only, no API)

```bash
python expand_datapoints.py --id ep-0200          # print combined prompt
python expand_datapoints.py --id ep-0200 --copy   # macOS clipboard
python expand_datapoints.py --id ep-0200 --write  # scaffold {folder}.expanded.md (legacy helper)
```

## Quality tips

- Fix bad timestamps in `{folder}.notes.md` before expanding.
- Review `.expanded.draft.md` before `--promote`; promotion checks section count vs bullets.
- Prefer committing `.expanded.md` only when satisfied — you can regenerate drafts with `--force`.
- Cross-episode themes: use `python search.py` or `content/posts/_corpus/all-posts.md` after posts are imported.
