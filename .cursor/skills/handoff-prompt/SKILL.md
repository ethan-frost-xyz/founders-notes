---
name: handoff-prompt
description: >-
  Produces a copy-paste handoff prompt for external coding agents (Gemini CLI,
  Grok build, or similar). Gathers task, constraints, relevant file paths,
  acceptance criteria, and verify commands from the current conversation and
  codebase. Use when the user asks to hand off a task, export a prompt for
  another agent, mentions Gemini CLI or Grok build, or wants a portable
  copy-paste prompt block.
disable-model-invocation: false
---

# Handoff Prompt

Generate a **portable prompt** the user can paste into Gemini CLI, Grok build, or any external coding agent. Do not run the handoff yourself unless the user also asks you to implement the task.

## Output shape

1. **Short summary** (2–4 sentences): what the handoff covers, what's included, any gaps you had to leave as `[TBD]`.
2. **One fenced code block** containing the full handoff prompt — the only part meant to be copied.

Use a plain `text` fence (not `markdown`) so pasting into terminals and CLIs stays clean.

## Before writing

Gather full context. Do not guess file paths or commands.

1. **Task** — Restate the goal as a single imperative sentence. If the user's ask is vague, ask one focused clarifying question; do not interview at length.
2. **Codebase** — Read or search for files the external agent must touch. List paths relative to repo root with a one-line note per file (role, not a summary of contents).
3. **Constraints** — Stack, style rules, scope limits, things explicitly out of scope.
4. **Acceptance criteria** — Observable done conditions (tests pass, behavior changes, files exist).
5. **Verify commands** — Exact commands from this repo (pytest, verify.py, build, lint). Read `docs/testing.md`, `AGENTS.md`, or CI config if unsure.
6. **Gaps** — Use `[TBD: …]` for anything unknown. Mention gaps in the summary.

## Prompt template

Fill every section. Delete lines that truly do not apply; do not leave empty section headers.

```text
You are implementing a focused change in an existing codebase. Read the listed files before editing. Match existing conventions. Minimize scope — no drive-by refactors.

## Task
<one clear imperative sentence>

## Background
<2–4 sentences: why this change, relevant conversation context, what already exists>

## Constraints
- <language, framework, versions if known>
- <style / scope limits from user or repo>
- <explicit out-of-scope items>

## Files to read first
- `path/to/file` — <why this file matters>
- `path/to/other` — <why>

## Implementation notes
- <specific approach, patterns to follow, functions to extend>
- <edge cases or pitfalls from codebase exploration>

## Acceptance criteria
- [ ] <observable outcome 1>
- [ ] <observable outcome 2>

## Verify
Run these after implementing:
```
<exact command 1>
<exact command 2>
```

## Do not
- <anti-patterns, files to avoid, things user said not to do>
```

## Quality bar

- **Self-contained** — The external agent should not need this chat history.
- **Paths over prose** — Prefer concrete file paths to long explanations.
- **Commands are real** — Only include commands that exist in the repo; never invent scripts.
- **Scope is tight** — One task per handoff. If the user bundled multiple tasks, split into separate handoffs or ask which to export.
- **No Cursor-isms** — Omit references to Cursor, MCP, skills, or internal tools unless the task itself is about them.

## Examples

**User:** "Hand this off to Gemini — add a retry wrapper around the search API call."

**Summary:** Handoff covers a single retry wrapper for the vault search client, with paths to the search module and existing tests, plus pytest commands from this repo.

**Code block:** (filled template with real paths and `ingestion/.venv/bin/pytest tests -q` or whatever applies)

**User:** "Give me a grok build prompt for the auth refactor we discussed."

**Summary:** Exports the auth refactor from this thread. Flagged `[TBD: session storage choice]` because we never decided Redis vs JWT-only.

**Code block:** (filled template with `[TBD]` where needed)
