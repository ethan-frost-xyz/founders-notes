"""Vault filesystem paths and folder naming."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

INGESTION_DIR = Path(__file__).resolve().parent.parent
ROOT = INGESTION_DIR.parent
CATALOG_PATH = ROOT / "catalog" / "episodes.jsonl"
GAPS_PATH = ROOT / "catalog" / "gaps.md"
UNMAPPED_POSTS_PATH = ROOT / "catalog" / "unmapped-posts.jsonl"
IMPORT_REVIEW_PATH = ROOT / "catalog" / "import-review.md"
TRANSCRIPTS_DIR = ROOT / "content" / "transcripts"
NOTES_DIR = ROOT / "content" / "notes"
POSTS_DIR = ROOT / "content" / "posts"
POSTS_CORPUS_PATH = POSTS_DIR / "_corpus" / "all-posts.md"
CHUNKS_PATH = ROOT / "catalog" / "chunks.jsonl"
EPISODE_SUMMARIES_PATH = ROOT / "catalog" / "episode-summaries.jsonl"
EMBEDDINGS_PATH = ROOT / "catalog" / "embeddings.npy"
EMBEDDINGS_MANIFEST_PATH = ROOT / "catalog" / "embeddings-manifest.jsonl"
EMBEDDINGS_META_PATH = ROOT / "catalog" / "embeddings-meta.json"
TELEGRAM_SESSIONS_DIR = ROOT / "catalog" / "telegram-sessions"

CONTENT_TYPES = frozenset({"transcript", "notes", "expanded", "post"})


@dataclass(frozen=True)
class CatalogPaths:
    root: Path
    episodes: Path
    chunks: Path
    embeddings: Path
    embeddings_manifest: Path
    episode_summaries: Path
    telegram_sessions: Path


def catalog_paths(vault_root: Path | None = None) -> CatalogPaths:
    """Resolve catalog index paths for the vault root (or module ROOT when None)."""
    root = (vault_root or ROOT).resolve()
    if root == ROOT.resolve():
        return CatalogPaths(
            root=ROOT,
            episodes=CATALOG_PATH,
            chunks=CHUNKS_PATH,
            embeddings=EMBEDDINGS_PATH,
            embeddings_manifest=EMBEDDINGS_MANIFEST_PATH,
            episode_summaries=EPISODE_SUMMARIES_PATH,
            telegram_sessions=TELEGRAM_SESSIONS_DIR,
        )
    catalog = root / "catalog"
    return CatalogPaths(
        root=root,
        episodes=catalog / "episodes.jsonl",
        chunks=catalog / "chunks.jsonl",
        embeddings=catalog / "embeddings.npy",
        embeddings_manifest=catalog / "embeddings-manifest.jsonl",
        episode_summaries=catalog / "episode-summaries.jsonl",
        telegram_sessions=catalog / "telegram-sessions",
    )


def path_relative_to_root(path: Path) -> str:
    """Return vault-root-relative path string, or absolute if outside ROOT."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def staging_draft_file_path(
    staging_root: Path,
    variant: str,
    episode_id: str,
    slug: str,
    episode_number: int | None = None,
) -> Path:
    """Sandbox draft for prompt A/B tuning (under ingestion/fixtures/expand-runs/)."""
    folder = _episode_folder(episode_id, slug, episode_number)
    return staging_root / variant / folder / f"{folder}.expanded.draft.md"


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
