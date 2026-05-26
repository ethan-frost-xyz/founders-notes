# Historical migrations

One-shot scripts from the 2026 zero-pad and filename unification rollout. **Do not re-run** on a current vault unless you are restoring from [`catalog/migration-layout-2026-05-21.json`](../../catalog/migration-layout-2026-05-21.json).

| Script | Purpose |
|--------|---------|
| `migrate_episode_layout.py` | `ep-N` → `ep-NNNN`, rename `{folder}.{type}.md`, update catalog paths |
| `migrate_transcript_names.py` | Remove legacy `transcript.md` files inside episode dirs |
| `migrate_episode_frontmatter.py` | Canonical YAML headers on all `content/` episode markdown (body preserved) |
| `import_notes_apple.py` | One-shot Apple Notes export → `content/notes/` (2026; **do not re-run** — overwrites `import-review.md`) |

Run from `ingestion/` if needed: `python migrations/migrate_episode_layout.py --dry-run`
