---
name: Expanded datapoint retrieval
overview: First shrink the A/B batch to 5 episodes and prune legacy fixtures; then edit only expand_datapoints.candidate.md and re-run expand_tune variant B (5 API calls) against frozen A on the same five.
todos:
  - id: shrink-tune-batch
    content: "Update catalog/expand-tune-batch.json to 5 eps; delete dropped episode folders from baseline/A and B"
    status: pending
  - id: prompt-candidate-only
    content: "Edit only ingestion/prompts/expand_datapoints.candidate.md (retrieval title, From your note, grounding)"
    status: pending
  - id: tune-variant-b-only
    content: "Re-run expand_tune --variant B --apply --force (5 episodes); compare B/ vs frozen A/"
    status: pending
isProject: false
---

# Expanded datapoint organization for retrieval (prompt B only)

## Scope

**In scope (in order):**

1. **Shrink A/B batch to 5 episodes** — update [catalog/expand-tune-batch.json](catalog/expand-tune-batch.json) and **prune** legacy fixture dirs under `ingestion/fixtures/expand-runs/baseline/{A,B}/` for dropped episodes.
2. Edit **[ingestion/prompts/expand_datapoints.candidate.md](ingestion/prompts/expand_datapoints.candidate.md)** only (prompt B).
3. Re-run **`expand_tune --variant B`** on the 5-episode batch (5 API calls); compare `baseline/B/` vs **frozen** `baseline/A/` on the same five.

**Out of scope for this pass:**

- [ingestion/prompts/expand_datapoints.md](ingestion/prompts/expand_datapoints.md) — frozen as A baseline.
- Re-run variant A (unless A’s prompt file changes).
- [build_chunks.py](ingestion/search/build_chunks.py), workflow/retrieval docs — after B promotes.

---

## Step 0 — Shorten the tune batch (do this first)

**Why:** Cuts A/B cost and review time from 10 → **5 OpenRouter calls per variant** (10 total if you ever re-run both; this plan only re-runs B).

### New batch (5 episodes)

| Episode | Id | Role in review |
|---------|-----|----------------|
| 1 | `ep-0001` | Terse bullets → retrieval titles + grounding |
| 22 | `ep-0022` | Mid-catalog sample |
| 66 | `ep-0066` | Many bullets, missing timestamps, long output |
| 105 | `ep-0105` | High bullet count (~8) |
| 189 | `ep-0189` | Mid-catalog sample |

```json
"episode_ids": [
  "ep-0001",
  "ep-0022",
  "ep-0066",
  "ep-0105",
  "ep-0189"
]
```

Update `description` / `notes` in [catalog/expand-tune-batch.json](catalog/expand-tune-batch.json) accordingly.

### Remove from batch (drop legacy fixtures)

Delete episode folders from **both** `baseline/A/` and `baseline/B/`:

- `ep-0042-one-from-many-visa-and-the-rise-of-chaordic-organization`
- `ep-0085-walter-and-olive-ann-beech-aviation-legends`
- `ep-0125-charles-kettering-inventor-engineer-founder`
- `ep-0145-william-randolph-hearst`
- `ep-0166-robert-noyce-intel`

**Keep** fixture trees only for the five ids above (under each variant). No need to re-expand A for kept episodes unless those A drafts are missing or you change prompt A later.

### Touch points (batch size only)

- [ingestion/fixtures/expand-runs/README.md](ingestion/fixtures/expand-runs/README.md) — “10 episodes” → 5, list the five ids.
- [docs/datapoint-workflow.md](docs/datapoint-workflow.md) — sandbox section: 5-episode batch, 5 calls per variant (defer full format doc until promote).
- [AGENTS.md](AGENTS.md) — one-line “10-episode” → “5-episode” if present.

`expand_tune.py` already reads `catalog/expand-tune-batch.json`; no code change required unless `report`/`verify` hardcode “10” (grep and fix if so).

---

## A/B setup

| Variant | File | Role |
|---------|------|------|
| **A** | `expand_datapoints.md` | **Do not edit.** Keep existing `baseline/A/` drafts for the 5 kept episodes. |
| **B** | `expand_datapoints.candidate.md` | **Only file to edit.** Regenerate `baseline/B/` for the 5-episode batch after prompt change. |

---

## Edits to `expand_datapoints.candidate.md` only

### 1. Retrieval-friendly `###` title

- Format: `### {timestamp} — {title}`
- **Title:** 6–12 words, standalone in search. Strip `[approx]` from title, not from anchored note.
- Clear raw bullets: match or lightly polish.

### 2. Anchor raw bullet in Context

- **First sentence:** `From your note: "{verbatim bullet}"` then 1–2 sentences story position.

### 3. Grounding discipline

- No TRANSCRIPT support → say so in Context; do not invent quotes.
- Uncertain match → flag in Context; no confident Quote.

### 4. Unchanged

- Context → Quote → Key takeaway; quote mechanics; one `###` per bullet.

---

## Validation (B only, 5 episodes)

```bash
cd ingestion
# After batch shrink + candidate prompt edit:

python notes/expand_tune.py expand --variant B --apply --force
python notes/expand_tune.py report
python notes/expand_tune.py verify   # optional structural check
```

Compare `baseline/B/` vs `baseline/A/` for all five batch episodes (focus read: **ep-0001**, **ep-0066**).

**After B wins:** `expand_tune.py promote --variant B` → merge to `expand_datapoints.md` + docs (separate step).

---

## What to avoid

| Idea | Verdict |
|------|---------|
| Edit `expand_datapoints.md` during tune | Breaks A/B |
| Re-run A when only B prompt changed | Wasted calls |
| Keep dropped-episode fixture dirs | Clutters diff and confuses review |
| Reorder Context / Quote / Takeaway | Out of scope |

---

## Suggested sequence

1. **Shrink batch** — `expand-tune-batch.json` → 5 ids; delete 5 dropped episode dirs from `baseline/A/` and `baseline/B/`; quick doc string fixes (expand-runs README, datapoint-workflow, AGENTS).
2. Edit **`expand_datapoints.candidate.md`**.
3. `expand_tune.py expand --variant B --apply --force` (5 episodes).
4. `report` + read B vs A on ep-0001, ep-0066 (and spot-check 22, 105, 189).
5. Iterate candidate + B re-run until satisfied; later promote + production docs.
