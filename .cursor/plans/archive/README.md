# Archived Cursor plans

**Live docs (source of truth):** [`docs/telegram-vault-agent.md`](../../../docs/telegram-vault-agent.md), [`services/telegram/README.md`](../../../services/telegram/README.md), [`docs/janitor.md`](../../../docs/janitor.md), [`potential-ideas.md`](../../../potential-ideas.md).

**Deferred backlog:** [`potential-ideas.md`](../../../potential-ideas.md) — open work only.

**Historical plans:** all completed `.plan.md` files live in [`legacy/`](legacy/) (pre-Telegram ingestion/expand + shipped Telegram/Janitor plans). That folder is `.cursorignore`d so agents are not flooded with stale command lists and todos.

When you finish a new plan in [`.cursor/plans/`](../), move it to `legacy/` and update live docs — do not grow this README into a changelog.

### Key legacy plans (grep `legacy/` if you need the file)

| Topic | File |
|-------|------|
| Retrieval orchestrator (v3) | `legacy/librarian_retrieval_overhaul_7969c6d8.plan.md` |
| GitHub webhook / sync | `legacy/telegram_ops_sync.plan.md` |
| Mock harness | `legacy/telegram_mock_harness_2296d9fc.plan.md` |
| Janitor architecture | `legacy/vault_janitor_agent.plan.md` |
| v0 SP1–SP4 (PR #3) | `legacy/telegram_vault_sp1_tools.plan.md` … `sp4_ops.plan.md` |
| v4 agentic loop (post-SP4) | Shipped on `main`; see [`docs/telegram-vault-agent.md`](../../../docs/telegram-vault-agent.md) — docs may label this **SP5** |

New implementation work starts in `.cursor/plans/*.plan.md` until shipped.
