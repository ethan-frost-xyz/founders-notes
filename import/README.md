# Import drop zone

Place one-time exports here (gitignored). Pass paths explicitly to ingestion scripts.

| Source | Suggested file | Script |
|--------|----------------|--------|
| X posts (cache) | `x-posts-raw.csv` | `sync_x_cache.py` then `organize_posts_from_csv.py` |
| Manual post body | any `.txt` file | `assign_post_manual.py --body-file path` |

Personal exports and X cache are not committed (see `.gitignore`).

**Notes:** Study notes live in `content/notes/` and are edited directly in git ([docs/notes-pipeline.md](../docs/notes-pipeline.md)). Apple Notes backfill was a one-shot migration ([`ingestion/migrations/import_notes_apple.py`](../ingestion/migrations/import_notes_apple.py)).

## Coverage gaps are not import failures

`catalog/gaps.md` low counts are **expected** while you work through the catalog (~1 episode/day):

- **Notes without datapoints** — not listened yet.
- **Missing posts** — not posted on X yet (today the list starts around **ep-0190** because ~187 posts exist through ~ep-0188).

Do not bulk-fix these lists. Only **blocking** gaps are transcript/layout (`verify.py` exit 1).

## Recurring workflow (after each X post)

```bash
cd ingestion
source .venv/bin/activate

python sync_x_cache.py
python organize_posts_from_csv.py
python attribute_posts_llm.py --dry-run   # optional: ambiguous review queue
python attribute_posts_llm.py --apply     # when dry-run looks right
python verify.py
```

- **Organize** auto-maps tweets with explicit Founders `#N` / `ep. N` (high confidence).
- **Native X articles** (`post_kind: article`) are **skipped** by organize — not written to `content/posts/`. You will not post articles going forward; legacy bodies use manual assign below.
- **LLM** (`attribute_posts_llm.py`) handles medium-confidence rows in `catalog/post-mapping-review.jsonl` (requires `OPENROUTER_API_KEY`, `OPENROUTER_ATTRIBUTION_MODEL` optional).

`organize_posts_from_csv.py` **rewrites** `post-mapping-review.jsonl` each run. Record manual resolutions in [`catalog/import-review.md`](../catalog/import-review.md).

## One-time / rare

```bash
# Grow CSV history (optional; not needed to “close” ep-0190+ gaps)
python sync_x_cache.py --full
```

## Manual assignment

For native X articles, recap threads, wrong `#` on X, or link-only promos:

```bash
python assign_post_manual.py --episode 82 --x-post-id 2020587382983237949 \
  --published-at 2026-02-08 --post-kind article --body-file ../import/ep-0082-article.txt
```

See [`catalog/import-review.md`](../catalog/import-review.md) for ep-0082, ep-0088, ep-0148.

## Outputs

- `import/x-posts-raw.csv` — every tweet/reply/article row
- `import/x-posts-sync-meta.json` — sync state
- `content/posts/ep-NNNN-.../ep-NNNN-....post.md` — high-confidence Founders matches
- `content/posts/_other/{id}.md` — non-Founders and low-confidence
- `catalog/post-mapping-review.jsonl` — medium-confidence matches for LLM / manual review
- `content/posts/_corpus/all-posts.md` — Founders corpus
- `content/posts/_corpus/all-posts-other.md` — other posts corpus
