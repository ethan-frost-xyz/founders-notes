"""Write expanded drafts and promote validated drafts to .expanded.md."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from expand_validate import validate_expanded_draft
from markdown_io import (
    parse_frontmatter,
    read_markdown_body,
    write_expanded_draft_md,
    write_expanded_md,
    write_frontmatter_md,
)
import paths
from paths import (
    expanded_draft_file_path,
    expanded_file_path,
    notes_file_path,
    path_relative_to_root,
    staging_draft_file_path,
)


def prompt_file_hash(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes())
    return h.hexdigest()[:16]


def resolve_draft_path(
    row: dict[str, Any],
    *,
    staging_root: Path | None = None,
    variant: str | None = None,
    out_path: Path | None = None,
) -> Path:
    """Resolve draft output path (production notes dir or tune sandbox)."""
    if out_path is not None:
        return out_path
    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    if staging_root is not None:
        if not variant:
            raise ValueError("variant required when staging_root is set")
        return staging_draft_file_path(staging_root, variant, ep_id, slug, num)
    return expanded_draft_file_path(ep_id, slug, num)


def write_expanded_draft(
    row: dict[str, Any],
    expanded_body: str,
    *,
    model: str,
    prompt_path: Path,
    out_path: Path | None = None,
    staging_root: Path | None = None,
    variant: str | None = None,
) -> Path:
    ep_id = row["id"]
    num = row.get("episode_number")
    out = resolve_draft_path(
        row, staging_root=staging_root, variant=variant, out_path=out_path
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    rel_prompt = path_relative_to_root(prompt_path)
    fm = write_expanded_draft_md(
        row,
        model=model,
        prompt_path=rel_prompt,
        prompt_hash=prompt_file_hash(prompt_path),
        tune_variant=variant,
    )
    write_frontmatter_md(out, frontmatter=fm, body=expanded_body)
    return out


def promote_draft(
    row: dict[str, Any],
    *,
    dry_run: bool,
    draft_path: Path | None = None,
) -> tuple[Path | None, list[str], list[str]]:
    """
    Validate draft, write {folder}.expanded.md, delete draft on success.
    Returns (expanded_path or None if dry_run, errors, warnings).
    """
    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    if draft_path is None:
        draft_path = expanded_draft_file_path(ep_id, slug, num)
    expanded_path = expanded_file_path(ep_id, slug, num)
    npath = notes_file_path(ep_id, slug, num)

    if not draft_path.exists():
        return None, [f"no draft: {draft_path.relative_to(paths.ROOT)}"], []

    body = read_markdown_body(draft_path)
    errors, warnings = validate_expanded_draft(npath, body)
    if errors:
        return None, errors, warnings

    if dry_run:
        return expanded_path, [], warnings

    full = draft_path.read_text(encoding="utf-8")
    draft_fm = parse_frontmatter(full)
    model_val = draft_fm.get("model", "")
    prompt_hash_val = draft_fm.get("prompt_hash", "")

    write_expanded_md(
        row,
        body,
        expanded_model=model_val or None,
        prompt_hash=prompt_hash_val or None,
    )
    draft_path.unlink()
    return expanded_path, [], warnings
