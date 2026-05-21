# Import drop zone

Place one-time exports here (gitignored). Pass paths explicitly to ingestion scripts.

| Source | Suggested file | Script |
|--------|----------------|--------|
| Apple Notes | `apple-notes.txt` or `.md` | `python import_notes.py --input ../import/apple-notes.txt` |
| X posts (cache) | `x-posts-raw.csv` | `python sync_x_cache.py` then `python organize_posts_from_csv.py` |
| Google Doc (optional) | `google-doc-posts.txt` | legacy: `import_posts_x.py --doc` |

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

Outputs:

- `import/x-posts-raw.csv` — every tweet/reply/article row
- `import/x-posts-sync-meta.json` — sync state
- `content/posts/ep-NNN-.../post.md` — high-confidence Founders matches
- `content/posts/_other/{id}.md` — non-Founders and low-confidence
- `catalog/post-mapping-review.jsonl` — medium-confidence matches for manual review
- `content/posts/_corpus/all-posts.md` — Founders corpus
- `content/posts/_corpus/all-posts-other.md` — other posts corpus
