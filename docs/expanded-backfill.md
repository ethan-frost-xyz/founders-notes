# Expanded notes backfill (operator guide)

Bulk workflow for turning timestamp bullets in `{folder}.notes.md` into reviewable `.expanded.draft.md` files, then canonical `{folder}.expanded.md` for search.

**Authoritative counts:** [`catalog/gaps.md`](../catalog/gaps.md) (regenerate via `python pipeline/verify.py` or `python maintain.py` → menu 1).

**Related:** [datapoint-workflow.md](datapoint-workflow.md) (prompt shape, tune sandbox), [retrieval.md](retrieval.md) (when chunks matter), [manual-operations.md](manual-operations.md) (index: chunks + parent-tier embeddings), [Telegram vault agent](telegram-vault-agent.md) (reads **`.expanded.md` only**, not drafts).

---

## Eligibility

An episode is in the **expand backlog** when all of the following hold:

| Requirement | Check |
|-------------|--------|
| Numbered episode | `episode_number` in catalog |
| Transcript complete | `transcript_status == complete` |
| Raw datapoints | `{folder}.notes.md` has `MM:SS —` bullets |
| Not yet canonical | No `{folder}.expanded.md` |

Skipped automatically: empty scaffolds, episodes without bullets, specials without numbers.

**Not indexed until promote:** `.expanded.draft.md` is staging only; `build_chunks.py` reads `.expanded.md` only.

---

## Prerequisites

1. Repo root `.env` with `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` (see [`.env.example`](../.env.example)).
2. `ingestion` venv: `cd ingestion && source .venv/bin/activate && pip install -r requirements.txt`
3. Phase 1 green: `python pipeline/verify.py` (no blocking transcript gaps).

---

## File roles

| File | Role |
|------|------|
| `{folder}.notes.md` | Source bullets (you edit while listening) |
| `{folder}.expanded.draft.md` | LLM staging — review before promote |
| `{folder}.expanded.md` | Canonical expanded notes — indexed for search |
| `catalog/expand-run.jsonl` | Gitignored API run log (tokens, cost, status) |

Prompt source of truth: [`ingestion/prompts/expand_datapoints.md`](../ingestion/prompts/expand_datapoints.md).

---

## Recommended loop (maintenance console)

```bash
cd ingestion
python maintain.py
```

| Step | Menu | Action |
|------|------|--------|
| 0 | **1** | Refresh coverage; note **backlog (datapoints, no expanded)** |
| 1 | **5** | Dry-run cost — backlog scope, set **limit** for a pilot batch |
| 2 | **4** | Expand backlog — confirm **apply**; optional subprocess per episode |
| 3 | — | Review drafts in editor |
| 4 | **6** | List drafts + validation errors/warnings |
| 5 | **7** | Promote — `all-ready` or id/range; confirm apply |
| 6 | **8** | Rebuild chunks + embeddings (`reindex_vault` — same recipe as Mac mini `sync-and-index.sh`) |
| 7 | **10** | Summarize `expand-run.jsonl` (cost rollup) |

Repeat steps 2–6 until backlog is acceptable.

**Telegram vault agent host:** After promote waves, run Telegram `/sync` when idle, `sync-and-index.sh`, or `python lib/reindex_vault.py` from `ingestion/` on the Mac mini so parent-tier search includes **Quote** / **Key takeaway** from canonical `.expanded.md`. The agent does not read `.expanded.draft.md`.

---

## CLI equivalents

```bash
cd ingestion

# Pilot: cost only
python notes/expand_datapoints_llm.py --missing-expanded --dry-run --limit 10

# Write drafts
python notes/expand_datapoints_llm.py --missing-expanded --apply --limit 10

# Optional range
python notes/expand_datapoints_llm.py --from 1 --to 50 --missing-expanded --apply

# Memory isolation (still sequential)
python notes/expand_datapoints_llm.py --missing-expanded --apply --subprocess --limit 20

# After review
python notes/expand_datapoints_llm.py --promote --all-ready --apply
python search/build_chunks.py
# On Mac mini running the vault agent (when implemented):
#   ./services/telegram/deploy/sync-and-index.sh

# Monitor spend
python notes/expand_datapoints_llm.py --summarize-log --last 50
```

