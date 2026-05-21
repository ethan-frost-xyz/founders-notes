#!/usr/bin/env python3
"""Regenerate catalog/gaps.md and print completeness stats."""

from __future__ import annotations

from pathlib import Path

from vault_lib import CATALOG_PATH, GAPS_PATH, ROOT, load_catalog, transcript_dir

BLOCKING_STATUSES = {"pending", "failed"}


def main() -> None:
    rows = load_catalog()
    if not rows:
        raise SystemExit("catalog/episodes.jsonl is empty — run build_catalog.py")

    numbered = [r for r in rows if r.get("episode_number") is not None]
    specials = [r for r in rows if r.get("episode_number") is None]
    complete = [r for r in rows if r.get("transcript_status") == "complete"]
    blocking = [
        r
        for r in numbered
        if r.get("transcript_status") in BLOCKING_STATUSES
        or (r.get("colossus_url") and r.get("transcript_status") not in ("complete", "coming_soon", "no_transcript"))
    ]
    unmapped = [r for r in numbered if not r.get("colossus_url")]
    missing_files = []
    for r in complete:
        rel = r.get("transcript_path")
        if not rel or not (ROOT / rel).exists():
            missing_files.append(r["id"])

    lines = [
        "# Catalog gaps (auto-generated)",
        "",
        f"**Total episodes:** {len(rows)}",
        f"**Numbered:** {len(numbered)} | **Specials:** {len(specials)}",
        f"**Transcripts complete:** {len(complete)}",
        "",
    ]

    if unmapped:
        lines.append(f"## Unmapped Colossus URLs ({len(unmapped)})")
        lines.append("")
        for r in unmapped[:50]:
            lines.append(f"- `{r['id']}` — {r['title']} — {r['founders_url']}")
        if len(unmapped) > 50:
            lines.append(f"- … and {len(unmapped) - 50} more")
        lines.append("")

    if blocking:
        lines.append(f"## Blocking transcript gaps ({len(blocking)})")
        lines.append("")
        for r in blocking[:50]:
            err = r.get("last_error") or r.get("transcript_status")
            lines.append(f"- `{r['id']}` — {err}")
        if len(blocking) > 50:
            lines.append(f"- … and {len(blocking) - 50} more")
        lines.append("")

    documented = [
        r
        for r in rows
        if r.get("transcript_status") in ("coming_soon", "no_transcript")
        and r not in blocking
    ]
    if documented:
        lines.append(f"## Documented exceptions ({len(documented)})")
        lines.append("")
        for r in documented[:30]:
            lines.append(f"- `{r['id']}` — {r['transcript_status']}")
        lines.append("")

    if missing_files:
        lines.append(f"## Missing transcript files ({len(missing_files)})")
        for mid in missing_files[:20]:
            lines.append(f"- `{mid}`")
        lines.append("")

    if not unmapped and not blocking and not missing_files:
        lines.append("No blocking gaps. Phase 1 transcript archive is complete.")
        lines.append("")

    GAPS_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Catalog: {len(rows)} rows")
    print(f"Complete: {len(complete)} / {len(numbered)} numbered")
    print(f"Unmapped colossus_url: {len(unmapped)}")
    print(f"Blocking gaps: {len(blocking)}")
    print(f"Wrote {GAPS_PATH.relative_to(ROOT)}")

    if len(rows) < 400:
        raise SystemExit(f"VERIFY FAILED: expected >= 400 rows, got {len(rows)}")
    if unmapped:
        raise SystemExit(f"VERIFY FAILED: {len(unmapped)} numbered episodes lack colossus_url")
    if blocking:
        raise SystemExit(f"VERIFY FAILED: {len(blocking)} blocking transcript gaps")
    if missing_files:
        raise SystemExit(f"VERIFY FAILED: {len(missing_files)} complete rows missing files")


if __name__ == "__main__":
    main()
