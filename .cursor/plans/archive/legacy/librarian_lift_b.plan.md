---
name: Librarian lift B
overview: "First implementation slice from the librarian output quality living doc: hygiene fixes (prompt strip, DSML sanitization) plus small retrieval tuning (`search_vault_many` expansion, excerpt cap alignment). Explicitly defers `load_episode` formatting, prompt playbook, and harness tool-assert relaxation to a second lift."
status: shipped
parent: .cursor/plans/librarian_output_quality.md
isProject: true
---

# Librarian output quality — lift B (hygiene + retrieval micro-fixes)

Child plan of [librarian_output_quality.md](librarian_output_quality.md).

## Scope

| In | Out (lift 2) |
|----|----------------|
| Strip `## Cursor Cloud` from Telegram prompt (`librarian_prompt.py`) | `format_load_episode_for_tool()` |
| `sanitize_librarian_reply()` + unit tests + verbatim `not_contains` | AGENTS.md search-stop / verbatim playbook |
| `EXPAND_VARIANTS_LIGHT = 2` for `search_vault_many` | Harness `tool_called_any` + citation regex |
| `EXCERPT_MAX_CHARS = 600` alignment | `structured_embed_text`, `librarian_temperature` |

## Decisions (grill-me)

- Prompt strip: code at `## Cursor Cloud` in `librarian_prompt.py`
- Sanitize hook: `agent.py` `_finish()` only
- Verification: CI on laptop + 3 live scenarios on Mac mini via Tailscale SSH

## Execution order

1. Living doc — before
2. Implementation
3. CI on laptop
4. Live reruns on Mac mini (#11, #3, #7)
5. Living doc — after

See full runbook in workspace plan history; implementation details in living doc red flags #1, #2, #4, #5.
