---
name: Unify Episode Headers
overview: Unify episode markdown frontmatter across transcripts, raw notes, expanded notes, drafts, and posts, while keeping LLM expansion output body-only. Also make the chunk index carry normalized episode metadata for better future retrieval.
todos:
  - id: frontmatter-helper
    content: Create shared episode frontmatter helper and route all markdown writers through it
    status: pending
  - id: expanded-workflow
    content: Update expanded draft/promote flow to use canonical headers while keeping model output body-only
    status: pending
  - id: schema-verify
    content: Add frontmatter parsing and validation to verify/layout checks
    status: pending
  - id: chunk-metadata
    content: Include normalized episode metadata in generated search chunks
    status: pending
  - id: migration-docs
    content: Backfill canonical frontmatter across all existing content markdown while preserving bodies, then update schema/retrieval docs
    status: pending
  - id: validation
    content: Run verify and rebuild chunk index to validate the change
    status: pending
isProject: false
---

# Unify Episode Markdown Headers

## Scope
- Add a canonical episode frontmatter model in [`ingestion/lib/markdown_io.py`](ingestion/lib/markdown_io.py) so all generated episode markdown starts with the same core fields in the same order.
- Keep type-specific metadata, but move it behind a shared base header rather than each writer hand-building unrelated dictionaries.
- Preserve the expanded workflow’s current boundary: LLM returns only `## Expanded datapoints`; Python wraps it with frontmatter.
- Backfill all prior episode markdown files under `content/` to the canonical header format while preserving body content exactly.
- Extend validation and docs so future agents can rely on the schema.
- Improve retrieval metadata in [`catalog/chunks.jsonl`](catalog/chunks.jsonl) by copying normalized frontmatter/catalog fields into chunk rows.

## Canonical Header Shape
Core fields for every episode markdown file:

```yaml
---
id: "ep-0001"
episode_number: 1
title: "#1 Elon Musk: Tesla, SpaceX, & the Quest for a Fantastic Future"
content_type: "expanded"
source: "expand_llm"
published_at: "2016-09-19"
founders_url: "https://www.founderspodcast.com/episodes/..."
created_at: "2026-05-26T14:37:02Z"
---
```

Type-specific fields stay after the core block:
- `transcript`: `colossus_url`, `fetched_at`
- `notes`: `imported_at`
- `post`: `x_url`, `x_post_id`, `post_kind`, `attribution_note`, `alt_source`, `imported_at`
- `expanded.draft`: `model`, `generated_at`, `prompt_path`, `prompt_hash`, `tune_variant`
- `expanded`: `expanded_at`, `expanded_model`, `prompt_hash` if available

## Implementation Steps
1. Update [`ingestion/lib/markdown_io.py`](ingestion/lib/markdown_io.py):
   - Add a shared `episode_frontmatter(row, content_type, source, extra)` helper.
   - Make `write_notes_md`, `write_post_md`, and `write_transcript_md` use it.
   - Keep `write_frontmatter_md` as the low-level serializer, but ensure stable ordering comes from the helper.

2. Update expanded writers in [`ingestion/lib/expand_llm.py`](ingestion/lib/expand_llm.py):
   - Use the same frontmatter helper for `.expanded.draft.md` and `.expanded.md`.
   - Preserve `parse_expanded_body()` behavior so model output still starts at `## Expanded datapoints` and never contains frontmatter.
   - Carry prompt/model metadata from draft to promoted expanded files where useful.

3. Add frontmatter parsing + schema validation:
   - Add a small parser in [`ingestion/lib/markdown_io.py`](ingestion/lib/markdown_io.py) or reuse `_parse_simple_frontmatter` after moving it out of [`ingestion/lib/expand_llm.py`](ingestion/lib/expand_llm.py).
   - Extend [`ingestion/lib/layout.py`](ingestion/lib/layout.py) / [`ingestion/pipeline/verify.py`](ingestion/pipeline/verify.py) to report missing core fields, mismatched `id`, invalid `content_type`, and missing required type-specific fields.

4. Update retrieval indexing in [`ingestion/search/build_chunks.py`](ingestion/search/build_chunks.py):
   - Parse frontmatter when indexing each markdown file.
   - Add stable metadata to each chunk: `title`, `episode_number`, `content_type`, `published_at`, maybe `source`.
   - Keep `source_path`, `section`, and line ranges unchanged for citation stability.

5. Backfill all existing episode markdown files with a deterministic script:
   - Add a migration under [`ingestion/migrations/`](ingestion/migrations/) that rewrites only frontmatter for every existing episode markdown file in [`content/transcripts/`](content/transcripts/), [`content/notes/`](content/notes/), and [`content/posts/`](content/posts/), including any existing `.expanded.md` and `.expanded.draft.md` files in canonical content locations.
   - Preserve body content exactly: split frontmatter from body, rewrite the frontmatter block only, and write the original body bytes/string back unchanged.
   - Add a body-preservation check in the migration, such as hashing or direct comparison of the body before and after each rewrite, and fail loudly if any body changes.
   - Derive canonical fields from [`catalog/episodes.jsonl`](catalog/episodes.jsonl) plus existing frontmatter type-specific values, so old fields like `x_post_id`, `fetched_at`, `imported_at`, model metadata, and prompt metadata are retained.
   - Include `--dry-run` and `--apply`.
   - Report counts by content type and list files whose existing frontmatter cannot be safely normalized.
   - Leave historical prompt-tuning fixtures under [`ingestion/fixtures/expand-runs/`](ingestion/fixtures/expand-runs/) out of the default backfill unless explicitly requested, since they are comparison artifacts rather than canonical episode content.

6. Update docs:
   - Expand [`docs/episode-id-rules.md`](docs/episode-id-rules.md) with the canonical core header and per-type field tables.
   - Update [`docs/datapoint-workflow.md`](docs/datapoint-workflow.md) to explicitly say expanded LLM output is body-only and frontmatter is generated by tooling.
   - Update [`docs/retrieval.md`](docs/retrieval.md) to document chunk metadata.

7. Verify:
   - Run `python pipeline/verify.py` from [`ingestion/`](ingestion/).
   - Run `python search/build_chunks.py` and inspect a few chunk rows for normalized metadata.
   - After migration, spot-check representative transcript, notes, post, expanded draft, and expanded files.
   - Confirm the migration’s body-preservation checks passed for every rewritten file.

## Notes
- I will not commit `.env` or touch secrets.
- I will avoid changing all markdown body content, not just note/post/transcript bodies.
- Existing generated fixtures can remain as historical outputs unless you want those normalized too; the canonical backfill target is `content/`.