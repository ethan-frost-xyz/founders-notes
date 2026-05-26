# Expand prompt tuning runs

Outputs from `notes/expand_tune.py`. **Committed to git** so A/B drafts are available for prompt comparison without re-running the API.

Default run: **`baseline/`** (23 episodes × prompt A + B — see [`catalog/expand-tune-batch.json`](../../../catalog/expand-tune-batch.json)).

## Layout

```
expand-runs/{run_id}/
  manifest.json
  A/{folder}/{folder}.expanded.draft.md   # prompt A
  B/{folder}/{folder}.expanded.draft.md   # prompt B
```

## Cost

Default batch: **23 episodes** in [`catalog/expand-tune-batch.json`](../../../catalog/expand-tune-batch.json) (ep 10–180 every 10 where notes exist, plus curated ep-0001, ep-0022, ep-0066, ep-0105, ep-0189).

Full A/B cycle = **46 OpenRouter calls** (23 × prompt A + 23 × prompt B). Run `--dry-run` first — prints a per-episode table with ~input tokens and `$` estimates from whatever model is set in `OPENROUTER_MODEL` (or `--model`). The run’s model is recorded in `manifest.json` and draft frontmatter, not in these docs.

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

During `--apply`, the parent prints `N/M` per episode (M = batch size); each child streams progress (`waiting for API…`, `first output`, `datapoint k/M`). Add `--no-stream` on `expand` to disable live section progress.

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
