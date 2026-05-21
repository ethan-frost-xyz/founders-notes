# Import drop zone

Place one-time exports here (gitignored). Pass paths explicitly to ingestion scripts.

| Source | Suggested file | Script |
|--------|----------------|--------|
| Apple Notes | `apple-notes.txt` or `.md` | `python import_notes.py --input ../import/apple-notes.txt` |
| Google Doc (optional) | `google-doc-posts.txt` | same heuristics as notes; merge via `--doc` on `import_posts_x.py` |

Personal exports are not committed. Copy from Apple Notes: select all → export or paste into a `.txt` file.
