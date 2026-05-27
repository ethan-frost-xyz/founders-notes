---
name: Deslop expand fixtures
overview: "Remove low-value redundancy from the tracked expand-fixtures commit: simplify `cmd_verify`, trim overlapping tests and docs, fix stale CLI help. No behavior changes beyond clearer errors and accurate `--force` help."
todos:
  - id: simplify-cmd-verify
    content: Remove redundant staging/path logic in cmd_verify; fix p_init --force help
    status: completed
  - id: trim-tests
    content: Remove dead constants, trivial/overlapping baseline tests; keep verify CLI smoke test
    status: completed
  - id: trim-readme
    content: Deduplicate expand-runs README quick start vs regenerate sections
    status: completed
  - id: verify-pytest
    content: Run pytest + expand_tune verify; commit deslop changes
    status: completed
isProject: false
---

# Deslop: tracked expand fixtures (1cbc793)

Scope: code/docs/tests introduced in [`1cbc793`](https://github.com/ethan-frost-xyz/founders-notes/commit/1cbc793) — not the 20 LLM draft markdown files (content, not slop).

## Findings

### [`ingestion/notes/expand_tune.py`](ingestion/notes/expand_tune.py) — `cmd_verify`

- **`staging` variable** is assigned but only used to rebuild a path that `draft_report_row` already resolved internally — duplicate `staging_draft_file_path` call.
- **Fix:** Drop `staging`; on missing draft print `[error] {ep_id} variant {variant}: no draft` (same pattern as `draft_report_row`'s internal message). Keeps behavior, removes 7 lines.

### [`ingestion/notes/expand_tune.py`](ingestion/notes/expand_tune.py) — argparse

- **`p_init --force` help** still says "Re-init and re-seed candidate prompt" but `init` no longer re-seeds B on `--force` (regression from implementation). Update to: `Re-init run directory (overwrites manifest)`.
- **Repeated `--run-id` help** (`Run folder name (default: baseline)`) on 5 parsers — optional micro-cleanup: one module constant `RUN_ID_HELP = f"Run folder name (default: {DEFAULT_RUN_ID})"` used in `add_argument` calls. Matches local style only if similar constants exist elsewhere; otherwise leave as-is (not worth churn).

### [`tests/test_expand_baseline_fixtures.py`](tests/test_expand_baseline_fixtures.py)

| Item | Issue |
|------|--------|
| `BASELINE_DIR` | Defined, never used — delete |
| `test_baseline_manifest_exists` | Subset of `test_baseline_manifest_records_variants` — delete |
| `test_default_run_id` in [`tests/test_expand_tune.py`](tests/test_expand_tune.py) | Asserts constant equals literal `"baseline"` — no behavior coverage — delete |
| `test_baseline_verify_cli` vs `test_baseline_has_twenty_drafts` + `test_baseline_drafts_validate` | Heavy overlap; verify subprocess already exercises existence + validation + hash checks |

**Consolidate tests:** Keep one in-process test (`test_baseline_drafts_validate` covers existence implicitly via `read_markdown_body` / path resolution — or keep a slim existence check inside one loop). Drop `test_baseline_has_twenty_drafts` as separate test; merge existence into `test_baseline_drafts_validate` with clear assert on missing file. Keep **one** subprocess smoke test (`test_baseline_verify_cli`) and drop `test_baseline_report_cli` (report is print-only; verify is the guardrail). Net: ~3 tests instead of 6.

### [`ingestion/fixtures/expand-runs/README.md`](ingestion/fixtures/expand-runs/README.md)

- **Quick start** and **Regenerate baseline** duplicate the same command sequence (init → expand A/B → verify).
- **Fix:** Single "Commands" section: first-time flow with `--force` noted in one line; tuning loop table stays; remove standalone "Regenerate baseline" block.

### Docs elsewhere

- [`docs/datapoint-workflow.md`](docs/datapoint-workflow.md) / [`ingestion/README.md`](ingestion/README.md): already minimal; no slop beyond what README fix covers.

### Out of scope

- Fixture markdown bodies (LLM output)
- `.cursor/plans/tracked_expand_fixtures_9450f23b.plan.md`
- Refactoring `cmd_verify` to call shared logic with `cmd_report` (larger than deslop)

## Verification

```bash
cd ingestion && .venv/bin/python -m pytest tests/test_expand_baseline_fixtures.py tests/test_expand_tune.py -q
.venv/bin/python notes/expand_tune.py verify
```

## Commit

Single focused commit on `main`: `Deslop expand-tune baseline fixtures and verify command`
