"""Integration tests for committed expand-tune baseline fixtures (no network)."""

import json
import subprocess
import sys

import paths
from expand_tune import DEFAULT_RUN_ID, manifest_path


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
