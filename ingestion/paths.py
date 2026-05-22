"""Vault filesystem paths and folder naming."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog" / "episodes.jsonl"
GAPS_PATH = ROOT / "catalog" / "gaps.md"
UNMAPPED_POSTS_PATH = ROOT / "catalog" / "unmapped-posts.jsonl"
IMPORT_REVIEW_PATH = ROOT / "catalog" / "import-review.md"
TRANSCRIPTS_DIR = ROOT / "content" / "transcripts"
NOTES_DIR = ROOT / "content" / "notes"
POSTS_DIR = ROOT / "content" / "posts"
POSTS_CORPUS_PATH = POSTS_DIR / "_corpus" / "all-posts.md"
CHUNKS_PATH = ROOT / "catalog" / "chunks.jsonl"

CONTENT_TYPES = frozenset({"transcript", "notes", "expanded", "post"})


def folder_name(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> str:
    """e.g. ep-0418 + 418-phil-knight -> ep-0418-phil-knight-founder-of-nike"""
    if episode_number is not None and slug.startswith(f"{episode_number}-"):
        return f"{episode_id}-{slug[len(str(episode_number)) + 1:]}"
    return f"{episode_id}-{slug}"


def content_filename(folder: str, content_type: str) -> str:
    if content_type not in CONTENT_TYPES:
        raise ValueError(f"content_type must be one of {sorted(CONTENT_TYPES)}")
    return f"{folder}.{content_type}.md"


def _episode_folder(episode_id: str, slug: str, episode_number: int | None = None) -> str:
    return folder_name(episode_id, slug, episode_number)


def transcript_dir(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> Path:
    return TRANSCRIPTS_DIR / _episode_folder(episode_id, slug, episode_number)


def transcript_filename(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> str:
    folder = _episode_folder(episode_id, slug, episode_number)
    return content_filename(folder, "transcript")


def transcript_path(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> str:
    rel = transcript_dir(episode_id, slug, episode_number) / transcript_filename(
        episode_id, slug, episode_number
    )
    return str(rel.relative_to(ROOT))


def episode_content_dir(
    episode_id: str,
    slug: str,
    base: Path,
    episode_number: int | None = None,
) -> Path:
    return base / _episode_folder(episode_id, slug, episode_number)


def notes_dir(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> Path:
    return episode_content_dir(episode_id, slug, NOTES_DIR, episode_number)


def notes_file_path(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> Path:
    folder = _episode_folder(episode_id, slug, episode_number)
    return notes_dir(episode_id, slug, episode_number) / content_filename(folder, "notes")


def expanded_file_path(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> Path:
    folder = _episode_folder(episode_id, slug, episode_number)
    return notes_dir(episode_id, slug, episode_number) / content_filename(folder, "expanded")


def expanded_draft_file_path(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> Path:
    """LLM staging file; not indexed as chunks until promoted to .expanded.md."""
    folder = _episode_folder(episode_id, slug, episode_number)
    return notes_dir(episode_id, slug, episode_number) / f"{folder}.expanded.draft.md"


def post_dir(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> Path:
    return episode_content_dir(episode_id, slug, POSTS_DIR, episode_number)


def post_file_path(
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> Path:
    folder = _episode_folder(episode_id, slug, episode_number)
    return post_dir(episode_id, slug, episode_number) / content_filename(folder, "post")
