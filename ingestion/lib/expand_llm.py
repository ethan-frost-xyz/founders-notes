"""OpenRouter / datapoint expansion: prompts, API call, draft write, promote."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from markdown_io import (
    TIMESTAMP_BULLET_RE,
    read_markdown_body,
    utc_now_iso,
    write_frontmatter_md,
)
import paths
from paths import (
    INGESTION_DIR,
    expanded_draft_file_path,
    expanded_file_path,
    notes_file_path,
    staging_draft_file_path,
    transcript_dir,
    transcript_filename,
)

DEFAULT_PROMPT_PATH = INGESTION_DIR / "prompts" / "expand_datapoints.md"


def expand_run_log_path() -> Path:
    return paths.ROOT / "catalog" / "expand-run.jsonl"

MARKERS = ("<<<SYSTEM>>>", "<<<USER>>>")


def default_prompt_path() -> Path:
    return DEFAULT_PROMPT_PATH


def load_prompt_template(path: Path | None = None) -> tuple[str, str]:
    """Return (system_message, user_template with {notes} and {transcript} placeholders)."""
    p = path or default_prompt_path()
    if not p.exists():
        raise FileNotFoundError(f"Prompt file missing: {p.relative_to(paths.ROOT)}")
    text = p.read_text(encoding="utf-8")
    if MARKERS[0] not in text or MARKERS[1] not in text:
        raise ValueError(
            f"Prompt {p} must contain {MARKERS[0]} and {MARKERS[1]} delimiters"
        )
    _, rest = text.split(MARKERS[0], 1)
    system_part, user_part = rest.split(MARKERS[1], 1)
    return system_part.strip(), user_part.strip()


def build_user_message(user_template: str, *, notes: str, transcript: str) -> str:
    return user_template.format(notes=notes, transcript=transcript)


CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class ExpandEstimate:
    episode_id: str
    n_bullets: int
    notes_chars: int
    transcript_chars: int
    input_chars: int

    @property
    def approx_input_tokens(self) -> int:
        return (self.input_chars + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def format_compact_chars(n: int) -> str:
    """Human-readable char count (e.g. 54k, 1.2M)."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.0f}k"
    return f"{n / 1_000_000:.2f}M"


