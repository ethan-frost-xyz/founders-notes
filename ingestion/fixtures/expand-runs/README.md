# Expand prompt tuning runs (sandbox)

Outputs from `notes/expand_tune.py` land here. **Gitignored** except this README.

## Layout

```
expand-runs/{run_id}/
  manifest.json
  A/{folder}/{folder}.expanded.draft.md   # prompt A
  B/{folder}/{folder}.expanded.draft.md   # prompt B
```

## Cost

Default batch: **10 episodes** in [`catalog/expand-tune-batch.json`](../../../catalog/expand-tune-batch.json).

Full A/B cycle = **20 OpenRouter calls** (10 × prompt A + 10 × prompt B). Run `--dry-run` first — prints a per-episode table with ~input tokens and optional `$` if `OPENROUTER_ESTIMATE_INPUT_USD_PER_MTOK` is set in `.env`.

## Isolation

`notes/expand_tune.py expand` runs **one subprocess per episode** (fresh Python process, single `--id`, stateless API). No in-process batch expand for tune mode.

## Prompts

| Variant | File | Style |
|---------|------|--------|
| A | `ingestion/prompts/expand_datapoints.md` | Faithful: Context, Quote (**bold** core + unbolded flank), Key takeaway; worked example |
| B | `ingestion/prompts/expand_datapoints.candidate.md` | Retrieval-tight: same labels, shorter rules; **bold** key phrase in a shorter quote |

`init` copies A → B only if B is missing. For format A/B tests, edit B while keeping A frozen for the run.

## Quick start

```bash
cd ingestion
python notes/expand_tune.py init --run-id tune-001
python notes/expand_tune.py expand --run-id tune-001 --variant A --dry-run
python notes/expand_tune.py expand --run-id tune-001 --variant A --apply
python notes/expand_tune.py expand --run-id tune-001 --variant B --apply
python notes/expand_tune.py report --run-id tune-001
python notes/expand_tune.py promote --run-id tune-001 --variant B --apply
```

See [`docs/datapoint-workflow.md`](../../../docs/datapoint-workflow.md).
