---
name: Telegram Vault SP2 — Agent loop
overview: "OpenRouter tool-calling loop + vault_agent.md. Depends on SP1 vault tools. No Telegram transport."
todos:
  - id: vault-agent-prompt
    content: services/telegram/prompts/vault_agent.md — study-notes voice, tool policy, citations
    status: pending
  - id: agent-loop
    content: services/telegram/bot/agent.py — max_steps=5, tool execution, error handling, char caps
    status: pending
  - id: tool-schemas
    content: OpenRouter-compatible tools JSON wired to vault.py (+ web stub interface)
    status: pending
  - id: mock-tests
    content: Mock OR responses — search_vault_parent before thematic answer; no web_search when allow_web=false
    status: pending
isProject: false
---

# SP2 — Agent loop + prompt

**Master (contracts only):** [telegram_rag_bot_v0.plan.md](telegram_rag_bot_v0.plan.md)  
**Requires:** [telegram_vault_sp1_tools.plan.md](telegram_vault_sp1_tools.plan.md) merged or on same branch  
**Next:** [telegram_vault_sp3_telegram.plan.md](telegram_vault_sp3_telegram.plan.md)  
**Branch:** `feature/telegram-vault-bot` · **Commit:** SP2 only

## Agent handoff

Implement **only** `VaultAgent.run_turn()` and prompt. Wire tools to SP1 `vault.py`. Do **not** add `python-telegram-bot`, handlers, or `launchd`.

**`web_search` in SP2:** register its JSON schema and add an inline stub that returns `{"error":"not configured"}` — SP3 promotes this to `bot/tools/web.py`. Do not create `web.py` in this SP.

## Goal

Multi-step OpenRouter chat with tool calling until final answer or `max_steps`.

## Deliverables

| Path | Purpose |
|------|---------|
| [`services/telegram/prompts/vault_agent.md`](../../services/telegram/prompts/vault_agent.md) | Study-notes voice, tool-use policy, citation rules |
| [`services/telegram/bot/agent.py`](../../services/telegram/bot/agent.py) | Tool loop, accumulate tool results, errors |
| [`services/telegram/bot/config.py`](../../services/telegram/bot/config.py) | Env: `OPENROUTER_API_KEY`, `TELEGRAM_CHAT_MODEL`, `VAULT_ROOT`, optional `TELEGRAM_MAX_STEPS` (default 5) |

**OpenRouter client:** Same pattern as [`expand_llm.py`](../../ingestion/lib/expand_llm.py) (OpenAI client + OpenRouter base URL). Expand does not use tools today — **tool loop is new here**.

## Turn lifecycle

1. **Input:** user text + `allow_web: bool` + last N turns from memory (caller supplies in SP3).
2. **System:** `vault_agent.md` + cheap metadata (chunks count, embeddings `built_at`, git short SHA if cheap).
3. **Loop (≤5 steps):** model `tool_calls` → execute → append `tool` role JSON → continue.
4. **Output:** final assistant string; optional tool trace for session jsonl (SP3).

## System prompt policy

1. Prefer **expanded** → **notes** → **posts** for “what I believe / noted.”
2. Call **`search_transcript`** only when quotes need transcript grounding or user asks for dialogue depth.
3. Never call **`web_search`** unless `allow_web=true`.
4. Cite `[ep-NNNN]`; quote verbatim from tool results; say when evidence is missing.

## Tool catalog (register with OpenRouter)

| Tool | When |
|------|------|
| `search_vault_parent` | Default cross-episode questions |
| `search_transcript` | Verbatim dialogue not in notes/expanded |
| `load_episode` | Named episode or narrowed to one id |
| `list_episode_ids` | Resolve “episode 22”, title |
| `web_search` | **Only** if `allow_web=true` |

## Guardrails

| Guard | Value |
|-------|--------|
| `max_steps` | 5 (env `TELEGRAM_MAX_STEPS` optional override) |
| `max_tool_result_chars` | ~20_000 per turn (sum) |
| `k` per search | 8 |
| `load_episode` cap | ~30_000 chars total |

## Failure modes

- **No hits:** model must say vault has no match; suggest `search_transcript` for dialogue — no fabrication.
- **Tool error:** return `{ "error": "..." }` in tool message.
- **OpenRouter timeout:** short user-facing error; log session id when available.

## `vault_agent.md` outline (stub before coding)

1. Role — study-notes synthesis for Founders vault  
2. Source priority — expanded > notes > post > transcript tool  
3. Tool-use rules — table above  
4. Citation format — `[ep-NNNN]`, verbatim quotes  
5. When evidence is missing  
6. Web — never unless `allow_web`  

## Tests

- **Unit:** tool wiring returns SP1 evidence shape unchanged.
- **Contract (mock OR):** thematic question → trace includes `search_vault_parent`; `allow_web=false` → never `web_search`.
- **Optional local:** one live turn with real API (not required in CI).

## Verify before commit

```bash
cd ingestion && pytest -q
python pipeline/verify.py
```

## Commit message

`feat(telegram): SP2 OpenRouter vault agent loop and prompt`
