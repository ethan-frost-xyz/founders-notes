---
name: Librarian lift 2
overview: "Second slice from librarian_output_quality.md — harness quality assertions, AGENTS.md search-stop playbook, and unified load_episode evidence formatting. Laptop-first (CI); live suite validation deferred to Mac mini."
status: not started
parent: .cursor/plans/librarian_output_quality.md
predecessor: .cursor/plans/librarian_lift_b.plan.md
isProject: true
---

# Librarian output quality — lift 2

Child plan of [librarian_output_quality.md](librarian_output_quality.md). Follows [librarian_lift_b.plan.md](librarian_lift_b.plan.md) (shipped 2026-06-10).

**For the planning agent:** Read the parent living doc in full, then use this file as the scope boundary. Prefer `/grill-me` on slice order (harness-first vs evidence-first) before implementing.

---

## Goals

1. **Measure answer quality, not tool choice** — relax flaky harness asserts; add citation guards.
2. **Reduce tool-loop / zero-tool failure modes** — short `AGENTS.md` playbook (soft; no mandatory pre-retrieval).
3. **Unify evidence shape for synthesis** — `load_episode` formatted like search evidence.

**Success bar (laptop):** CI green (`pytest` + `verify.py`).

**Success bar (Mac mini, when available):** Re-run live suite vs [`RERUN-LIVE-SUITE.md`](../../dev/scenarios/librarian/RERUN-LIVE-SUITE.md); target harness pass ≥10/11 with substantive quality on #4, #7, #11.

---

## Scope

### In scope (lift 2)

| ID | Item | Red flag / easy win | Effort |
|----|------|---------------------|--------|
| A | Harness `tool_called_any` + citation regex | #8, #7, testing gap 1 & 3 | Small |
| B | Harness `not_contains_all` (or list) for leak patterns | testing gap 2 (complete partial from lift B) | Small |
| C | `AGENTS.md` search-stop + verbatim + comparison playbook | #6, #7, easy win #6 | Small |
| D | Enrich `SEARCH_BUDGET_NUDGE` with evidence summary | #7 | Small |
| E | `evidence_format.py` + `format_load_episode_for_tool()` | #3, easy win #3 | Medium |
| F | Optional stretch: `structured_embed_text` in vault evidence | #9 medium table, easy win #8 | Small |

### Out of scope (lift 3+)

