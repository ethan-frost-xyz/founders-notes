# Librarian harness reports

Live `mock_telegram_cli.py` runs write timestamped artifacts here:

| Pattern | Contents |
|---------|----------|
| `*-report.json` | Full trace: tools, timing, `response_text`, assertions |
| `*-report.md` | Formatted librarian answers (preview-friendly) |
| `*-librarian-live-suite-summary.json` | Suite rerun aggregates (agent-written) |

**Committed to git** so baselines and reruns are visible on GitHub. Ephemeral harness output (`*.log`) and `dev/logs/sessions/` / `dev/logs/sandbox/` stay local.

After a run on the Mac mini: `./dev/pull-harness-reports.sh` (laptop) then commit, or commit and push from the mini.
