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
| `expand_tune.py` | Ad-hoc A/B under `fixtures/expand-runs/` (`init`, `expand`, `report`, `verify`, `promote`; local batch JSON) |
| `estimate_timestamps.py` | Estimate `MM:00` for `- —` bullets (`--all-missing`, `--apply`; needs `duration_seconds` in catalog) |

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

After promote to `.expanded.md`, refresh the index:

- **Chunks:** `search/build_chunks.py` → `catalog/chunks.jsonl`
- **Embeddings (Telegram / parent-tier):** `search/build_embeddings.py` when the bot host or local env has embed keys — see [`docs/operations.md`](../../docs/operations.md)

On the Mac mini, `services/telegram/deploy/sync-and-index.sh` runs both after `git pull`.
