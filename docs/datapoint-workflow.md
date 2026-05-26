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
- `<<<USER>>>` … template with `{notes}` and `{transcript}` placeholders (`{transcript}` is lookup only — not echoed in output).

Per bullet: `### {timestamp} — {bullet}`, then **Context** (1–2 sentences), **Quote** (verbatim + timestamp), **Key takeaway** (2–3 sentences), with blank lines between fields.

Edit that file to change behavior for both the manual CLI and OpenRouter runs. Candidate prompt B: `expand_datapoints.candidate.md`.

## Quick start (Cursor / manual)

1. `@content/notes/ep-0200-.../ep-0200-....notes.md`
2. `@content/transcripts/ep-0200-.../ep-0200-....transcript.md`
3. Paste the prompt from `python notes/expand_datapoints.py --id ep-0200` (optional `--prompt path/to.md`)
4. Save the model output as `{folder}.expanded.md` in the same notes folder (or use the draft → promote flow below)

## Quick start (OpenRouter)

Set in repo root `.env` (see [`.env.example`](../.env.example)):

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (e.g. provider slug from OpenRouter’s model list)
- Optional: `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`)

**Expand** (one stateless API call per episode — notes + transcript only; no cross-episode context):

```bash
cd ingestion
python notes/expand_datapoints_llm.py --id ep-0200 --dry-run    # char estimates, no API
python notes/expand_datapoints_llm.py --id ep-0200 --apply     # writes .expanded.draft.md
python notes/expand_datapoints_llm.py --missing-expanded --apply --limit 5
python notes/expand_datapoints_llm.py --from 1 --to 50 --apply --subprocess   # one process per episode
```

**Promote** draft → canonical `.expanded.md` (validates structure vs raw bullets; deletes draft on success):

```bash
python notes/expand_datapoints_llm.py --promote --id ep-0200 --dry-run
python notes/expand_datapoints_llm.py --promote --id ep-0200 --apply
python notes/expand_datapoints_llm.py --promote --all-ready --apply
```

After promoting, refresh search chunks:

```bash
python search/build_chunks.py
```

Runs append to `catalog/expand-run.jsonl` (gitignored) for resume / debugging.

## Prompt tuning (10-episode A/B sandbox)

Compare **prompt A** vs **prompt B** on a fixed batch without touching `content/notes/` until you promote a winner. Each episode runs in a **fresh subprocess** (no cross-episode or A/B contamination).

Batch: [`catalog/expand-tune-batch.json`](../catalog/expand-tune-batch.json) (10 episodes). Outputs: `ingestion/fixtures/expand-runs/{run_id}/A/` and `.../B/` (gitignored).

| Prompt | File |
|--------|------|
| A (faithful format) | `ingestion/prompts/expand_datapoints.md` — Context, Quote (bold core + flank), Key takeaway |
| B (retrieval-tight) | `ingestion/prompts/expand_datapoints.candidate.md` — same fields, shorter rules; **bold** key phrase in a shorter quote |

Expanded output per bullet: `### {timestamp} — {bullet}`, then Context / Quote / Key takeaway (blank line between fields). TRANSCRIPT is API input only — never echoed in the output.

```bash
cd ingestion
python notes/expand_tune.py init --run-id tune-001
# Edit prompts/expand_datapoints.candidate.md (prompt B)

python notes/expand_tune.py expand --run-id tune-001 --variant A --dry-run  # cost table + $ from OpenRouter catalog
python notes/expand_tune.py expand --run-id tune-001 --variant A --apply   # 10 subprocesses
python notes/expand_tune.py expand --run-id tune-001 --variant B --apply   # 10 subprocesses

python notes/expand_tune.py report --run-id tune-001
python notes/expand_tune.py promote --run-id tune-001 --variant B --apply  # winner → .expanded.md
python search/build_chunks.py
```

Full A/B apply = **20 API calls**. See [`ingestion/fixtures/expand-runs/README.md`](../ingestion/fixtures/expand-runs/README.md).

## CLI (prompt only, no API)

```bash
python notes/expand_datapoints.py --id ep-0200          # print combined prompt
python notes/expand_datapoints.py --id ep-0200 --copy   # macOS clipboard
python notes/expand_datapoints.py --id ep-0200 --write  # scaffold {folder}.expanded.md (legacy helper)
```

## Quality tips

- Fix bad timestamps in `{folder}.notes.md` before expanding.
- Review `.expanded.draft.md` before `--promote`; promotion checks `###` section count vs bullets and warns if Context / Quote / Key takeaway are missing.
- Prefer committing `.expanded.md` only when satisfied — you can regenerate drafts with `--force`.
- Cross-episode themes: use `python search/search.py` or `content/posts/_corpus/all-posts.md` after posts are imported.
