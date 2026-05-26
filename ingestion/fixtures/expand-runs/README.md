# Expand prompt tuning runs

Outputs from `notes/expand_tune.py`. **Committed to git** so A/B drafts are available for prompt comparison without re-running the API.

Default run: **`baseline/`** (10 episodes × prompt A + B).

## Layout

```
expand-runs/{run_id}/
  manifest.json
  A/{folder}/{folder}.expanded.draft.md   # prompt A
  B/{folder}/{folder}.expanded.draft.md   # prompt B
```

## Cost

Default batch: **10 episodes** in [`catalog/expand-tune-batch.json`](../../../catalog/expand-tune-batch.json).

Full A/B cycle = **20 OpenRouter calls** (10 × prompt A + 10 × prompt B). Run `--dry-run` first — prints a per-episode table with ~input tokens and `$` estimates from the OpenRouter model catalog (`OPENROUTER_MODEL` required).

## Isolation

`notes/expand_tune.py expand` runs **one subprocess per episode** (fresh Python process, single `--id`, stateless API). No in-process batch expand for tune mode.

## Prompts

| Variant | File | Style |
|---------|------|--------|
| A | `ingestion/prompts/expand_datapoints.md` | Faithful: Context, Quote (**bold** core + unbolded flank), Key takeaway; worked example |
| B | `ingestion/prompts/expand_datapoints.candidate.md` | Retrieval-tight: same labels, shorter rules; **bold** key phrase in a shorter quote |

`init` copies A → B only if B is missing. For format A/B tests, edit B while keeping A frozen for the run.

## Commands

```bash
cd ingestion
python notes/expand_tune.py init
python notes/expand_tune.py expand --variant A --dry-run
python notes/expand_tune.py expand --variant A --apply
python notes/expand_tune.py expand --variant B --apply
python notes/expand_tune.py report
python notes/expand_tune.py verify
```

Full refresh: add `--force` to `init` and both `expand` runs.

## Tuning loop

| Step | Command |
|------|---------|
| Compare current A/B | `python notes/expand_tune.py report` |
| Structural check | `python notes/expand_tune.py verify` |
| Edit prompt B | `ingestion/prompts/expand_datapoints.candidate.md` |
| Regenerate B only | `python notes/expand_tune.py expand --variant B --apply --force` |
| Commit updated drafts | `git add ingestion/fixtures/expand-runs/` |
| New experimental run | `python notes/expand_tune.py init --run-id tune-002` → expand → commit |

After prompt edits, `verify` warns on `prompt_hash` mismatch — re-expand with `--force`, then commit.

See [`docs/datapoint-workflow.md`](../../../docs/datapoint-workflow.md).
