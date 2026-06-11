---
name: librarian-live-suite-loop
description: Run librarian live harness scenarios against a baseline summary, compare timing and quality, and write a suite rerun JSON. Use when rerunning the librarian live suite, live mock_telegram_cli scenarios, harness regression loops, or the user says proceed through the scenario queue.
---

# Librarian live suite testing loop

Regression loop for the 11 live librarian scenarios. **Ask run mode first** (see below), then preflight and run.

Canonical prompt and baseline table: [RERUN-LIVE-SUITE.md](../../../dev/scenarios/librarian/RERUN-LIVE-SUITE.md)

## Choose run mode (first action)

Use **AskQuestion** before the first scenario:

| Mode | Label | Behavior |
|------|-------|----------|
| **Interactive** (default) | One-by-one | Run **one** scenario per agent turn; wait for user **"proceed"** before the next |
| **Sequential** | Full suite | Run all 11 in queue order in **one session** without pausing; post per-scenario summaries then suite JSON |

Record the chosen mode in your first reply. If the user already specified a mode in their message, skip the question.

### Interactive mode

- One scenario per turn — **do not** run the next until the user says **proceed** (or gives a queue #).
- User may say **start from #N** to skip ahead.

### Sequential mode

- Run the full queue in one session (long `block_until_ms` — expect **~60–90 min** total).
- Prefer the canonical suite command (alphabetical order matches the queue table):

```bash
ingestion/.venv/bin/python dev/mock_telegram_cli.py \
  --suite librarian --live-only -v
```

- Or run each YAML in queue order if you need per-scenario report paths mid-run.
- After all 11 finish: post condensed per-scenario summaries + write suite summary JSON.

## Before the first scenario

All commands below run from the **repo root** (same pattern as [`docs/operations.md`](../../../docs/operations.md)).

1. Read `dev/scenarios/librarian/RERUN-LIVE-SUITE.md` and the baseline JSON it references.
2. Check `~/.config/founders-telegram/runtime.json` — note `retrieval_model` and `librarian_model` (baseline: `deepseek/deepseek-v4-flash` / `deepseek/deepseek-v4-pro`).
3. Preflight if keys/vault are uncertain:

```bash
ingestion/.venv/bin/python dev/mock_telegram_cli.py --preflight
```

4. Skim git log since baseline for harness/scenario/agent changes that affect what to watch.
5. **Note:** Baseline `unaccounted_ms` values (Jun 9) used the old sum-based formula. Post-fix runs use wall-based accountability — compare **magnitude and flags**, not exact ms parity with baseline.

## Run one scenario (interactive) or full suite (sequential)

**Single scenario:**

```bash
ingestion/.venv/bin/python dev/mock_telegram_cli.py \
  --scenario dev/scenarios/librarian/<FILE>.yaml -v
```

Queue order:

| # | File |
|---|------|
| 1 | `basic_qa.yaml` |
| 2 | `episode_resolve.yaml` |
| 3 | `multi_founder_comparison.yaml` |
| 4 | `multi_hop.yaml` |
| 5 | `multi_turn.yaml` |
| 6 | `single_founder_depth.yaml` |
| 7 | `thematic_cross_episode.yaml` |
| 8 | `thematic_search.yaml` |
| 9 | `thin_evidence_probe.yaml` |
| 10 | `tool_coverage.yaml` |
| 11 | `verbatim_transcript.yaml` |

Use a long `block_until_ms` for slow scenarios (#3, #5, #6, #7, #9, #10).

## After each scenario — required summary

Read `dev/logs/runs/*-report.json` and paired `*-report.md`. Post:

```markdown
## #N `<file>` — PASS|FAIL

**Delta vs baseline:** harness … | substantive … | wall **Xs (±%)** | stop … | tools … | retrieval_llm … | unaccounted …

**Timing:** search_wall … | tool_local … | thread_wait … | parallelism_excess … (if notable)

**Quality:** 1–2 sentences — would you trust this answer?

**Reports:** `dev/logs/runs/…-report.json`, `…-report.md`
```

### Timing accountability (post-fix)

Read `timing_accountability` and `timing.accounted_breakdown` on each live turn:

| Field | Meaning | Monitor |
|-------|---------|---------|
| `unaccounted_ms` | `wall_ms − (search_wall_ms + tool_local_ms + openrouter_total_ms)` | Flag turns **>60s** |
| `search_wall_ms` | Wall-based search time; consecutive `search_vault_many` rows use **max** `wall_ms` per batch | Primary search bucket for accountability |
| `tool_local_ms` | `load_episode` / `list_episode_ids` disk + catalog | Expect nonzero on #2, #3, #10 |
| `thread_wait_ms` | Parent wall on `search_vault_many` fan-out | Diagnostic; should ≈ max sub-query `wall_ms` |
| `expand_retry_ms` | Expand/rerank retry backoff + failed attempts | Diagnostic; surfaced in reports |
| `parallelism_excess_ms` | `(vault + retrieval effort) − search_wall_ms` | High on concurrent `search_vault_many` is **expected**, not a regression |
| `retrieval_llm_ms` / `vault_search_local_ms` | **Effort** totals (sum across parallel sub-queries) | Still flag **>25%** vs baseline for retrieval cost; can exceed wall on many-fan-out turns |

Per-search rows in `timing.searches[]` include `wall_ms` when instrumentation is active.

### Monitor (flag regressions)

| Signal | Action |
|--------|--------|
| Harness pass rate | Target 11/11 — fix assertions or agent, not reroll alone |
| Wall / `retrieval_llm_ms` | Flag if **>25%** vs baseline row |
| `stop_reason: cap` | Flag new caps; check DSML in `response_text` |
| Zero tools on thematic Q | Substantive failure even if harness passes |
| `unaccounted_ms` | Flag turns **>60s** (formula is now wall-based; old baseline unaccounted not 1:1 comparable) |
| `search_vault` vs `search_vault_many` | Harness flake if scenario pins one tool — see diagnosis below |
| Thin-evidence / verbatim | Read answer for honesty and DSML leaks |

## Harness fail ≠ bad answer

`expect_live` checks tool names and response substrings, not answer quality.

- **`tool_called` / `tools_called`** — subset check: listed tools must appear at least once.
- **`tool_called_any`** — at least one listed tool must appear.

If the agent used `search_vault_many` but the scenario requires `search_vault`, harness fails while substantive passes. Fix: align scenario with [AGENTS.md](../../../AGENTS.md) (`tool_called_any: [search_vault, search_vault_many]`). Do **not** change librarian mechanics to satisfy a stale assertion unless the user asks.

## When the queue finishes

Write `dev/logs/runs/YYYY-MM-DD-librarian-live-suite-rerun-summary.json`:

- Same schema as baseline `dev/logs/runs/2026-06-09-librarian-live-suite-summary.json`
- Add `baseline_comparison` (harness/substantive deltas, wall total, improved/regressed list)
- Per-scenario `report_path`, timing, tool counts, notes
- Include `run_mode`: `interactive` or `sequential`

`dev/logs/` is gitignored — summaries stay local unless the user commits docs/scenarios only.

## Rules

- **Do not change code** unless the user asks (scenario YAML fixes are OK when diagnosing assertion drift).
- **Interactive only:** one scenario per turn — wait for **proceed**.
- **Sequential:** full suite in one session is allowed; still distinguish harness vs substantive per scenario.
- Distinguish **harness pass** vs **substantive pass** (DSML leaks, hallucination, missing thin-evidence honesty).
- Use enriched report fields: `response_text`, `tool_rounds`, `trace_summary`, `stop_reason`, `timing_accountability`, `timing.searches[]`.

## References

- [RERUN-LIVE-SUITE.md](../../../dev/scenarios/librarian/RERUN-LIVE-SUITE.md) — copy-paste prompt + baseline table
- [telegram-mock-harness.md](../../../docs/telegram-mock-harness.md) — harness modes, timing buckets, report schema
- [dev/scenarios/README.md](../../../dev/scenarios/README.md) — per-scenario tool expectations
