# Librarian live suite — rerun prompt

Copy everything inside the block below into a **new Cursor chat** to replay the Jun 9 process and compare against the baseline.

---

```
Run the librarian live suite per dev/scenarios/librarian/RERUN-LIVE-SUITE.md.

**First:** ask whether I want **interactive** (one scenario per turn, wait for "proceed") or **sequential** (all 15 in one session via `--suite librarian --live-only -v`).

Start from #1 unless I specify otherwise.

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

- **Harness pass rate** → target 15/15 (fix assertions or agent, not just reroll)
- **Wall time & retrieval_llm** → lower is better; flag regressions >25% vs baseline row
- **Agent path** → `observability.agent_path.path_string`; flag redundant tool chains on simple Qs (#1, #8)
- **Final synthesis TTFT** → `observability.latency.synthesis.final_ttft_ms` (not `agent_ttft_ms_mean`)
- **Retrieval spans** → `observability.latency.retrieval` (`query_expand_ms`, `hybrid_search_ms`, `llm_rerank_ms`)
- **Cap thrash** → `observability.cap_thrash.gathered.thrash_score` when `stop_reason=cap`; flag high final-round evidence dependency
- **Routing efficiency** → `observability.routing_efficiency.redundant_queries`, `tool_switches`
- **stop_reason** → prefer `natural`; flag new `cap` hits (#11)
- **unaccounted_ms** → flag turns >60s via `timing_accountability` or `observability.latency.accountability`
- **Substantive quality** → `response_text` / `*-report.md`; check `observability.synthesis_quality.dsml_leak`
- **Suite history** → auto-appended to `dev/logs/runs/librarian-suite-history.json` with `delta_vs_baseline`
- **Known flakes** → `search_vault` vs `search_vault_many` on #4/#7: note whether behavior or assertion changed
- **OOD (#12)** — `tool_rounds_used ≤ 2`, zero `[ep-NNNN]`, no hallucinated "I noted…" for absent founders
- **Negative constraints (#13)** — excluded names absent; `episode_citations_exclude` ids not in `response_text`
- **Verbatim intent (#14)** — `search_transcript` first; flag `search_vault` before transcript
- **Tool efficiency (#15)** — single `search_vault_many` with ≥2 sub-queries vs N× `search_vault` retry chains

After each scenario, print a **delta vs baseline** line (pass/fail change, wall ±%, tools, stop_reason, retrieval_llm).

Harness auto-appends each librarian suite run to `dev/logs/runs/librarian-suite-history.json`. Optional: copy a run entry to a dated snapshot (e.g. `YYYY-MM-DD-librarian-live-suite-summary.json`) for long-term baselines.

## Commands

**Sequential (all 15):**
cd /Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes
ingestion/.venv/bin/python dev/mock_telegram_cli.py \
  --suite librarian --live-only -v

**Interactive (one at a time) — always tag with `--run-note`:**
cd /Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes
ingestion/.venv/bin/python dev/mock_telegram_cli.py \
  --scenario dev/scenarios/librarian/<FILE>.yaml -v \
  --run-note "librarian-live/YYYY-MM-DD #N <stem> <branch>@<sha>"

## Queue (15)

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
12. ood_decline.yaml — OOD halt
13. negative_constraints.yaml — exclusion compliance
14. verbatim_intent.yaml — transcript-first routing
15. tool_efficiency.yaml — `search_vault_many` decomposition

### Baseline placeholders (#12–15)

Re-baseline after first green run on Mac mini:

| # | Scenario | Pass | Wall | Stop | Tools | Notes |
|---|----------|------|------|------|-------|-------|
| 12 | ood_decline | TBD | TBD | TBD | TBD | ≤2 rounds, no citations |
| 13 | negative_constraints | TBD | TBD | TBD | TBD | layered exclusion |
| 14 | verbatim_intent | TBD | TBD | TBD | TBD | transcript first |
| 15 | tool_efficiency | TBD | TBD | TBD | TBD | search_vault_many ≥2 queries |

Interactive run-note examples:

```text
librarian-live/YYYY-MM-DD #12 ood_decline main@<sha>
librarian-live/YYYY-MM-DD #13 negative_constraints main@<sha>
librarian-live/YYYY-MM-DD #14 verbatim_intent main@<sha>
librarian-live/YYYY-MM-DD #15 tool_efficiency main@<sha>
```

## After each run, summarize

- Pass/fail + **delta vs baseline** (harness + substantive; also `librarian-suite-history.json` → `delta_vs_baseline`)
- Wall time + **±% vs baseline**
- `observability.agent_path.path_string_compact` and `tool_rounds_used`
- `observability.latency.synthesis.final_ttft_ms` and retrieval spans (`query_expand_ms`, `hybrid_search_ms`, `llm_rerank_ms`)
- `observability.cap_thrash.gathered.thrash_score` when `stop_reason=cap`
- `observability.routing_efficiency.redundant_queries`
- stop_reason (natural / cap)
- response_text quality (1–2 sentences); `observability.synthesis_quality.dsml_leak`
- Legacy timing: retrieval_llm_ms, timing_accountability.unaccounted_ms
- Report paths: `dev/logs/runs/*-report.json`, `*-report.md`, suite history

## Rules

- Do not change code unless I ask
- **Interactive:** one scenario per turn — wait for "proceed"
- **Sequential:** full suite in one session is OK
- Preflight only if needed: `ingestion/.venv/bin/python dev/mock_telegram_cli.py --preflight`
- Reports are schema v2: use `observability`, `response_text`, `tool_rounds`, `trace_summary`, `stop_reason` for diagnosis
- Confirm `retrieval_model` is still `deepseek/deepseek-v4-flash` before starting (or note if different)

Start with #1.
```

---

## Quick one-liner

> Rerun librarian live suite per `dev/scenarios/librarian/RERUN-LIVE-SUITE.md` — compare to `dev/logs/runs/2026-06-09-librarian-live-suite-summary.json`. Ask interactive vs sequential, start #1.
