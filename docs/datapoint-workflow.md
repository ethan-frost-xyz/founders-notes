# Datapoint expansion workflow

Turn half-sentence timestamp bullets in `{folder}.notes.md` into full transcript quotes and takeaways — without manually pasting the transcript.

## Files per episode

| File | Role |
|------|------|
| `content/notes/{folder}/{folder}.notes.md` | Raw bullets (`12:34 — …`) |
| `content/transcripts/{folder}/{folder}.transcript.md` | Full transcript |
| `content/notes/{folder}/{folder}.expanded.draft.md` | LLM staging output (review before indexing) |
| `content/notes/{folder}/{folder}.expanded.md` | Canonical expanded notes (optional; indexed for search) |

Promoted `.expanded.md` files feed the **parent tier** of Librarian hybrid search (orchestrator + `catalog/chunks.jsonl` / embeddings); drafts are not indexed. See [retrieval.md](retrieval.md).

## Tunable prompt (source of truth)

Instructions live in [`ingestion/prompts/expand_datapoints.md`](../ingestion/prompts/expand_datapoints.md):

- `<<<SYSTEM>>>` … role, quoting rules, output shape.
- `<<<USER>>>` … template with `{notes}` and `{transcript}` placeholders (`{transcript}` is lookup only — not echoed in output).

Per bullet: `### {timestamp} — {bullet}`, then **Context** (1–2 sentences), **Quote** (verbatim + timestamp), **Key takeaway** (2–3 sentences), with blank lines between fields.

The LLM reply must start with `## Expanded datapoints` on line 1 (required by the parser). **Do not** ask the model for YAML frontmatter — `expand_datapoints_llm.py` wraps the body with canonical episode headers (`content_type`, `created_at`, model metadata, etc.) via `ingestion/lib/markdown_io.py`.

Edit that file to change behavior for both the manual CLI and OpenRouter runs. For A/B tuning, pass a second prompt file to `expand_tune.py` (see below).

## Quick start (Cursor / manual)

1. `@content/notes/ep-0200-.../ep-0200-....notes.md`
2. `@content/transcripts/ep-0200-.../ep-0200-....transcript.md`
3. Paste the prompt from `python notes/expand_datapoints.py --id ep-0200` (optional `--prompt path/to.md`)
4. Save the model output as `{folder}.expanded.md` in the same notes folder (or use the draft → promote flow below)

## Maintenance console (recommended)

For day-to-day work, use the interactive menu (wraps the scripts below):

```bash
cd ingestion
python maintain.py
```

Options include coverage/gaps refresh, next notes path, single-episode or backlog expand (dry-run cost first), pending draft list, promote, chunk rebuild, and expand-run log summary.

**Bulk backfill:** see [`docs/expanded-backfill.md`](expanded-backfill.md) (operator checklist, promote batches, safe behavior during large draft runs).

## Quick start (OpenRouter)

Set in repo root `.env` (see [`.env.example`](../.env.example)):

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` — any model slug from [OpenRouter’s catalog](https://openrouter.ai/models); change in `.env` or pass `--model` per run (docs do not pin a vendor)
- Optional: `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`)

Per-episode override: `python notes/expand_datapoints_llm.py --id ep-0200 --apply --model 'provider/model-id'`. Tune runs: `python notes/expand_tune.py expand --variant A --apply --model 'provider/model-id'`.

**Expand** (one stateless API call per episode — notes + transcript only; no cross-episode context). By default `--apply` **streams** the response and prints time-to-first-token plus `datapoint N/M` as each `###` section arrives; use `--no-stream` for a silent blocking request.

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

Apply runs append structured rows to `catalog/expand-run.jsonl` (gitignored): `status`, token counts, `cost_usd`, `duration_ms`, `run_id` / `variant` (when launched from `expand_tune`).

| Field | Meaning |
|-------|---------|
| `status` | `ok`, `error`, or `skipped` |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | From OpenRouter `usage` when the API call completed |
| `cost_usd` | OpenRouter `usage.cost` when present |
| `duration_ms` | Wall time for the API call |
| `run_id`, `variant` | Set via `EXPAND_RUN_ID` / `EXPAND_VARIANT` (tune subprocesses) |

Monitor a batch:

```bash
python notes/expand_datapoints_llm.py --summarize-log --run-id tune-001 --log-variant A
# or
jq -s 'group_by(.status) | map({status: .[0].status, n: length})' catalog/expand-run.jsonl
```

## Prompt tuning (A/B sandbox, ad-hoc)

Compare **prompt A** vs **prompt B** on a batch you choose without touching `content/notes/` until you promote a winner. Each episode runs in a **fresh subprocess** (no cross-episode or A/B contamination). Outputs live under `ingestion/fixtures/expand-runs/{run_id}/A/` and `.../B/` — **not committed**.

| Prompt | Typical file |
|--------|----------------|
| A | `ingestion/prompts/expand_datapoints.md` |
| B | Your copy or fork (e.g. `ingestion/prompts/expand_datapoints.variant-b.md`) |

Start from [`ingestion/fixtures/expand-tune-batch.example.json`](../ingestion/fixtures/expand-tune-batch.example.json): copy to a local batch file (e.g. `catalog/expand-tune-batch.json`, gitignored) with your `episode_ids` list.

```bash
cd ingestion
cp fixtures/expand-tune-batch.example.json ../catalog/expand-tune-batch.json   # edit episode_ids
python notes/expand_tune.py init --batch-file ../catalog/expand-tune-batch.json

python notes/expand_tune.py expand --variant A --dry-run
python notes/expand_tune.py expand --variant A --apply
python notes/expand_tune.py expand --variant B --apply --prompt prompts/expand_datapoints.variant-b.md

python notes/expand_tune.py report
python notes/expand_tune.py verify
python notes/expand_tune.py promote --variant B --apply
python search/build_chunks.py
```

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
