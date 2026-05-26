# Notes and expansion

Scaffold study-note files and expand timestamp bullets into full quotes + takeaways.

Run from `ingestion/`:

```bash
python notes/scaffold_notes.py --next
python notes/expand_datapoints.py --id ep-0200
python notes/expand_datapoints_llm.py --id ep-0200 --apply
python notes/expand_datapoints_llm.py --promote --id ep-0200 --apply
```

See [`docs/notes-pipeline.md`](../../docs/notes-pipeline.md) and [`docs/datapoint-workflow.md`](../../docs/datapoint-workflow.md).

## Scripts

| Script | Purpose |
|--------|---------|
| `scaffold_notes.py` | Create empty `{folder}.notes.md` (`--next`, `--missing`, `--id`) |
| `expand_datapoints.py` | Build expansion prompt from notes + transcript (manual / Cursor) |
| `expand_datapoints_llm.py` | OpenRouter → `.expanded.draft.md`; `--promote` → `.expanded.md` |
| `expand_tune.py` | 23-episode A/B under `fixtures/expand-runs/` (`report`, `verify`; default run `baseline/`) |

## Environment

| Variable | Used by |
|----------|---------|
| `OPENROUTER_API_KEY` | `expand_datapoints_llm.py`, `expand_tune.py` |
| `OPENROUTER_MODEL` | Default expand model — any OpenRouter slug; `--model` overrides per run |

Prompts: [`../prompts/`](../prompts/).

## Flags (common)

| Flag | Meaning |
|------|---------|
| `--id ep-NNNN` | Single episode |
| `--dry-run` / `--apply` | Preview vs write |
| `--force` | Regenerate draft / overwrite empty scaffold |
| `--no-stream` | Blocking API only (no live `datapoint k/M` progress) |
| `--subprocess` | `expand_datapoints_llm.py` — one process per episode |

## Downstream

After expansion: `search/build_chunks.py` to refresh `catalog/chunks.jsonl`.
