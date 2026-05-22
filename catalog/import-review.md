# Import review (manual cleanup)

## Apple Notes (completed — archived)

- **189 notes** imported in one shot; workflow is now vault-native only (edit `.notes.md` in git)
- ep-0021 still has manual `XYZ` placeholder if you add that note later
- Script archived: `ingestion/migrations/import_notes_apple.py` — do not re-run (wipes X attribution section in this file)

## X posts — manual attribution (2026-05-21)

| Episode | Status | Source |
|---------|--------|--------|
| ep-0088 | Assigned | Extracted from first-100 recap thread `2016586992859963402` |
| ep-0091 | Assigned | Same recap thread |
| ep-0131 | Assigned | `2027495250260828541` (Friedland quote + @founderspodcast ep. 131) |
| ep-0182 | Assigned | `2054376932901531937` (X labeled `#183`; content matches ep-0182 notes) |
| ep-0148 | Assigned | Promo tweet `2034041777489863124` + full article text (manual paste; API sync had link only) |
| ep-0159 | **Skipped** | Deleted on X or accidentally never posted — no `{folder}.post.md` |
| ep-0189 | **Not posted** | Intentionally empty until you publish on X |

Reply-to-others filter active: 184 rows excluded from attribution (`x_posts_threads.is_reply_to_other`).

## Resolved

- Episode 21 — `XYZ` placeholder in notes (no Apple Notes export)
