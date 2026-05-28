# Archived Cursor plans

Completed or superseded implementation plans moved out of [`.cursor/plans/`](../) so active work stays visible.

**Active plan (parent directory):**

- [`telegram_rag_bot_v0.plan.md`](../telegram_rag_bot_v0.plan.md) — Telegram vault agent master index (SP1–SP5 + Janitor shipped; SP6-lite in [`potential-ideas.md`](../../../potential-ideas.md) § Shipped)
- [`laptop_remote_hardening.plan.md`](../laptop_remote_hardening.plan.md) — laptop dev + SP5 webhook (code shipped; Mac mini operator steps pending)
- [`telegram_ops_sync.plan.md`](../telegram_ops_sync.plan.md) — SP5 webhook contracts

**Deferred backlog (not a plan):** [`potential-ideas.md`](../../../potential-ideas.md) — **Shipped / Next / Decided** sections.

May 2026 hygiene: `telegram_vault_bot` superseded todos cancelled; single backlog uses `potential-ideas.md` structure above.

**Recently archived (May 2026 hygiene):**

- [`backlog_plan_hygiene.plan.md`](backlog_plan_hygiene.plan.md) — cancel superseded todos; `potential-ideas.md` Shipped/Next/Decided (shipped)
- [`vault_cleanup_refactors.plan.md`](vault_cleanup_refactors.plan.md) — docs/hygiene, bootstrap, unified reindex (PRs #5+; shipped)
- [`expand_llm_split.plan.md`](expand_llm_split.plan.md) — `openrouter_client` + `expand_*` modules (shipped)
- [`fix_bare_episode_refs_4f718a49.plan.md`](fix_bare_episode_refs_4f718a49.plan.md) — Librarian episode resolution without NL regex (PR #10; shipped)
- [`telegram_mock_harness_2296d9fc.plan.md`](telegram_mock_harness_2296d9fc.plan.md) — headless Librarian/Janitor harness (shipped; guide: [`docs/telegram-mock-harness.md`](../../../docs/telegram-mock-harness.md))
- [`telegram_runtime_config_260f441f.plan.md`](telegram_runtime_config_260f441f.plan.md) — runtime.json model ops + Telegram `/sync` (shipped)
- [`harness_docs_validation_00c7577f.plan.md`](harness_docs_validation_00c7577f.plan.md) — harness docs + testing cross-links (shipped)

**Telegram SP + Janitor + index backlog:**

- `telegram_vault_sp1_tools` … `sp4` — shipped in PR #3
- [`vault_janitor_agent.plan.md`](vault_janitor_agent.plan.md) — Janitor architecture (shipped; operator guide: [`docs/janitor.md`](../../../docs/janitor.md))
- [`vault_agent_backlog_8fad41c3.plan.md`](vault_agent_backlog_8fad41c3.plan.md) — retrieval/index backlog (completed May 2026; Janitor shipped)
- [`janitor_llm-first_clean.plan.md`](janitor_llm-first_clean.plan.md) — LLM-first paste clean (shipped May 2026)
- [`telegram_vault_bot.plan.md`](telegram_vault_bot.plan.md) — superseded background sketch

**Deep archive:** [`legacy/`](legacy/) — pre-Telegram ingestion/expand plans (`.cursorignore`d)

New plans belong in `.cursor/plans/` until shipped; archive here when all todos are done or the plan is superseded. Pull deferred items into `potential-ideas.md` before archiving when possible.
