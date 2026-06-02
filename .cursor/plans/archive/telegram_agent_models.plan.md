# Telegram agent/models cleanup (shipped Jun 2026)

## Scope shipped

- Removed misleading `max_steps` / `TELEGRAM_MAX_STEPS` / `/setsteps` / `/resetsteps` and Settings **max_steps** UI.
- `AgentConfig` no longer carries `max_steps`; `apply_runtime_overrides` only sets librarian model. (`retrieval_model` for orchestrator expand/rerank is separate — unchanged.)
- Librarian `run_turn` keeps fixed **1–2 synthesis passes** (`synthesis_passes` local variable); retrieval is deterministic Python via orchestrator.

## Deferred

- OpenRouter `reasoning.effort` for Librarian synthesis — not universal across models; see [`potential-ideas.md`](../../potential-ideas.md) cluster `telegram_agent_models_reasoning.plan.md`.

## Verification

```bash
pytest tests/test_runtime_settings.py tests/test_vault_agent.py tests/test_telegram_bot.py -q
```
