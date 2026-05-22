# Import drop zone

Place one-time exports here (gitignored). Pass paths explicitly to ingestion scripts.

| Source | Suggested file | Script |
|--------|----------------|--------|
| Apple Notes | `apple-notes.txt` or `.md` | `python import_notes.py --input ../import/apple-notes.txt` |
| X posts (cache) | `x-posts-raw.csv` | `python sync_x_cache.py` then `python organize_posts_from_csv.py` |
| Manual post body | any `.txt` file | `assign_post_manual.py --body-file path` |

Personal exports and X cache are not committed (see `.gitignore`).

## X posts workflow (CSV-first)

```bash
cd ingestion
source .venv/bin/activate

# One-time backfill (uses API; writes import/x-posts-raw.csv)
python sync_x_cache.py --full

# Later: cheap incremental sync (stops at known tweet ids)
python sync_x_cache.py

# Organize from CSV only (no API calls)
python organize_posts_from_csv.py --dry-run
python organize_posts_from_csv.py
```

Manual assignment when organize misses an episode (link-only articles, recap threads, wrong `#` on X):

```bash
python assign_post_manual.py --episode 148 --x-post-id 2034041777489863124 \
  --published-at 2026-03-17 --post-kind article --body-file ../import/body.txt
```

Outputs:

- `import/x-posts-raw.csv` — every tweet/reply/article row
- `import/x-posts-sync-meta.json` — sync state
- `content/posts/ep-NNN-.../post.md` — high-confidence Founders matches
- `content/posts/_other/{id}.md` — non-Founders and low-confidence
- `catalog/post-mapping-review.jsonl` — medium-confidence matches for manual review
- `content/posts/_corpus/all-posts.md` — Founders corpus
- `content/posts/_corpus/all-posts-other.md` — other posts corpus
