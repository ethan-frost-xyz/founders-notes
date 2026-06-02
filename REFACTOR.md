# Cut-Noise Refactor — tracking

Branch: `refactor/cut-noise`  
Plan: [.cursor/plans/cut-noise_refactor_cb852e3b.plan.md](.cursor/plans/cut-noise_refactor_cb852e3b.plan.md)

## North star

The **product** is Telegram **Librarian** (v3 orchestrated retrieval) + **Janitor** + the **content vault** they serve. `ingestion/` and `maintain.py` are authoring/dev toolchain — kept only where they feed the bot or the daily ritual.

## Guardrails

| Rule | Detail |
|------|--------|
| Content | `content/**` and `catalog/episodes.jsonl` are **read-only** |
| Indexes | `chunks.jsonl` / embeddings change **only** via `reindex_vault.py` |
| Behavior | No rewrites of live Librarian/Janitor/orchestrator — dead-branch removal only |
| CI | `pytest tests -q` + `cd ingestion && python pipeline/verify.py` green **every commit** |
| Commits | One workstream = one focused commit |

## Interview decisions (locked)

- **Product:** Telegram-centric (Librarian + Janitor + vault).
- **Daily ritual:** Telegram primary; `maintain.py` slimmed to recovery/tactical fallback.
- **X pipeline:** Lean sync → organize (`#N` attribution); cut LLM attribution + dedupe.
- **Migrations/archives:** Delete outright; git history is the archive.
- **Compat shims:** Verify-then-cut per shim.
- **Retrieval:** Remove `search_vault_parent` / `search_transcript` from live agent executor; keep in `tools/vault.py` for tests/harness.
- **Expand tune:** Slim — delete committed fixtures; keep `expand_tune.py` for ad-hoc runs.
- **Docs:** Merge four operator docs → `docs/operations.md` (WS9 last).
- **`/web`:** Remove stub entirely.
- **Execution:** One branch, one commit per workstream.

## Workstreams

| ID | Description | Status | Commit |
|----|-------------|--------|--------|
| WS0 | Branch + this doc + plan + green baseline | done | 5cebdaf |
| WS1 | Delete migrations + historical archives | in progress | |
| WS2 | Lean X pipeline (cut LLM attribution + dedupe) | pending | |
| WS3 | Slim expand-tune sandbox | pending | |
| WS4 | Trim retrieval v2 from live agent executor | pending | |
| WS5 | Remove `/web` stub | pending | |
| WS6 | Verify-then-cut compat shims | pending | |
| WS7 | Slim `maintain.py` (after WS3) | pending | |
| WS8 | Misc dead-code (`ingestion/tests/`, venv note) | pending | |
| WS9 | Docs consolidation (last) | pending | |

## Notes

- **Python venv:** Use `ingestion/.venv` only. A root `.venv` may exist locally — do not document or rely on it.
- **Review queue:** `catalog/post-mapping-review.jsonl` and `content/posts/_other/` remain as `organize` outputs.
