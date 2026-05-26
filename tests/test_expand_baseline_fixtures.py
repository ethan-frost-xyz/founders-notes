"""Integration tests for committed expand-tune baseline fixtures (no network)."""

import json
import subprocess
import sys

import paths
from catalog import load_catalog
from expand_llm import validate_expanded_draft
from markdown_io import read_markdown_body
from expand_tune import DEFAULT_RUN_ID, load_batch_file, manifest_path, run_dir
from paths import staging_draft_file_path

BATCH_FILE = paths.ROOT / "catalog" / "expand-tune-batch.json"


def _catalog_by_id() -> dict[str, dict]:
    return {r["id"]: r for r in load_catalog()}


def test_baseline_drafts_validate():
    episode_ids = load_batch_file(BATCH_FILE)
    by_id = _catalog_by_id()
    staging = run_dir(DEFAULT_RUN_ID)
    failures: list[str] = []
    for ep_id in episode_ids:
        row = by_id[ep_id]
        npath = paths.notes_file_path(
            row["id"], row["slug"], row.get("episode_number")
        )
        for variant in ("A", "B"):
            draft = staging_draft_file_path(
                staging,
                variant,
                row["id"],
                row["slug"],
                row.get("episode_number"),
            )
            if not draft.exists():
                failures.append(f"missing {draft.relative_to(paths.ROOT)}")
                continue
            body = read_markdown_body(draft)
            errors, _ = validate_expanded_draft(npath, body)
            if errors:
                failures.append(f"{ep_id} {variant}: " + "; ".join(errors))
    assert not failures, "\n".join(failures)


def test_baseline_verify_cli():
    result = subprocess.run(
        [sys.executable, str(paths.INGESTION_DIR / "notes" / "expand_tune.py"), "verify"],
        cwd=str(paths.ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_baseline_manifest_records_variants():
    data = json.loads(manifest_path(DEFAULT_RUN_ID).read_text(encoding="utf-8"))
    assert data.get("run_id") == DEFAULT_RUN_ID
    assert "A" in data.get("variants", {})
    assert "B" in data.get("variants", {})
