# Transcript fetch

Download episode transcripts from Colossus into `content/transcripts/{folder}/{folder}.transcript.md`.

Run from `ingestion/`:

```bash
python transcripts/fetch_transcripts.py --id ep-0200
python transcripts/fetch_transcripts.py   # pending rows in catalog
```

## Environment

Set in repo root `.env`:

| Variable | Purpose |
|----------|---------|
| `COLOSSUS_EMAIL`, `COLOSSUS_PASSWORD` | Login |
| `COLOSSUS_COOKIES_FILE` | Alternative to login (saved session cookies) |

Requires `colossus_url` on each catalog row (`pipeline/map_colossus.py` first).

## Flags

| Flag | Meaning |
|------|---------|
| `--id ep-NNNN` | Single episode |
| `--force` | Re-fetch even if transcript exists |
| `--dry-run` | Report without writing |

## Upstream / downstream

- **Before:** `pipeline/map_colossus.py`
- **After:** `notes/scaffold_notes.py`, `pipeline/verify.py`
