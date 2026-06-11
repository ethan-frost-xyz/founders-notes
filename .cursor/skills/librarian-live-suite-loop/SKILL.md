---
name: librarian-live-suite-loop
description: Run librarian live harness scenarios one at a time, compare each run to a baseline summary, and write a suite rerun JSON. Use when rerunning the librarian live suite, live mock_telegram_cli scenarios, harness regression loops, or the user says proceed through the scenario queue.
---

# Librarian live suite testing loop

Interactive regression loop for the 11 live librarian scenarios. **One scenario per user turn** — wait for "proceed" before the next.

Canonical prompt and baseline table: [RERUN-LIVE-SUITE.md](../../../dev/scenarios/librarian/RERUN-LIVE-SUITE.md)

## Before the first scenario

1. Read `dev/scenarios/librarian/RERUN-LIVE-SUITE.md` and the baseline JSON it references.
2. Check `~/.config/founders-telegram/runtime.json` — note `retrieval_model` and `librarian_model` (baseline: `deepseek/deepseek-v4-flash` / `deepseek/deepseek-v4-pro`).
3. Preflight if keys/vault are uncertain:

```bash
cd /Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes
ingestion/.venv/bin/python dev/mock_telegram_cli.py --preflight
```

4. Skim git log since baseline for harness/scenario/agent changes that affect what to watch.

## Run one scenario

```bash
cd /Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes
ingestion/.venv/bin/python dev/mock_telegram_cli.py \
  --scenario dev/scenarios/librarian/<FILE>.yaml -v
```

Queue order (do not batch):

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

**Quality:** 1–2 sentences — would you trust this answer?

**Reports:** `dev/logs/runs/…-report.json`, `…-report.md`
```

### Monitor (flag regressions)

| Signal | Action |
|--------|--------|
| Harness pass rate | Target 11/11 — fix assertions or agent, not reroll alone |
| Wall / `retrieval_llm_ms` | Flag if **>25%** vs baseline row |
| `stop_reason: cap` | Flag new caps; check DSML in `response_text` |
| Zero tools on thematic Q | Substantive failure even if harness passes |
| `unaccounted_ms` | Flag turns **>60s** |
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

`dev/logs/` is gitignored — summaries stay local unless the user commits docs/scenarios only.

## Rules

- **Do not change code** unless the user asks (scenario YAML fixes are OK when diagnosing assertion drift).
- **Do not run the full suite** in one turn.
- Distinguish **harness pass** vs **substantive pass** (DSML leaks, hallucination, missing thin-evidence honesty).
- Use enriched report fields: `response_text`, `tool_rounds`, `trace_summary`, `stop_reason`, `timing_accountability`.

## References

- [RERUN-LIVE-SUITE.md](../../../dev/scenarios/librarian/RERUN-LIVE-SUITE.md) — copy-paste prompt + baseline table
- [telegram-mock-harness.md](../../../docs/telegram-mock-harness.md) — harness modes and report schema
- [dev/scenarios/README.md](../../../dev/scenarios/README.md) — per-scenario tool expectations