- `librarian_temperature` runtime key (easy win #9) — tune after behavior stable
- Stream-preview sanitization (P3 #12)
- Multi-turn evidence in session history (P3 #14)
- Mandatory pre-retrieval, JSON-schema replies, full markdown renderer
- Split expand/rerank models (`potential-ideas.md`)

---

## Recommended implementation order (laptop)

1. **Living doc — before** (mark lift 2 in progress)
2. **Slice A + B** — harness assertions (`scenario_runner.py` + YAML)
3. **Slice C + D** — `AGENTS.md` + `agent.py` cap nudge
4. **Slice E** — `evidence_format.py`, wire `load_episode` in `_tool_result_content()`
5. **Slice F** (optional) — `structured_embed_text` in orchestrator formatter
6. **CI** — pytest + verify.py
7. **Living doc — after**
8. **Mac mini** (when reachable) — live suite or targeted #4, #7, #11

---

## Slice A — Harness quality assertions

### Problem

Baseline failures #4 and #7 often reflect **tool choice**, not bad answers. `scenario_runner` only supports one `not_contains` per turn (duplicate YAML keys overwrite — see `episode_resolve.yaml`).

### Changes

**[`dev/harness/scenario_runner.py`](../../dev/harness/scenario_runner.py):**

- Add `response_matches_regex` (or `response_contains_episode_citation`) — live only; pattern `\[ep-\d{4}\]`
- Add `not_contains_all: [list]` for multiple leak needles
- Keep echo-mode behavior unchanged

**Scenario YAML updates:**

| File | Current | Proposed |
|------|---------|----------|
| [`multi_hop.yaml`](../../dev/scenarios/librarian/multi_hop.yaml) | `tools_called: [search_vault_many]` | `tool_called_any: [search_vault, search_vault_many]` + citation regex |
| [`multi_founder_comparison.yaml`](../../dev/scenarios/librarian/multi_founder_comparison.yaml) | `tool_called: search_vault_many` | `tool_called_any` + citation regex |
| [`thematic_cross_episode.yaml`](../../dev/scenarios/librarian/thematic_cross_episode.yaml) | tool asserts per turn | Keep `tool_called_any`; add citation regex on turns 1–3 |
| Live librarian scenarios (stretch) | verbatim only has DSML guard | Add `not_contains_all` for leak patterns on thematic scenarios |

**Tests:** extend [`tests/test_harness_scenarios.py`](../../tests/test_harness_scenarios.py) or add focused unit tests for new expect keys (echo stubs).

---

## Slice B — Leak guards (complete lift B partial)

- Unit tests already in [`tests/test_reply_sanitize.py`](../../tests/test_reply_sanitize.py)
- Extend harness beyond verbatim `not_contains: DSML` once `not_contains_all` exists
- Patterns: `DSML`, `redacted_reasoning`, `` (if stable in reports)

---

## Slice C — AGENTS.md playbook

Add **short** bullets to [`AGENTS.md`](../../AGENTS.md) (no rigid Telegram headers). Candidates from parent doc:

- **Answer shape:** 2–4 short paragraphs; quotes in quotation marks; cite after the claim.
- **Verbatim:** Call `search_transcript` once; if no hit, say so — do not loop.
- **Comparison:** `search_vault_many` with one sub-query per founder; answer both sides or flag missing side.
- **Stop searching:** If two searches return overlapping episodes with score ≥7, synthesize.
- **Retrieve before cite:** Thematic / cross-founder turns must call at least one vault tool before `[ep-NNNN]` citations (reinforce existing rule).

Do **not** add mandatory pre-retrieval in code.

---

## Slice D — Cap nudge enrichment

In [`services/telegram/bot/agent.py`](../../services/telegram/bot/agent.py), when `MAX_TOOL_ROUNDS` hit:

- Append to `SEARCH_BUDGET_NUDGE`: episode ids and chunk count from trace/evidence gathered this turn (keep message concise).

---

## Slice E — `format_load_episode_for_tool()`

### Problem

[`load_episode()`](../../services/telegram/bot/tools/vault.py) returns raw JSON; [`_tool_result_content()`](../../services/telegram/bot/agent.py) `json.dumps` it. Search tools return labeled markdown via [`format_evidence_for_tool()`](../../ingestion/lib/retrieval_orchestrator.py).

### Target shape

Match search evidence blocks: episode id, title, listened flag prominent, stripped frontmatter, capped excerpt, citation hint.

### Module split

```
services/telegram/bot/evidence_format.py
  format_load_episode_for_tool(payload) -> str
  # future: consolidate transcript formatting helpers
```

Wire in `_tool_result_content()` when `evidence` key absent and payload is load_episode result.

**Tests:** [`tests/test_vault_agent.py`](../../tests/test_vault_agent.py) — formatter output shape, frontmatter stripped, `meta.listened` visible, char cap respected.

---

## Slice F — `structured_embed_text` (optional)

In [`ingestion/lib/retrieval_orchestrator.py`](../../ingestion/lib/retrieval_orchestrator.py) `format_evidence_for_tool()`, use [`structured_embed_text`](../../ingestion/lib/search_retrieval.py) for `expanded:` chunks instead of raw excerpt only.

---

## File touch list (expected)

| File | Slice |
|------|-------|
| `dev/harness/scenario_runner.py` | A, B |
| `dev/scenarios/librarian/multi_hop.yaml` | A |
| `dev/scenarios/librarian/multi_founder_comparison.yaml` | A |
| `dev/scenarios/librarian/thematic_cross_episode.yaml` | A |
| `dev/scenarios/librarian/*.yaml` (leak guards) | B |
| `tests/test_harness_scenarios.py` or new harness expect tests | A, B |
| `AGENTS.md` | C |
| `services/telegram/bot/agent.py` | D |
| `services/telegram/bot/evidence_format.py` | E (new) |
| `services/telegram/bot/agent.py` `_tool_result_content` | E |
| `tests/test_vault_agent.py` or `tests/test_evidence_format.py` | E |
| `ingestion/lib/retrieval_orchestrator.py` | F |
| `.cursor/plans/librarian_output_quality.md` | before + after |

---

## Verification

**Laptop (required before merge):**

```bash
ingestion/.venv/bin/pytest tests/test_harness_scenarios.py tests/test_vault_agent.py \
  tests/test_retrieval_orchestrator.py tests/test_telegram_bot.py -q
cd ingestion && ../ingestion/.venv/bin/python pipeline/verify.py
```

**Mac mini (when available — not blocking laptop merge):**

```bash
ingestion/.venv/bin/python dev/mock_telegram_cli.py --preflight
# Lift B validation (if not done yet)
ingestion/.venv/bin/python dev/mock_telegram_cli.py --scenario dev/scenarios/librarian/verbatim_transcript.yaml -v
# Post lift 2
ingestion/.venv/bin/python dev/mock_telegram_cli.py --suite librarian --live-only -v
```

Requires Remote Login on mini for SSH from laptop (`potential-ideas.md`). Reports: `dev/logs/runs/*-report.{json,md}` (gitignored — `scp` back to laptop).

---

## Open decisions for grill-me

1. **Slice order:** harness-first (A) vs evidence-first (E)?
2. **Citation regex:** require on all thematic live scenarios or only `multi_hop` / `multi_founder_comparison`?
3. **Cap nudge:** trace-only summary vs re-read evidence strings (token cost)?
4. **Slice F:** include in lift 2 or defer to lift 3?

---

## Living doc sync

Same protocol as lift B: update [librarian_output_quality.md](librarian_output_quality.md) **before** code (lift 2 in progress) and **after** ship (tick easy wins 3, 6, 7, 8 if F ships; red flags 3, 6, 7, 8).
