"""Datapoint expansion: prompts, cost estimates, progress UI; re-exports split modules."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Any

from expand_promote import (
    promote_draft,
    prompt_file_hash,
    resolve_draft_path,
    write_expanded_draft,
)
from expand_run_log import (
    append_expand_run_log,
    expand_log_context_from_env,
    expand_run_log_path,
    filter_expand_run_log,
    format_compact_chars,
    format_compact_tokens,
    format_cost_usd,
    format_duration_sec,
    format_expand_usage_suffix,
    load_expand_run_log,
    log_expand_event,
    openrouter_completion_log_fields,
    print_expand_batch_summary,
    print_expand_error_line,
    print_expand_ok_line,
)
from expand_validate import (
    count_datapoint_headings,
    count_datapoint_headings_in_partial,
    parse_expanded_body,
    validate_expanded_draft,
)
from markdown_io import TIMESTAMP_BULLET_RE, read_markdown_body
from openrouter_client import (
    OPENROUTER_MAX_ATTEMPTS,
    ExpandProgressReporter,
    OpenRouterCompletion,
    call_openrouter,
    call_openrouter_streaming,
    execute_openrouter_with_retry,
    is_retriable_openrouter_error,
    usage_from_response,
)
from openrouter_pricing import (
    COMPLETION_TOKENS_PER_BULLET,
    estimate_cost_usd,
    format_usd_per_million,
    model_id_for_pricing,
    resolve_model_rates,
)
import paths
from paths import (
    INGESTION_DIR,
    notes_file_path,
    transcript_dir,
    transcript_filename,
)

# Backward compatibility for callers using the private name.
_count_datapoint_headings = count_datapoint_headings

DEFAULT_PROMPT_PATH = INGESTION_DIR / "prompts" / "expand_datapoints.md"

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


def _prompt_display_path(prompt_path: Path) -> str:
    try:
        return str(prompt_path.relative_to(paths.ROOT))
    except ValueError:
        return str(prompt_path)


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

    pricing_model = model_id_for_pricing(model)
    if pricing_model is None:
        print("  cost: (set OPENROUTER_MODEL or pass --model for $ estimate)")
    else:
        try:
            rates = resolve_model_rates(pricing_model, input_tokens=total_tokens)
            costs = estimate_cost_usd(
                rates,
                input_tokens=total_tokens,
                n_calls=n_calls,
                total_bullets=total_bullets,
            )
            print(
                f"  rates: {format_usd_per_million(rates.prompt_usd_per_token)} input, "
                f"{format_usd_per_million(rates.completion_usd_per_token)} output  "
                f"({rates.model_id}, OpenRouter catalog)"
            )
            print(f"  ~input cost: ${costs.input_usd:.2f}")
            if costs.request_usd > 0:
                print(f"  ~request fees: ${costs.request_usd:.2f}")
            print(
                f"  ~output cost (est.): ${costs.output_usd:.2f}  "
                f"(~{COMPLETION_TOKENS_PER_BULLET} tok/bullet)"
            )
            print(f"  ~total (est.): ${costs.total_usd:.2f}")
        except Exception as e:
            print(f"  cost: could not load OpenRouter pricing: {e}")

    if extra_footer_lines:
        print()
        for line in extra_footer_lines:
            print(f"  {line}")


def build_combined_prompt_for_clipboard(system: str, user_message: str) -> str:
    """Single document for manual paste (Cursor / Gemini)."""
    return f"{system}\n\n---\n\n{user_message}"


class TerminalExpandProgressReporter:
    """Print expand progress lines to stdout (flush after each)."""

    def __init__(self, *, episode_id: str, total_sections: int) -> None:
        self.episode_id = episode_id
        self.total_sections = max(total_sections, 0)

    def waiting(self, *, input_chars: int) -> None:
        print(
            f"[expand] {self.episode_id}  waiting for API…  "
            f"(~{format_compact_chars(input_chars)} chars in)",
            flush=True,
        )

    def first_token(self, *, ttft_ms: int) -> None:
        print(
            f"[expand] {self.episode_id}  first output ({format_duration_sec(ttft_ms)})",
            flush=True,
        )

    def section(self, *, index: int, total: int) -> None:
        denom = total if total > 0 else self.total_sections or "?"
        print(
            f"[expand] {self.episode_id}  datapoint {index}/{denom}",
            flush=True,
        )


__all__ = [
    "CHARS_PER_TOKEN",
    "COMPLETION_TOKENS_PER_BULLET",
    "DEFAULT_PROMPT_PATH",
    "ExpandEstimate",
    "ExpandProgressReporter",
    "MARKERS",
    "OPENROUTER_MAX_ATTEMPTS",
    "OpenRouterCompletion",
    "TerminalExpandProgressReporter",
    "_count_datapoint_headings",
    "append_expand_run_log",
    "build_combined_prompt_for_clipboard",
    "build_user_message",
    "call_openrouter",
    "call_openrouter_streaming",
    "count_datapoint_headings",
    "count_datapoint_headings_in_partial",
    "default_prompt_path",
    "estimate_expand_for_row",
    "execute_openrouter_with_retry",
    "expand_log_context_from_env",
    "expand_run_log_path",
    "filter_expand_run_log",
    "format_compact_chars",
    "format_compact_tokens",
    "format_cost_usd",
    "format_duration_sec",
    "format_expand_usage_suffix",
    "is_retriable_openrouter_error",
    "load_expand_run_log",
    "load_prompt_template",
    "log_expand_event",
    "model_id_for_pricing",
    "openrouter_completion_log_fields",
    "parse_expanded_body",
    "print_expand_batch_summary",
    "print_expand_dry_run_summary",
    "print_expand_error_line",
    "print_expand_ok_line",
    "promote_draft",
    "prompt_file_hash",
    "resolve_draft_path",
    "resolve_model_rates",
    "validate_expanded_draft",
    "usage_from_response",
    "write_expanded_draft",
]