Single episode: `--id ep-0200` instead of `--missing-expanded`.

---

## Bulk draft run (in progress)

While a large **draft-only** run is executing:

### Safe

- Read `catalog/expand-run.jsonl` and menu **10** summaries.
- Spot-check finished drafts (do not promote until the batch you care about is done).
- Doc/plan work, tests, Telegram vault agent planning (no writes under `content/notes/` for in-flight episodes).
- Fix bullets in `.notes.md` for episodes **not** currently expanding.

### Avoid

| Action | Why |
|--------|-----|
| `--promote` on in-flight episodes | Draft may be incomplete |
| `build_chunks.py` expecting expanded search | Drafts are not chunked |
| `--force` re-expand same id in parallel | Overwrites draft mid-write |
| Editing `expand_datapoints.md` mid-batch | Workers already started may use old prompt |

### Parallel workers (manual)

The console and `--subprocess` batch modes are **sequential**. For ~N concurrent episodes, run N separate processes with distinct `--id` and `--no-stream`:

```bash
python notes/expand_datapoints_llm.py --id ep-0010 --apply --no-stream &
python notes/expand_datapoints_llm.py --id ep-0011 --apply --no-stream &
# cap concurrency; wait for each wave
wait
```

Future: `--jobs N` on `expand_datapoints_llm.py` (not implemented yet).

---

## Review checklist (per draft)

- [ ] `## Expanded datapoints` on line 1 of model body (parser requirement; frontmatter added by script).
- [ ] One `### {timestamp} — {bullet}` per raw bullet (count vs `.notes.md`).
- [ ] Each block has **Context**, **Quote**, **Key takeaway** (promote warns if missing).
- [ ] Quotes are contiguous transcript text; fix bad timestamps in `.notes.md` and re-expand with `--force` if needed.
- [ ] Episodes listed under gaps **“Bullets missing timestamp”** — fix bullets before trusting quotes.

---

## Promote in batches

Promoting 100+ drafts at once is fine structurally; review quality in slices:

```bash
python notes/expand_datapoints_llm.py --promote --from 1 --to 50 --apply
python search/build_chunks.py
```

`--promote --all-ready` promotes every production draft that passes validation.

On success, draft file is deleted and `.expanded.md` is written with canonical frontmatter.

---

## Prompt A/B vs production backfill

| Workflow | Tool | Output |
|----------|------|--------|
| **Production backfill** | `expand_datapoints_llm.py --missing-expanded` | `content/notes/.../*.expanded.draft.md` |
| **Prompt tune sandbox** | `expand_tune.py` / menu **9** | `ingestion/fixtures/expand-runs/{run_id}/A|B/` |

Do not confuse tune fixtures with production drafts. Promote tune winners via `expand_tune.py promote`, not production `--promote`.

---

## When things fail

| Symptom | Likely fix |
|---------|------------|
| `No episodes matched selection` | No bullets, or `.expanded.md` already exists |
| `Set OPENROUTER_API_KEY` | Root `.env` |
| Promote blocked | Validation errors — menu **6** or fix draft/notes |
| `[error]` in expand log | Re-run single `--id`; check transcript/notes exist |
| High cost | Lower `--limit`; dry-run first; cheaper `--model` |

---

## Done when

- **Draft phase:** Backlog count in menu **1** unchanged for “no expanded” but drafts exist — you are in review.
- **Shipped phase:** Canonical `.expanded.md` count matches what you trust; `build_chunks.py` run; `search/search.py` finds expanded sections.
- **Daily ritual unchanged:** New episodes still get bullets first (`scaffold_notes.py --next`), then expand/promote for that episode only.