def format_compact_tokens(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


def input_usd_per_mtok_from_env() -> float | None:
    raw = os.environ.get("OPENROUTER_ESTIMATE_INPUT_USD_PER_MTOK", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def estimate_expand_for_row(row: dict[str, Any], *, prompt_path: Path) -> ExpandEstimate:
    """Approximate OpenRouter input size for one expand call (no API)."""
    system, user_template = load_prompt_template(prompt_path)
    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    npath = notes_file_path(ep_id, slug, num)
    tx_path = transcript_dir(ep_id, slug, num) / transcript_filename(ep_id, slug, num)
    if not npath.exists():
        raise FileNotFoundError(f"Missing notes: {npath.relative_to(paths.ROOT)}")
    if not tx_path.exists():
        raise FileNotFoundError(f"Missing transcript: {tx_path.relative_to(paths.ROOT)}")
    notes_body = read_markdown_body(npath)
    transcript_body = read_markdown_body(tx_path)
    user_msg = build_user_message(
        user_template, notes=notes_body, transcript=transcript_body
    )
    n_bullets = len(TIMESTAMP_BULLET_RE.findall(notes_body))
    return ExpandEstimate(
        episode_id=ep_id,
        n_bullets=n_bullets,
        notes_chars=len(notes_body),
        transcript_chars=len(transcript_body),
        input_chars=len(system) + len(user_msg),
    )


def _prompt_display_path(prompt_path: Path) -> str:
    try:
        return str(prompt_path.relative_to(paths.ROOT))
    except ValueError:
        return str(prompt_path)


def print_expand_dry_run_summary(
    estimates: list[ExpandEstimate],
    *,
    title: str,
    prompt_path: Path,
    model: str,
    extra_footer_lines: list[str] | None = None,
) -> None:
    """Print a table of per-episode input size and roll-up totals."""
    if not estimates:
        print("No episodes to estimate")
        return

    print(title)
    print(f"  prompt: {_prompt_display_path(prompt_path)}")
    print(f"  model:  {model}")
    print()
    print(f"  {'episode':<10} {'bl':>3} {'notes':>6} {'tx':>6} {'input':>8} {'~tokens':>8}")
    print(f"  {'-' * 10} {'-' * 3} {'-' * 6} {'-' * 6} {'-' * 8} {'-' * 8}")

    total_bullets = 0
    total_input = 0
    for est in estimates:
        total_bullets += est.n_bullets
        total_input += est.input_chars
        print(
            f"  {est.episode_id:<10} {est.n_bullets:>3} "
            f"{format_compact_chars(est.notes_chars):>6} "
            f"{format_compact_chars(est.transcript_chars):>6} "
            f"{format_compact_chars(est.input_chars):>8} "
            f"{format_compact_tokens(est.approx_input_tokens):>8}"
        )

    total_tokens = (total_input + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN
    n_calls = len(estimates)
    print(f"  {'-' * 10} {'-' * 3} {'-' * 6} {'-' * 6} {'-' * 8} {'-' * 8}")
    print(
        f"  {'TOTAL':<10} {total_bullets:>3} {'':>6} {'':>6} "
        f"{format_compact_chars(total_input):>8} "
        f"{format_compact_tokens(total_tokens):>8}"
    )
    print()
    print(f"  API calls this pass: {n_calls}")
    print(
        f"  ~input tokens (sum): {total_tokens:,}  (chars÷{CHARS_PER_TOKEN} heuristic)"
    )

    rate = input_usd_per_mtok_from_env()
    if rate is not None:
        usd = total_tokens * rate / 1_000_000
        print(f"  ~input cost: ${usd:.2f}  (@ ${rate}/M tok from OPENROUTER_ESTIMATE_INPUT_USD_PER_MTOK)")
    else:
        print(
            "  ~input cost: (set OPENROUTER_ESTIMATE_INPUT_USD_PER_MTOK in .env for $ estimate)"
        )

    if extra_footer_lines:
        print()
        for line in extra_footer_lines:
            print(f"  {line}")


def build_combined_prompt_for_clipboard(system: str, user_message: str) -> str:
    """Single document for manual paste (Cursor / Gemini)."""
    return f"{system}\n\n---\n\n{user_message}"


_FENCE_RE = re.compile(
    r"^\s*```(?:markdown|md)?\s*\r?\n(.*?)\r?\n```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def parse_expanded_body(raw: str) -> str:
    """Strip optional markdown fence and preamble; return body starting at ## Expanded datapoints."""
    text = raw.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    marker = "## Expanded datapoints"
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f"Model output missing {marker!r}")
    return text[idx:].strip()


def _count_datapoint_headings(body: str) -> int:
    return len(re.findall(r"^###\s+.+$", body, re.MULTILINE))


def _block_has_field(block: str, labels: tuple[str, ...]) -> bool:
    """True if block contains any label (plain or **Label:** markdown)."""
    lower = block.lower()
    for label in labels:
        if label.lower() in lower:
            return True
        bold = f"**{label}**"
        if bold.lower() in lower:
            return True
    return False


def validate_expanded_draft(
    notes_path: Path,
    expanded_body: str,
) -> tuple[list[str], list[str]]:
    """
    Return (errors, warnings). Errors block promotion; warnings are advisory.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if "## Expanded datapoints" not in expanded_body:
        errors.append("missing ## Expanded datapoints section")
        return errors, warnings

    n_sections = _count_datapoint_headings(expanded_body)
    if n_sections == 0:
        errors.append("no ### datapoint headings found")

    notes_body = read_markdown_body(notes_path)
    n_bullets = len(TIMESTAMP_BULLET_RE.findall(notes_body))
    if n_bullets > 0 and n_sections < n_bullets:
        errors.append(
            f"fewer expanded sections ({n_sections}) than note bullets ({n_bullets})"
        )
    if n_sections > n_bullets and n_bullets > 0:
        warnings.append(
            f"more ### sections ({n_sections}) than note bullets ({n_bullets})"
        )

    # Each ### block should have Context, Quote, and takeaway (soft check)
    for i, block in enumerate(re.split(r"^###\s+", expanded_body, flags=re.MULTILINE)):
        if i == 0:
            continue  # preamble before first ###
        if not _block_has_field(block, ("Context:",)):
            warnings.append(f"block after heading #{i} may be missing Context:")
        if not _block_has_field(block, ("Quote:",)):
            warnings.append(f"block after heading #{i} may be missing Quote:")
        if not _block_has_field(
            block, ("Key takeaway:", "Takeaway:")
        ):
            warnings.append(
                f"block after heading #{i} may be missing Key takeaway: or Takeaway:"
            )

    return errors, warnings


def _parse_simple_frontmatter(text: str) -> dict[str, str]:
    """Best-effort key: value from first YAML frontmatter block."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def prompt_file_hash(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes())
    return h.hexdigest()[:16]


def call_openrouter(
    *,
    system: str,
    user: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.0,
    response_format: dict[str, str] | None = None,
) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=(base_url or "https://openrouter.ai/api/v1").rstrip("/"),
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content
    if not raw:
        raise ValueError("empty model response")
    return raw


def append_expand_run_log(record: dict[str, Any]) -> None:
    log_path = expand_run_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


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
    try:
        rel_prompt = str(prompt_path.relative_to(paths.ROOT))
    except ValueError:
        rel_prompt = str(prompt_path)
    fm: dict[str, Any] = {
        "id": ep_id,
        "title": row["title"],
        "source": "expand_llm",
        "model": model,
        "generated_at": utc_now_iso(),
        "prompt_path": rel_prompt,
        "prompt_hash": prompt_file_hash(prompt_path),
    }
    if num is not None:
        fm["episode_number"] = num
    if variant is not None:
        fm["tune_variant"] = variant
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
    draft_fm = _parse_simple_frontmatter(full)
    model_val = draft_fm.get("model", "")

    fm: dict[str, Any] = {
        "id": ep_id,
        "title": row["title"],
        "source": "expand_llm",
        "expanded_at": utc_now_iso(),
    }
    if num is not None:
        fm["episode_number"] = num
    if model_val:
        fm["expanded_model"] = model_val

    write_frontmatter_md(expanded_path, frontmatter=fm, body=body)
    draft_path.unlink()
    return expanded_path, [], warnings
