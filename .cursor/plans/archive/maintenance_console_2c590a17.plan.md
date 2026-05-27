---
name: Maintenance Console
overview: Create a simple interactive console under `ingestion/` that becomes the primary entry point for note coverage, expansion, promotion, search rebuilds, prompt tuning, and recent run summaries while preserving existing scripts and staging semantics.
todos:
  - id: branch
    content: Create a new branch before any file edits so the console work is isolated from the current prompt run.
    status: completed
  - id: console
    content: Add the interactive maintenance console with reusable helper functions and conservative confirmations.
    status: completed
  - id: wrappers
    content: Wire menu actions to existing verify, scaffold, expand, promote, tune, log, and chunk workflows.
    status: completed
  - id: tests
    content: Add focused no-network tests for helper behavior and command construction.
    status: completed
  - id: docs
    content: Document the new primary console entrypoint without removing existing script workflows.
    status: completed
  - id: verify
    content: Run targeted tests and lint checks for edited files.
    status: completed
isProject: false
---

# Vault Maintenance Console

## Scope

Build a new console script, likely `[ingestion/maintain.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/maintain.py)`, with a simple numbered menu and conservative confirmations for API/write actions. I will create a new branch first after approval, then avoid touching the in-progress prompt tuning fixture/prompt files unless tests reveal a direct need.

## Implementation Approach

- Start by creating a new branch, for example `console-maintenance-tool`, before any code edits.
- Add the console entrypoint with the same bootstrap pattern used by existing ingestion scripts:

```python
_INGESTION = Path(__file__).resolve().parents[0]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))
import _bootstrap
_bootstrap.setup_paths(__file__)
```

- Keep the menu plain: print numbered actions, prompt with `input()`, run one action, then return to the menu until quit.
- Put the action logic in small helper functions so it is testable without driving the interactive loop.

## Menu Actions

- Status / coverage:
  - Reuse `[ingestion/lib/gaps_report.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/lib/gaps_report.py)` and `[ingestion/lib/layout.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/lib/layout.py)` to regenerate `[catalog/gaps.md](/Users/ethan/Desktop/Projects/founders/founders-notes/catalog/gaps.md)` and print the same high-signal counts as `[ingestion/pipeline/verify.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/pipeline/verify.py)` without letting `SystemExit` kill the menu.
  - Surface blocking verification failures separately from expected Phase 2 backlog.

- Next notes episode:
  - Reuse `scaffold_notes.eligible_rows()` plus `markdown_io.has_timestamp_datapoints()` from `[ingestion/notes/scaffold_notes.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/notes/scaffold_notes.py)`.
  - Print the next `{folder}.notes.md` path, matching `--next`; do not generate raw datapoints.

- Expand one episode / backlog / dry-run cost:
  - Reuse `select_expand_rows()` and `run_expand_one()` from `[ingestion/notes/expand_datapoints_llm.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/notes/expand_datapoints_llm.py)`.
  - Reuse `estimate_expand_for_row()` and `print_expand_dry_run_summary()` from `[ingestion/lib/expand_llm.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/lib/expand_llm.py)` for dry-run count/cost.
  - Preserve safeguards: require existing timestamp datapoints, honor `--missing-expanded`, support optional `limit`, `from`, and `to`, require confirmation before `--apply`, and default backlog operations to dry-run.

- Pending drafts and promotion:
  - Use `select_promote_rows()` and `promote_draft()` to list production `.expanded.draft.md` files, validate each draft, print errors/warnings, and promote by id, range, or all-ready.
  - Treat `.expanded.draft.md` as review staging and `.expanded.md` as canonical; do not index drafts.

- Rebuild search chunks:
  - Either call `[ingestion/search/build_chunks.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/search/build_chunks.py)` in-process by extracting a small `build_chunks()` helper, or call its `main()` if the existing structure remains sufficient.
  - Keep the behavior identical: overwrite `[catalog/chunks.jsonl](/Users/ethan/Desktop/Projects/founders/founders-notes/catalog/chunks.jsonl)` from transcripts, notes, promoted expanded notes, and posts.

- Prompt tuning:
  - Wrap `[ingestion/notes/expand_tune.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/notes/expand_tune.py)` conservatively.
  - Use existing `cmd_*` helpers for dry-run/report/verify where practical, and subprocess for apply expansion because `expand_tune` already isolates each episode and sets `EXPAND_RUN_ID` / `EXPAND_VARIANT`.
  - Support the current 5-episode batch via `[catalog/expand-tune-batch.json](/Users/ethan/Desktop/Projects/founders/founders-notes/catalog/expand-tune-batch.json)` without changing the batch.

- Recent run log:
  - Reuse `load_expand_run_log()`, `filter_expand_run_log()`, and `print_expand_batch_summary()` from `[ingestion/lib/expand_llm.py](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/lib/expand_llm.py)` to show the last N rows from `[catalog/expand-run.jsonl](/Users/ethan/Desktop/Projects/founders/founders-notes/catalog/expand-run.jsonl)` when present.

## Tests And Docs

- Add focused tests, likely `[tests/test_maintain.py](/Users/ethan/Desktop/Projects/founders/founders-notes/tests/test_maintain.py)`, for selection helpers, draft validation summaries, command construction, and no-network dry-run behavior.
- Update `[ingestion/README.md](/Users/ethan/Desktop/Projects/founders/founders-notes/ingestion/README.md)` and, if useful, `[docs/datapoint-workflow.md](/Users/ethan/Desktop/Projects/founders/founders-notes/docs/datapoint-workflow.md)` to point ongoing maintenance at the new console while preserving direct script commands.
- Verify with targeted pytest runs first, then run the broader relevant tests if the change touches shared helpers.