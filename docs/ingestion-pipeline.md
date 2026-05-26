# Ingestion pipeline overview

All ingestion scripts live under [`ingestion/`](../ingestion/). **Always run from `ingestion/`** with the venv active:

```bash
cd ingestion
source .venv/bin/activate
```

Master index: [`ingestion/README.md`](../ingestion/README.md).

## Sections

| Area | Folder | Doc |
|------|--------|-----|
| Catalog + verify | `ingestion/pipeline/` | [pipeline/README.md](../ingestion/pipeline/README.md) |
| Transcripts | `ingestion/transcripts/` | [transcripts/README.md](../ingestion/transcripts/README.md) |
| Notes + expansion | `ingestion/notes/` | [notes/README.md](../ingestion/notes/README.md) |
| X posts | `ingestion/x/` | [x/README.md](../ingestion/x/README.md) |
| Search | `ingestion/search/` | [search/README.md](../ingestion/search/README.md) |
| Shared code | `ingestion/lib/` | [lib/README.md](../ingestion/lib/README.md) |

## End-to-end (new episode)

```bash
python pipeline/sync_new.py --apply
python pipeline/map_colossus.py
python transcripts/fetch_transcripts.py --id ep-NNNN
python notes/scaffold_notes.py --missing
python pipeline/verify.py
```

## Daily notes

See [notes-pipeline.md](notes-pipeline.md).

## X posts

See [import/README.md](../import/README.md).

## Related

- [episode-id-rules.md](episode-id-rules.md) — ids, frontmatter, CLI flags
- [datapoint-workflow.md](datapoint-workflow.md) — expansion workflow
- [retrieval.md](retrieval.md) — chunks and search
