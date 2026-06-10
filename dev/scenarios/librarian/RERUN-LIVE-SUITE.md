# Librarian live suite — rerun prompt

Copy everything inside the block below into a **new Cursor chat** to replay the Jun 9 process and compare against the baseline.

---

```
Run the librarian live scenarios one at a time, alphabetically, starting from #1 (or tell me which # to start from). Do not run the next scenario until I say "proceed".

## Baseline (compare every run against this)

- Suite summary: `dev/logs/runs/2026-06-09-librarian-live-suite-summary.json`
- Per-scenario reports: paths listed in that file under `queue[].report_path`
- Baseline score: **9/11 harness pass**, **10/11 substantive** (#11 cap/DSML leak)
- Baseline config: `retrieval_model: deepseek/deepseek-v4-flash`, `librarian_model: deepseek/deepseek-v4-pro` in `~/.config/founders-telegram/runtime.json`
- Baseline total wall (primary runs): **~3843s**

### Baseline targets (canonical primary runs)

| # | Scenario | Pass | Wall | Stop | Tools (summary) | retrieval_llm | Notes |
|---|----------|------|------|------|-----------------|---------------|-------|
| 1 | basic_qa | ✓ | 114s | natural | search_vault + search_transcript | 76s | best of 4 attempts; avoid 8-tool outlier |
| 2 | episode_resolve | ✓ | 28s | natural | load_episode ×2 | 0 | |
| 3 | multi_founder_comparison | ✓ | 550s | natural | 12 tools | 463s | search_vault_many + retries |
| 4 | multi_hop | ✗ | 105s / 158s | natural | 0 / search_vault_many | 0 / 237s | run1 no tools; run2 assertion fail |
| 5 | multi_turn | ✓ | 531s | natural | 2–8 per turn | 106s + 573s | T3 follow-up heavy |
| 6 | single_founder_depth | ✓ | 574s | natural | 6× search_vault + transcript | 263s | 251s unaccounted |
| 7 | thematic_cross_episode | ✗ | 471s | natural | search_vault_many heavy | varies | 2/3 tool asserts fail |
| 8 | thematic_search | ✓ | 64s | natural | 1× search_vault | 43s | |
| 9 | thin_evidence_probe | ✓ | 402s | natural | 8 tools | 347s | honest thin evidence |
| 10 | tool_coverage | ✓ | 467s | natural | all 4 tools | varies | |
| 11 | verbatim_transcript | ✓* | 136s | **cap** | 7 tools | 65s | *quality fail — DSML leak |

### What to monitor for improvement

- **Harness pass rate** → target 11/11 (fix assertions or agent, not just reroll)
- **Wall time & retrieval_llm** → lower is better; flag regressions >25% vs baseline row
- **Tool count** → fewer tools on simple Qs (#1, #8); no zero-tool answers on thematic (#4)
- **stop_reason** → prefer `natural`; flag new `cap` hits (#11)
- **unaccounted_ms** → flag turns >60s unaccounted
- **Substantive quality** → read `response_text` / `dev/logs/runs/*-report.md`; flag hallucination, missing thin-evidence honesty, DSML leaks
- **Known flakes** → `search_vault` vs `search_vault_many` on #4/#7: note whether behavior or assertion changed

After each scenario, print a **delta vs baseline** line (pass/fail change, wall ±%, tools, stop_reason, retrieval_llm).

When the full queue finishes, write a new suite summary JSON:
`dev/logs/runs/YYYY-MM-DD-librarian-live-suite-summary.json`
with the same schema as the baseline file and a `baseline_comparison` section.

## Command per scenario

cd /Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes
ingestion/.venv/bin/python dev/mock_telegram_cli.py \
  --scenario dev/scenarios/librarian/<FILE>.yaml -v

## Queue (11)

1. basic_qa.yaml
2. episode_resolve.yaml
3. multi_founder_comparison.yaml
4. multi_hop.yaml
5. multi_turn.yaml
6. single_founder_depth.yaml
7. thematic_cross_episode.yaml
8. thematic_search.yaml
9. thin_evidence_probe.yaml
10. tool_coverage.yaml
11. verbatim_transcript.yaml

## After each run, summarize

- Pass/fail + **delta vs baseline** (harness + substantive)
- Wall time + **±% vs baseline**
- stop_reason (natural / cap)
- tool_call_counts and notable tool_calls[].arguments
- response_text quality (1–2 sentences — would you trust this answer?)
- Key timing: retrieval_llm_ms, timing_accountability.unaccounted_ms
- Report paths: `dev/logs/runs/*-report.json` and `*-report.md`

## Rules

- Do not change code unless I ask
- Do not run the full suite — **one scenario per turn**
- Preflight only if needed: `ingestion/.venv/bin/python dev/mock_telegram_cli.py --preflight`
- Reports are enriched: use `response_text`, `tool_rounds`, `trace_summary`, `stop_reason` for diagnosis
- Confirm `retrieval_model` is still `deepseek/deepseek-v4-flash` before starting (or note if different)

Start with #1.
```

---

## Quick one-liner

> Rerun librarian live suite per `dev/scenarios/librarian/RERUN-LIVE-SUITE.md` — compare to `dev/logs/runs/2026-06-09-librarian-live-suite-summary.json`, one scenario per turn, start #1.
