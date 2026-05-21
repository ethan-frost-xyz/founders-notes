#!/usr/bin/env python3
"""One-shot migration: zero-pad episode ids and unify per-episode filenames."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from vault_lib import (
    NOTES_DIR,
    POSTS_DIR,
    ROOT,
    TRANSCRIPTS_DIR,
    content_filename,
    folder_name,
    format_episode_id,
    legacy_make_id,
    load_catalog,
    save_catalog,
    transcript_path,
)

CATALOG_PATH = ROOT / "catalog" / "episodes.jsonl"
POST_MAPPING_REVIEW = ROOT / "catalog" / "post-mapping-review.jsonl"

CONTENT_BASES: tuple[tuple[Path, str], ...] = (
    (TRANSCRIPTS_DIR, "transcript"),
    (NOTES_DIR, "notes"),
    (NOTES_DIR, "expanded"),
    (POSTS_DIR, "post"),
)
UNIQUE_CONTENT_DIRS = (TRANSCRIPTS_DIR, NOTES_DIR, POSTS_DIR)

ID_FRONTMATTER_RE = re.compile(
    r'^(id:\s*)(?:"|\')?(ep-\d+)(?:"|\')?\s*$',
    re.MULTILINE,
)


def legacy_folder_name(episode_number: int, slug: str) -> str:
    old_id = legacy_make_id(episode_number)
    if slug.startswith(f"{episode_number}-"):
        return f"{old_id}-{slug[len(str(episode_number)) + 1:]}"
    return f"{old_id}-{slug}"


@dataclass
class EpisodeMigration:
    episode_number: int
    slug: str
    old_id: str
    new_id: str
    old_folder: str
    new_folder: str
    dir_renames: list[tuple[Path, Path]] = field(default_factory=list)
    file_renames: list[tuple[Path, Path]] = field(default_factory=list)
    files_to_patch: list[Path] = field(default_factory=list)


def legacy_transcript_candidates(old_folder: str) -> list[str]:
    return [
        f"{old_folder}.md",
        "transcript.md",
    ]


def legacy_content_filename(old_folder: str, content_type: str) -> str | None:
    if content_type == "transcript":
        return None
    if content_type == "notes":
        return "notes.md"
    if content_type == "expanded":
        return "expanded.md"
    if content_type == "post":
        return "post.md"
    return None


def collect_episode_migration(row: dict[str, Any]) -> EpisodeMigration | None:
    num = row.get("episode_number")
    if num is None:
        return None

    slug = row["slug"]
    old_id = legacy_make_id(num)
    new_id = format_episode_id(num)
    old_folder = legacy_folder_name(num, slug)
    new_folder = folder_name(new_id, slug, num)

    mig = EpisodeMigration(
        episode_number=num,
        slug=slug,
        old_id=old_id,
        new_id=new_id,
        old_folder=old_folder,
        new_folder=new_folder,
    )

    if old_folder != new_folder:
        for base in UNIQUE_CONTENT_DIRS:
            old_dir = base / old_folder
            new_dir = base / new_folder
            if old_dir.is_dir():
                mig.dir_renames.append((old_dir, new_dir))

    for base, content_type in CONTENT_BASES:
        old_dir = base / old_folder
        new_dir = base / new_folder
        work_dir = old_dir if old_dir.is_dir() else (new_dir if new_dir.is_dir() else None)
        if work_dir is None:
            continue

        new_name = content_filename(new_folder, content_type)
        new_path = work_dir / new_name
        if new_path.exists():
            mig.files_to_patch.append(new_path)
            continue

        if content_type == "transcript":
            for old_name in legacy_transcript_candidates(old_folder):
                old_path = work_dir / old_name
                if old_path.is_file():
                    mig.file_renames.append((old_path, new_path))
                    mig.files_to_patch.append(new_path)
                    break
        else:
            old_name = legacy_content_filename(old_folder, content_type)
            if old_name:
                old_path = work_dir / old_name
                if old_path.is_file():
                    mig.file_renames.append((old_path, new_path))
                    mig.files_to_patch.append(new_path)

    return mig


def patch_frontmatter_id(path: Path, new_id: str) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        return
    fm = parts[1]

    def repl(m: re.Match[str]) -> str:
        return f'{m.group(1)}"{new_id}"'

    new_fm = ID_FRONTMATTER_RE.sub(repl, fm)
    if new_fm == fm:
        new_fm = re.sub(
            r"^(id:\s*)ep-\d+\s*$",
            f'id: "{new_id}"',
            fm,
            count=1,
            flags=re.MULTILINE,
        )
    path.write_text(f"---{new_fm}---{parts[2]}", encoding="utf-8")


def check_conflicts(migrations: list[EpisodeMigration]) -> list[str]:
    errors: list[str] = []
    dir_targets: set[Path] = set()
    file_targets: set[Path] = set()

    for mig in migrations:
        for _old, new in mig.dir_renames:
            if new in dir_targets:
                continue
            if new.exists():
                errors.append(f"target dir exists: {new.relative_to(ROOT)}")
            dir_targets.add(new)
        for _old, new in mig.file_renames:
            if new in file_targets or new.exists():
                errors.append(f"target file exists: {new.relative_to(ROOT)}")
            file_targets.add(new)

    return errors


def apply_migrations(migrations: list[EpisodeMigration]) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "migrated_at": date.today().isoformat(),
        "episodes": [],
    }

    for mig in migrations:
        ep_record: dict[str, Any] = {
            "episode_number": mig.episode_number,
            "old_id": mig.old_id,
            "new_id": mig.new_id,
            "old_folder": mig.old_folder,
            "new_folder": mig.new_folder,
            "dir_renames": [],
            "file_renames": [],
        }

        # Rename files before directories so collected paths remain valid.
        for old, new in mig.file_renames:
            if old.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                old.rename(new)
                ep_record["file_renames"].append(
                    [str(old.relative_to(ROOT)), str(new.relative_to(ROOT))]
                )

        for old, new in mig.dir_renames:
            if old.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                old.rename(new)
                ep_record["dir_renames"].append(
                    [str(old.relative_to(ROOT)), str(new.relative_to(ROOT))]
                )

        for path in mig.files_to_patch:
            if path.exists():
                patch_frontmatter_id(path, mig.new_id)

        manifest["episodes"].append(ep_record)

    return manifest


def repair_file_renames(rows: list[dict[str, Any]]) -> int:
    """Fix files left with legacy names inside already-renamed folders."""
    fixed = 0
    for row in rows:
        num = row.get("episode_number")
        if num is None:
            continue
        ep_id = row["id"]
        slug = row["slug"]
        new_folder = folder_name(ep_id, slug, num)
        old_folder = legacy_folder_name(num, slug)

        for base, content_type in CONTENT_BASES:
            dir_path = base / new_folder
            if not dir_path.is_dir():
                continue
            new_path = dir_path / content_filename(new_folder, content_type)
            if new_path.exists():
                patch_frontmatter_id(new_path, ep_id)
                continue

            candidates: list[Path] = []
            if content_type == "transcript":
                for name in legacy_transcript_candidates(old_folder):
                    candidates.append(dir_path / name)
            else:
                name = legacy_content_filename(old_folder, content_type)
                if name:
                    candidates.append(dir_path / name)

            for old_path in candidates:
                if old_path.is_file():
                    old_path.rename(new_path)
                    patch_frontmatter_id(new_path, ep_id)
                    fixed += 1
                    break

    return fixed


def update_catalog_rows(rows: list[dict[str, Any]]) -> int:
    updated = 0
    for row in rows:
        num = row.get("episode_number")
        if num is None:
            continue
        new_id = format_episode_id(num)
        if row["id"] != new_id:
            row["id"] = new_id
            updated += 1
        if row.get("transcript_status") == "complete":
            row["transcript_path"] = transcript_path(new_id, row["slug"], num)
    return updated


def update_post_mapping_review() -> int:
    if not POST_MAPPING_REVIEW.exists():
        return 0
    changed = 0
    lines_out: list[str] = []
    with POST_MAPPING_REVIEW.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            sug = rec.get("suggested_episode")
            num = rec.get("episode_number")
            if num is not None:
                new_sug = format_episode_id(num)
                if sug != new_sug:
                    rec["suggested_episode"] = new_sug
                    changed += 1
            lines_out.append(json.dumps(rec, ensure_ascii=False))
    POST_MAPPING_REVIEW.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate episode ids and filenames")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform migration (default is dry-run)",
    )
    parser.add_argument(
        "--repair-files",
        action="store_true",
        help="Rename legacy filenames inside already-migrated folders",
    )
    args = parser.parse_args()

    rows = load_catalog()

    if args.repair_files:
        fixed = repair_file_renames(rows)
        update_catalog_rows(rows)
        save_catalog(rows)
        print(f"Repaired {fixed} files")
        print("Next: python build_chunks.py && python verify.py")
        return
    migrations = [m for r in rows if (m := collect_episode_migration(r))]

    dir_count = sum(len(m.dir_renames) for m in migrations)
    file_count = sum(len(m.file_renames) for m in migrations)
    id_changes = sum(1 for m in migrations if m.old_id != m.new_id)

    print(f"Episodes to migrate: {len(migrations)}")
    print(f"Id changes: {id_changes}")
    print(f"Directory renames: {dir_count}")
    print(f"File renames: {file_count}")

    errors = check_conflicts(migrations)
    if errors:
        print("\nConflicts (aborting):")
        for err in errors[:20]:
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  … and {len(errors) - 20} more")
        raise SystemExit(1)

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to execute.")
        for mig in migrations[:5]:
            print(
                f"  ep {mig.episode_number}: {mig.old_id} -> {mig.new_id}, "
                f"{mig.old_folder} -> {mig.new_folder}"
            )
        if len(migrations) > 5:
            print(f"  … and {len(migrations) - 5} more")
        return

    manifest = apply_migrations(migrations)
    catalog_updates = update_catalog_rows(rows)
    save_catalog(rows)
    review_updates = update_post_mapping_review()

    manifest_path = ROOT / "catalog" / f"migration-layout-{date.today().isoformat()}.json"
    manifest["catalog_id_updates"] = catalog_updates
    manifest["post_mapping_review_updates"] = review_updates
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nApplied migration.")
    print(f"Catalog rows updated: {catalog_updates}")
    print(f"Post-mapping review updates: {review_updates}")
    print(f"Manifest: {manifest_path.relative_to(ROOT)}")
    print("\nNext:")
    print("  python build_chunks.py")
    print("  python verify.py")


if __name__ == "__main__":
    main()
