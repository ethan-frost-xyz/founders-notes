---
name: Backlog plan hygiene
overview: "Shipped May 2026. Cancelled superseded archived-plan todos; restructured potential-ideas.md into Shipped / Next / Decided; aligned cross-links."
todos:
  - id: cancel-vault-bot-todos
    content: "Step 1: Cancel 4 pending todos in archive/telegram_vault_bot.plan.md; banner + historical note"
    status: completed
  - id: trim-vault-backlog
    content: "Step 2: Remove NEXT/LATER from vault_agent_backlog; Follow-ups link; trim defer list"
    status: completed
  - id: dedupe-janitor-deferred
    content: "Step 3: vault_janitor_agent § Deferred → single potential-ideas pointer"
    status: completed
  - id: restructure-potential-ideas
    content: "Step 4: Restructure potential-ideas.md (Shipped / Next clusters / Won't do)"
    status: completed
  - id: update-master-archive-readme
    content: "Step 5: telegram_rag_bot_v0 § Deferred + archive/README hygiene note"
    status: completed
  - id: cross-link-docs
    content: "Step 6: docs/retrieval.md, telegram-vault-agent.md, services/telegram README/REVIEW"
    status: completed
  - id: verify
    content: "Step 7: Link spot-check; pytest skipped (no venv in environment)"
    status: completed
  - id: archive-hygiene-plan
    content: "Step 8: Archived this plan under .cursor/plans/archive/"
    status: completed
isProject: false
---

# Backlog and plan hygiene pass

**Status: Shipped (May 2026).**

Doc-only hygiene: single mutable backlog in [`potential-ideas.md`](../../../potential-ideas.md); live overview [`docs/telegram-vault-agent.md`](../../../docs/telegram-vault-agent.md).

## Outcome

- Cancelled four stale `pending` todos in [`telegram_vault_bot.plan.md`](telegram_vault_bot.plan.md)
- Removed NEXT/LATER from [`vault_agent_backlog_8fad41c3.plan.md`](vault_agent_backlog_8fad41c3.plan.md)
- Deduped Janitor deferred → `potential-ideas.md` Janitor UX cluster
- Restructured `potential-ideas.md` into **Shipped / Next / Decided**
- Updated master plan § Deferred, archive README, and Telegram/retrieval docs for SP6-lite vs open work
