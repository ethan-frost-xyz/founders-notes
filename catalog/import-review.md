# Import review (manual cleanup)

## Apple Notes (historical)

**189 notes** were bulk-imported once (`source: apple_notes_import` in frontmatter). Workflow is vault-native only — edit `.notes.md` in git. One-shot importer removed (git history before `2fb9d22`). ep-0021 may still have a manual `XYZ` placeholder.

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

Organize skips `post_kind: article` units; assign bodies manually for native X articles.

## Native X articles — needs manual body paste

These episodes were published as X articles. Auto-organize must not own them. Paste full article text into `import/*.txt` (gitignored) and run `assign_post_manual.py`.

| Episode | x_post_id | Issue | Command |
|---------|-----------|-------|---------|
| ep-0082 | `2020587382983237949` | Current `.post.md` has wrong reply chatter, not article body | `assign_post_manual.py --episode 82 --x-post-id 2020587382983237949 --published-at 2026-02-08 --post-kind article --body-file ../import/ep-0082-article.txt` |
| ep-0088 | `2016586992859963402` | Recap excerpt only; need full article body | `assign_post_manual.py --episode 88 --x-post-id 2016586992859963402 --published-at 2026-01-28 --post-kind article --body-file ../import/ep-0088-article.txt` |
| ep-0148 | `2034041777489863124` | Reference — already assigned with manual paste | Re-run only if you want to replace body |

## Resolved

- Episode 21 — `XYZ` placeholder in notes (no Apple Notes export)
