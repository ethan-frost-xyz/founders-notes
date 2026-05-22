# Expand prompt tuning runs (sandbox)

Outputs from `expand_tune.py` land here. **Gitignored** except this README.

## Layout

```
expand-runs/{run_id}/
  manifest.json
  A/{folder}/{folder}.expanded.draft.md   # prompt A
  B/{folder}/{folder}.expanded.draft.md   # prompt B
```

## Cost

Default batch: **10 episodes** in [`catalog/expand-tune-batch.json`](../../../catalog/expand-tune-batch.json).

Full A/B cycle = **20 OpenRouter calls** (10 × prompt A + 10 × prompt B). Run `--dry-run` first for char estimates.

## Isolation

`expand_tune.py expand` runs **one subprocess per episode** (fresh Python process, single `--id`, stateless API). No in-process batch expand for tune mode.

## Prompts

| Variant | File |
|---------|------|
| A (baseline) | `ingestion/prompts/expand_datapoints.md` |
| B (candidate) | `ingestion/prompts/expand_datapoints.candidate.md` |

`init` copies baseline → candidate if candidate is missing. Edit B for experiments; keep A frozen for the run.

## Quick start

```bash
cd ingestion
python expand_tune.py init --run-id tune-001
python expand_tune.py expand --run-id tune-001 --variant A --dry-run
python expand_tune.py expand --run-id tune-001 --variant A --apply
python expand_tune.py expand --run-id tune-001 --variant B --apply
python expand_tune.py report --run-id tune-001
python expand_tune.py promote --run-id tune-001 --variant B --apply
```

See [`docs/datapoint-workflow.md`](../../../docs/datapoint-workflow.md).
