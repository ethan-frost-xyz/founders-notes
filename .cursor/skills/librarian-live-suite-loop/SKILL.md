---
name: librarian-live-suite-loop
description: Run librarian live harness scenarios against a baseline summary, compare timing and quality, and write a suite rerun JSON. Use when rerunning the librarian live suite, live mock_telegram_cli scenarios, harness regression loops, or the user says proceed through the scenario queue.
---

# Librarian live suite testing loop

Regression loop for the 15 live librarian scenarios. **Prefer interactive (one-by-one)** — full `--suite` defers all output until the end and can hang invisibly on OpenRouter.

Canonical prompt and baseline table: [RERUN-LIVE-SUITE.md](../../../dev/scenarios/librarian/RERUN-LIVE-SUITE.md)

## Choose run mode (first action)

Use **AskQuestion** before the first scenario unless the user already chose:

| Mode | Label | Behavior |
|------|-------|----------|
| **Interactive** (default) | One-by-one | One scenario per turn; wait for **proceed**; **always pass `--run-note`** |
| **Sequential** | Full suite | All 15 in one session — only when user explicitly wants it; use queue-order loop with `--run-note` per file instead of bare `--suite` when possible |

Record the chosen mode in your first reply.

### Interactive mode (preferred)

- One scenario per turn — **do not** run the next until the user says **proceed** (or gives a queue #).
- User may say **start from #N** to skip ahead.
- **Every run must include `--run-note`** (see [Run tagging](#run-tagging)).

### Sequential mode

- Expect **~75–100 min** total (15 scenarios); use long `block_until_ms`.
- **Avoid** bare `--suite librarian --live-only` over SSH — no per-scenario feedback and no report until all finish.
- **Preferred:** loop queue YAMLs with `--scenario` + `--run-note` each (reports land immediately).
- If user insists on `--suite`, use `PYTHONUNBUFFERED=1` and `-v` (prints per-scenario summary mid-run when `scenario_count > 1`).
- After all 15: post condensed summaries + write `YYYY-MM-DD-librarian-live-suite-rerun-summary.json`.

## Before the first scenario

From **repo root** (see [`docs/operations.md`](../../../docs/operations.md)).

1. Read `dev/scenarios/librarian/RERUN-LIVE-SUITE.md` and baseline `dev/logs/runs/2026-06-09-librarian-live-suite-summary.json` (**#1–11 only**; #12–15 have no baseline row until re-baselined).
2. Check `~/.config/founders-telegram/runtime.json` — baseline: `deepseek/deepseek-v4-flash` / `deepseek/deepseek-v4-pro`.
3. Preflight if uncertain: `ingestion/.venv/bin/python dev/mock_telegram_cli.py --preflight`
4. Skim `git log` since baseline for harness/agent/scenario changes.
5. Set **session date** (`YYYY-MM-DD`) and optional **session prefix** for all run notes in this chat.
6. Pin comparison baseline in `dev/logs/runs/librarian-suite-history.json` → `baseline_run_id` when comparing to a specific prior run (default: first row).

**Note:** Jun 9 baseline `unaccounted_ms` used sum-based formula; post-fix runs are wall-based — compare magnitude/flags, not exact ms.

## Run tagging

Every librarian harness run stamps **`run_context`** on `*-report.json` and appends **`librarian-suite-history.json`** with:

- Auto: `git_sha`, `git_branch`, `git_dirty`, `librarian_model`, `retrieval_model`, `scenario_yaml` (single-scenario)
- Manual: **`run_note`** via `--run-note` (or `HARNESS_RUN_NOTE` env for a session default)

### Run note format (required in interactive loop)

Before each scenario, resolve branch + short sha (`git rev-parse --abbrev-ref HEAD`, `git rev-parse --short HEAD`), then:

```text
librarian-live/{session_date} #{N} {yaml_stem} {branch}@{sha}
```

Example:

```bash
ingestion/.venv/bin/python dev/mock_telegram_cli.py \
  --scenario dev/scenarios/librarian/basic_qa.yaml -v \
  --run-note "librarian-live/2026-06-11 #1 basic_qa main@b53a43b"
```

Optional suffix for intent: `… post-PR-36` or `… retry after cap`.

### After each run

- Confirm stdout shows `Run note: …`
- History row has matching `run_note` + `scenario_yaml`
- Pull from mini: `./dev/pull-harness-reports.sh`

## Queue (15)

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
| 12 | `ood_decline.yaml` |
| 13 | `negative_constraints.yaml` |
| 14 | `verbatim_intent.yaml` |
| 15 | `tool_efficiency.yaml` |

Use a long `block_until_ms` for #3, #5, #6, #7, #9, #10, #12–#15.

**Tool-routing FAIL hints (#3, #12–15):** `search_vault_many_queries_min` (#3, #15); agentic stress (#12–15): `tool_rounds_max`, `no_episode_citations`, `response_not_contains_all`, `episode_citations_exclude`, `tool_called_first` — see [telegram-mock-harness.md](../../../docs/telegram-mock-harness.md#agentic-stress-scenarios).

## After each scenario — required summary

Read latest `dev/logs/runs/*-report.json` (check `run_context.run_note`) and paired `*-report.md`. Post:

```markdown
## #N `<file>` — PASS|FAIL

**Run note:** `…` | **git:** `branch@sha` | **models:** retrieval / librarian

**Delta vs baseline:** harness … | substantive … | wall **Xs (±%)** | stop … | tools … | `final_ttft_ms` … | cap_hits …

**Observability:** `path_string_compact` | retrieval spans (expand/hybrid/rerank) | `thrash_score` if cap | `dsml_leak`

**Quality:** 1–2 sentences — would you trust this answer?

**Reports:** `dev/logs/runs/…-report.json`, `…-report.md`
```

### Key metrics (schema v2)

| Source | Use for |
|--------|---------|
| `observability.latency.synthesis.final_ttft_ms` | Final answer TTFT (not `agent_ttft_ms_mean`) |
| `observability.latency.retrieval.*` | `query_expand_ms`, `hybrid_search_ms`, `llm_rerank_ms` |
| `observability.agent_path.path_string_compact` | Tool chain |
| `observability.cap_thrash.gathered.thrash_score` | Cap thrash when `stop_reason=cap` |
| `observability.synthesis_quality.dsml_leak` | DSML in answer |
| `timing_accountability.unaccounted_ms` | Flag **>60s** |
| `librarian-suite-history.json` → `delta_vs_baseline` | vs pinned `baseline_run_id` |

Legacy: `retrieval_llm_ms`, `timing.searches[]` with `wall_ms`.

### Monitor (flag regressions)

| Signal | Action |
|--------|--------|
| Harness pass rate | Target 15/15 — fix assertions or agent, not reroll alone |
| Wall / retrieval spans | Flag **>25%** vs baseline row |
| `stop_reason: cap` | Flag new caps; check DSML |
| Zero tools on thematic Q | Substantive fail even if harness passes |
| `unaccounted_ms` | Flag **>60s** |
| `search_vault` vs `search_vault_many` | Assertion drift — see below |

## Harness fail ≠ bad answer

`expect_live` checks tool names and substrings, not quality. Harness can fail on tool choice (`search_vault` vs `search_vault_many`, `search_transcript` ordering) while the answer is fine — fix scenario YAML per [AGENTS.md](../../../AGENTS.md); do not change librarian mechanics unless asked.

## When the queue finishes

Write `dev/logs/runs/YYYY-MM-DD-librarian-live-suite-rerun-summary.json`:

- Schema like `dev/logs/runs/2026-06-09-librarian-live-suite-summary.json`
- `baseline_comparison`, per-scenario `report_path`, `run_note` from each report's `run_context`
- `run_mode`: `interactive` or `sequential`
- `config` block with models from last `run_context`

Git-tracked artifacts: `*-report.json`, `*-report.md`, suite summary JSONs. Mini → `./dev/pull-harness-reports.sh` → commit on laptop.

## Rules

- **Interactive:** one scenario per turn — wait for **proceed**; **always `--run-note`**.
- **Do not change code** unless asked (scenario YAML fixes OK for assertion drift).
- Distinguish harness pass vs substantive pass.
- Prefer `observability` + `run_context` over legacy fields alone.

## References

- [RERUN-LIVE-SUITE.md](../../../dev/scenarios/librarian/RERUN-LIVE-SUITE.md)
- [telegram-mock-harness.md](../../../docs/telegram-mock-harness.md) — report schema, `run_context`, suite history
- [dev/scenarios/README.md](../../../dev/scenarios/README.md)
