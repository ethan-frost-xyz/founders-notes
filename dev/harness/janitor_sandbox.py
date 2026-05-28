"""Temporary vault directory for Janitor harness runs (never touches real notes)."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from harness.mock_session import REPO_ROOT, _ensure_import_paths

_PATH_KEYS = (
    "ROOT",
    "CATALOG_PATH",
    "CHUNKS_PATH",
    "NOTES_DIR",
    "TRANSCRIPTS_DIR",
    "POSTS_DIR",
)


class JanitorSandbox:
    """Isolated vault slice for one episode; patches ingestion paths globals in-process."""

    def __init__(
        self,
        real_vault_root: Path | None = None,
        episode_id: str = "ep-0191",
        *,
        keep: bool = False,
        base_dir: Path | None = None,
    ) -> None:
        self.real_vault_root = (real_vault_root or REPO_ROOT).resolve()
        self.episode_id = episode_id
        self.keep = keep
        self.base_dir = (base_dir or REPO_ROOT / "dev" / "logs" / "sandbox").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._tmpdir: Path | None = None
        self._saved_paths: dict[str, Any] | None = None
        self._created_at = time.time()

    @property
    def vault_root(self) -> Path:
        if self._tmpdir is None:
            raise RuntimeError("JanitorSandbox not entered")
        return self._tmpdir

    def __enter__(self) -> JanitorSandbox:
        _ensure_import_paths(self.real_vault_root)
        from catalog import load_catalog, resolve_catalog_row

        row = resolve_catalog_row(load_catalog(), self.episode_id)
        self._tmpdir = Path(
            tempfile.mkdtemp(prefix=f"janitor-{self.episode_id}-", dir=self.base_dir)
        )
        self._build_tree(row)
        self._patch_paths()
        return self

    def __exit__(self, *exc: object) -> None:
        self._restore_paths()
        if self._tmpdir and not self.keep:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        self._tmpdir = None

    def _build_tree(self, row: dict[str, Any]) -> None:
        assert self._tmpdir is not None
        root = self._tmpdir
        ingestion_link = root / "ingestion"
        if ingestion_link.exists() or ingestion_link.is_symlink():
            ingestion_link.unlink()
        ingestion_link.symlink_to(self.real_vault_root / "ingestion", target_is_directory=True)

        catalog_dir = root / "catalog"
        catalog_dir.mkdir(parents=True)
        src_catalog = self.real_vault_root / "catalog" / "episodes.jsonl"
        ep_line = None
        with src_catalog.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                if row["id"] in line:
                    ep_line = line
                    break
        if ep_line is None:
            ep_line = json.dumps(row) + "\n"
        (catalog_dir / "episodes.jsonl").write_text(ep_line, encoding="utf-8")
        (catalog_dir / "chunks.jsonl").write_text("", encoding="utf-8")

        import paths as vault_paths

        folder = vault_paths.folder_name(row["id"], row["slug"], row.get("episode_number"))
        for rel_key in ("transcript_path", "notes"):
            src_rel = row.get(rel_key)
            if not src_rel:
                continue
            src = self.real_vault_root / src_rel
            if not src.is_file():
                continue
            dest = root / src.relative_to(self.real_vault_root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

        notes_rel = (
            row.get("notes")
            or f"content/notes/{folder}/{folder}.notes.md"
        )
        notes_dest = root / notes_rel
        if not notes_dest.is_file():
            notes_dest.parent.mkdir(parents=True, exist_ok=True)
            notes_dest.write_text(
                f"---\nepisode_id: {row['id']}\n---\n\n# Harness scaffold\n",
                encoding="utf-8",
            )

    def _patch_paths(self) -> None:
        import paths as vault_paths

        self._saved_paths = {k: getattr(vault_paths, k) for k in _PATH_KEYS}
        root = self.vault_root
        vault_paths.ROOT = root
        vault_paths.CATALOG_PATH = root / "catalog" / "episodes.jsonl"
        vault_paths.CHUNKS_PATH = root / "catalog" / "chunks.jsonl"
        vault_paths.NOTES_DIR = root / "content" / "notes"
        vault_paths.TRANSCRIPTS_DIR = root / "content" / "transcripts"
        vault_paths.POSTS_DIR = root / "content" / "posts"

    def _restore_paths(self) -> None:
        if not self._saved_paths:
            return
        import paths as vault_paths

        for key, value in self._saved_paths.items():
            setattr(vault_paths, key, value)
        self._saved_paths = None

    def inspect(self) -> dict[str, Any]:
        """Files under the sandbox created or modified since enter."""
        root = self.vault_root
        files: list[str] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.stat().st_mtime >= self._created_at - 1:
                files.append(str(path.relative_to(root)))
        return {"vault_root": str(root), "files": sorted(files)}
