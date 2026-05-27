---
name: Import lane next ship
overview: "Tooling/docs pass only: make coverage gaps unmistakably intentional, skip X articles in organize, fix ep-0082/ep-0088 via manual workflow, add a small OpenAI CLI for ambiguous post attribution. No bulk backfill or closing ep-0190+ gaps."
todos:
  - id: docs-coverage-model
    content: AGENTS.md + import/README + README §2 — gaps beyond current episode = not covered yet; not import failures
    status: completed
  - id: skip-articles-organize
    content: organize/x_posts_threads — exclude post_kind article from attribution; document manual assign_post_manual for legacy
    status: completed
  - id: manual-ep-82-88
    content: import-review.md — ep-0082/ep-0088 need article body via --body-file; correct wrong auto content
    status: completed
  - id: attribute-posts-llm
    content: New ingestion/attribute_posts_llm.py — OpenAI small model, review queue + explicit rules first
    status: completed
  - id: recurring-workflow-doc
    content: import/README — recurring steps after each X post (sync → organize → optional LLM)
    status: completed
isProject: false
---

# Import README + next ship (final plan)

## Guidelines alignment ([.cursor/guidelines.mdc](.cursor/guidelines.mdc))

- **Think before coding:** Scope locked to your answers—tooling/docs only, no sync runs in this pass.
- **Simplicity:** Three-tier attribution (explicit → skip articles → LLM for ambiguous). No regex matcher expansion, no article fetch, no bulk gap closing.
- **Surgical:** Touch `organize_posts_from_csv.py`, new `attribute_posts_llm.py`, docs, `import-review.md`—not notes/transcripts.
- **Goal-driven:** Verify with pytest + `organize --dry-run` showing articles skipped; LLM script dry-run on review JSONL.

---

## Coverage model (non-negotiable clarity)

**Gaps beyond your current episode are because you have not covered those episodes yet—not broken import.**

| `catalog/gaps.md` section | Meaning |
|---------------------------|---------|
| Notes without datapoints | Not listened yet (includes empty scaffolds ep 0190–0417 and backlog in 1–189). |
| Missing posts | Not posted on X yet. List starts at **ep-0190** because ~**187** posts exist through ~ep-0188. |
| Post gaps (documented) | ep-0159 skipped; ep-0189 not posted yet. |

Agents must **not** bulk-fix missing posts or notes lists. Daily ritual advances the frontier (~1 episode/day).

Existing `gaps.md` WIP banner is sufficient—**no `gaps_report.py` split** per your preference. Reinforce in [AGENTS.md](AGENTS.md), [import/README.md](import/README.md), and [README.md](README.md) § “What to build next” (remove “~400+ posts” framing).

---

## [import/README.md](import/README.md)

Still accurate for drop-zone role. Add in this pass:

- Coverage callout (above)
- **Recurring workflow** after each X post
- **Articles ignored** in organize; legacy bodies via `assign_post_manual.py --body-file`
- Optional third step: `attribute_posts_llm.py` for ambiguous rows

---

## Corrections (was wrong in prior plan)

| Item | Correction |
|------|------------|
| ep-0148 only article | **ep-0082, ep-0088, ep-0148** are native X articles. ep-0082 `.post.md` has wrong reply content; ep-0088 has recap excerpt, not full article. |
| Article fetch feature | **Removed.** You will not post articles going forward. Pipeline skips `post_kind: article`. |
| Regex matcher PR | **Removed.** Use OpenAI for non-explicit cases. |
| `--full` backfill / 400+ posts | **Removed.** Not goals; ep-0190+ gaps are intentional. |

---

## Next ship — tooling only (one PR)

### 1. Skip articles in organize

In [ingestion/x_posts_threads.py](ingestion/x_posts_threads.py) or [organize_posts_from_csv.py](ingestion/organize_posts_from_csv.py):

- Do not map or write `content/posts/...` for units where root `post_kind == "article"`.
- Optionally log/count `skipped_articles` in dry-run output.
- CSV rows remain in `import/x-posts-raw.csv` for history; they are not Founders episode posts unless manually assigned.

`classify_post_kind` in [x_posts_csv.py](ingestion/x_posts_csv.py) (`note_tweet` → `"article"`) stays as-is for CSV fidelity.

### 2. Manual fixes (document + you run when ready)

Update [catalog/import-review.md](catalog/import-review.md):

| Episode | Issue | Action |
|---------|-------|--------|
| ep-0082 | Auto-mapped reply text, not article body | `assign_post_manual.py --episode 82 --x-post-id … --body-file ../import/ep-0082-article.txt` |
| ep-0088 | Recap excerpt only | Same pattern with full article paste |
| ep-0148 | Already manual; keep as reference | No change unless you re-paste body |

This pass documents commands; **you** paste bodies (not committed in `import/`).

### 3. `attribute_posts_llm.py` (OpenAI, small model)

New script—**only** for rows that fail explicit match and are not articles.

**Tiered rules (cheap first):**

1. **Explicit** — existing `match_episode` / `EP_MENTION_RE` with score ≥ `AUTO_ACCEPT_SCORE` → unchanged in organize.
2. **Skip** — `post_kind == article` → no attribution.
3. **LLM** — medium-confidence / review-queue rows: prompt with tweet text + compact catalog slice (episode_number, title, published_at for numbered episodes); model returns `episode_number` or `none`.

**CLI sketch:**

```bash
python attribute_posts_llm.py --dry-run          # read post-mapping-review.jsonl
python attribute_posts_llm.py --apply            # write .post.md + update import-review note
```

- Env: `OPENAI_API_KEY`, model default `gpt-4o-mini` (or configurable `--model`).
- `--dry-run` prints proposed mappings; `--apply` calls existing `write_post_md` / manual path helpers.
- Do not auto-apply below confidence threshold; leave row in review JSONL.

Add `.env.example` entry + one pytest with mocked API response.

### 4. Recurring workflow (import/README)

```bash
cd ingestion && source .venv/bin/activate
python sync_x_cache.py                    # after you post on X
python organize_posts_from_csv.py         # explicit # → .post.md; articles skipped
python attribute_posts_llm.py --dry-run   # optional: ambiguous only
python attribute_posts_llm.py --apply     # when dry-run looks right
python verify.py
```

No `--full` unless you explicitly want older CSV history later.

---

## Explicitly out of scope

- Running sync/organize in agent session
- `gaps_report.py` frontier split
- Native X article body fetch
- Regex matcher expansion
- Closing ep-0190+ missing posts/notes
- Datapoint expansion batch mode (separate README goal #3)

---

## Success criteria

| Check | Pass when |
|-------|-----------|
| Clarity | Docs state gaps beyond current episode = **not covered yet** |
| Articles | organize dry-run skips article units; no new article `.post.md` from CSV |
| LLM | `attribute_posts_llm.py --dry-run` runs with mocked/real API; rules documented |
| Manual | import-review lists ep-0082/0088 correction steps |
| Tests | pytest for article skip + LLM helper (mocked) |

---

## Your decisions (recorded)

| Question | Choice |
|----------|--------|
| Execution scope | Tooling/docs only |
| Frontier in gaps.md | Not needed |
| Ambiguous attribution | OpenAI CLI (`attribute_posts_llm.py`), not regex |
| Articles | Ignore in pipeline; manual workflow for ep-0082, 0088 (and ep-0148 reference) |

Execute when you say **go ahead** / **implement the plan**.
