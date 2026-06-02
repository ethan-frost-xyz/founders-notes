# Import drop zone

Place one-time exports here (gitignored). Pass paths explicitly to ingestion scripts.

| Source | Suggested file | Script |
|--------|----------------|--------|
| X posts (cache) | `x-posts-raw.csv` | `x/sync_x_cache.py` then `x/organize_posts_from_csv.py` |
| Manual post body | any `.txt` file | `x/assign_post_manual.py --body-file path` |

Personal exports and X cache are not committed (see `.gitignore`).

**Notes:** Study notes live in `content/notes/` and are edited directly in git ([docs/notes-pipeline.md](../docs/notes-pipeline.md)).

## Coverage gaps are not import failures

`catalog/gaps.md` low counts are **expected** while you work through the catalog (~1 episode/day):

- **Notes without datapoints** — not listened yet.
- **Missing posts** — not posted on X yet (today the list starts around **ep-0190** because ~187 posts exist through ~ep-0188).

Do not bulk-fix these lists. Only **blocking** gaps are transcript/layout (`verify.py` exit 1).

## Recurring workflow (after each X post)

```bash
cd ingestion
source .venv/bin/activate

python x/sync_x_cache.py
python x/organize_posts_from_csv.py
python pipeline/verify.py
```

- **Organize** auto-maps tweets with explicit Founders `#N` / `ep. N` (high confidence).
- **Native X articles** (`post_kind: article`) are **skipped** by organize — not written to `content/posts/`. Legacy bodies use manual assign below.
- **Low-confidence** rows land in `catalog/post-mapping-review.jsonl` or `content/posts/_other/` — fix with `assign_post_manual.py` or edit attribution in the review file.

`organize_posts_from_csv.py` **rewrites** `post-mapping-review.jsonl` each run. Record manual resolutions in [`catalog/import-review.md`](../catalog/import-review.md).

## One-time / rare

```bash
# Grow CSV history (optional; not needed to “close” ep-0190+ gaps)
python x/sync_x_cache.py --full
```

## Manual assignment

For native X articles, recap threads, wrong `#` on X, or link-only promos:

```bash
python x/assign_post_manual.py --episode 82 --x-post-id 2020587382983237949 \
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
