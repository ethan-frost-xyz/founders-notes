"""OpenRouter / datapoint expansion: prompts, API call, draft write, promote."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any

from expanded_timestamp_lint import lint_expanded_body
from markdown_io import (
    TIMESTAMP_BULLET_RE,
    parse_frontmatter,
    read_markdown_body,
    utc_now_iso,
    write_expanded_draft_md,
    write_expanded_md,
    write_frontmatter_md,
)
import paths
from openrouter_pricing import (
    COMPLETION_TOKENS_PER_BULLET,
    estimate_cost_usd,
    format_usd_per_million,
    model_id_for_pricing,
    resolve_model_rates,
)
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

OPENROUTER_MAX_ATTEMPTS = 3


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


def count_datapoint_headings_in_partial(text: str) -> int:
    """Count completed `###` datapoint headings in a partial stream buffer."""
    return _count_datapoint_headings(text)


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

    for msg in lint_expanded_body(expanded_body):
        warnings.append(f"timestamp meta: {msg}")

    return errors, warnings


def prompt_file_hash(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes())
    return h.hexdigest()[:16]


@dataclass(frozen=True)
class OpenRouterCompletion:
    content: str
    response_id: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    duration_ms: int


def usage_from_response(response: Any) -> dict[str, Any]:
    """Normalize OpenRouter/OpenAI usage fields from a chat completion response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": None,
        }
    prompt_tokens = int(getattr(usage, "prompt_tokens", None) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", None) or 0)
    total_tokens = int(getattr(usage, "total_tokens", None) or 0)
    if total_tokens == 0 and (prompt_tokens or completion_tokens):
        total_tokens = prompt_tokens + completion_tokens
    cost_raw = getattr(usage, "cost", None)
    cost_usd: float | None
    if cost_raw is None:
        cost_usd = None
    else:
        try:
            cost_usd = float(cost_raw)
        except (TypeError, ValueError):
            cost_usd = None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
    }


def expand_log_context_from_env() -> dict[str, str]:
    """Optional tune correlation (set by expand_tune subprocess env)."""
    out: dict[str, str] = {}
    run_id = os.environ.get("EXPAND_RUN_ID", "").strip()
    variant = os.environ.get("EXPAND_VARIANT", "").strip()
    if run_id:
        out["run_id"] = run_id
    if variant:
        out["variant"] = variant
    return out


class ExpandProgressReporter:
    """Optional live progress callbacks during a streaming expand call."""

    def waiting(self, *, input_chars: int) -> None:
        pass

    def first_token(self, *, ttft_ms: int) -> None:
        pass

    def section(self, *, index: int, total: int) -> None:
        pass


class TerminalExpandProgressReporter(ExpandProgressReporter):
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


def _openrouter_retry_delay_sec(failed_attempt: int) -> float:
    """Seconds to wait after failed attempt N (1-based) before the next try."""
    return min(2.0 ** (failed_attempt - 1), 30.0)


def is_retriable_openrouter_error(exc: Exception) -> bool:
    """True for transient API/network failures worth retrying."""
    if isinstance(exc, ValueError) and "empty model response" in str(exc).lower():
        return True
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        )
    except ImportError:
        return False
    if isinstance(
        exc,
        (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError),
    ):
        return True
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", None)
        if code is None:
            return False
        return int(code) in (408, 429, 500, 502, 503, 504)
    return False


def execute_openrouter_with_retry(
    operation: Callable[[], OpenRouterCompletion],
    *,
    max_attempts: int = OPENROUTER_MAX_ATTEMPTS,
    episode_id: str | None = None,
) -> OpenRouterCompletion:
    """Run an OpenRouter call up to max_attempts times on retriable errors."""
    prefix = f"[expand] {episode_id}  " if episode_id else "[expand] "
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as e:
            last_exc = e
            if attempt >= max_attempts or not is_retriable_openrouter_error(e):
                raise
            delay = _openrouter_retry_delay_sec(attempt)
            print(
                f"{prefix}API attempt {attempt}/{max_attempts} failed "
                f"({type(e).__name__}: {e}); retrying in {delay:.0f}s…",
                flush=True,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def call_openrouter(
    *,
    system: str,
    user: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.0,
    response_format: dict[str, str] | None = None,
    episode_id: str | None = None,
) -> OpenRouterCompletion:
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
    def _once() -> OpenRouterCompletion:
        t0 = time.perf_counter()
        response = client.chat.completions.create(**kwargs)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        raw = response.choices[0].message.content
        if not raw:
            raise ValueError("empty model response")
        usage = usage_from_response(response)
        return OpenRouterCompletion(
            content=raw,
            response_id=getattr(response, "id", None),
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=usage["cost_usd"],
            duration_ms=duration_ms,
        )

    return execute_openrouter_with_retry(_once, episode_id=episode_id)


def call_openrouter_streaming(
    *,
    system: str,
    user: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.0,
    total_sections: int = 0,
    reporter: ExpandProgressReporter | None = None,
    episode_id: str | None = None,
) -> OpenRouterCompletion:
    """Stream chat completion; optional reporter for TTFT and per-section progress."""
    from openai import OpenAI

    if reporter is not None:
        reporter.waiting(input_chars=len(system) + len(user))

    client = OpenAI(
        api_key=api_key,
        base_url=(base_url or "https://openrouter.ai/api/v1").rstrip("/"),
    )
    def _once() -> OpenRouterCompletion:
        t0 = time.perf_counter()
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            stream=True,
            stream_options={"include_usage": True},
        )

        parts: list[str] = []
        response_id: str | None = None
        usage_chunk: Any = None
        first_token_reported = False
        last_section_count = 0
        section_total = max(total_sections, 0)

        for chunk in stream:
            chunk_id = getattr(chunk, "id", None)
            if chunk_id:
                response_id = chunk_id
            if getattr(chunk, "usage", None) is not None:
                usage_chunk = chunk

            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if not delta:
                continue

            if not first_token_reported:
                if reporter is not None:
                    reporter.first_token(ttft_ms=int((time.perf_counter() - t0) * 1000))
                first_token_reported = True

            parts.append(delta)
            buffer = "".join(parts)
            n_sections = count_datapoint_headings_in_partial(buffer)
            if reporter is not None and n_sections > last_section_count:
                for idx in range(last_section_count + 1, n_sections + 1):
                    reporter.section(
                        index=idx,
                        total=section_total if section_total > 0 else n_sections,
                    )
                last_section_count = n_sections

        duration_ms = int((time.perf_counter() - t0) * 1000)
        raw = "".join(parts)
        if not raw:
            raise ValueError("empty model response")

        usage = (
            usage_from_response(usage_chunk)
            if usage_chunk is not None
            else usage_from_response(None)
        )
        return OpenRouterCompletion(
            content=raw,
            response_id=response_id,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=usage["cost_usd"],
            duration_ms=duration_ms,
        )

    return execute_openrouter_with_retry(_once, episode_id=episode_id)


def append_expand_run_log(record: dict[str, Any]) -> None:
    log_path = expand_run_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_expand_event(record: dict[str, Any]) -> dict[str, Any]:
    """Append one expand-run.jsonl row (merges tune env context)."""
    merged = {**expand_log_context_from_env(), **record}
    append_expand_run_log(merged)
    return merged


def load_expand_run_log() -> list[dict[str, Any]]:
    path = expand_run_log_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def filter_expand_run_log(
    records: list[dict[str, Any]],
    *,
    run_id: str | None = None,
    variant: str | None = None,
    last: int | None = None,
) -> list[dict[str, Any]]:
    out = records
    if run_id:
        out = [r for r in out if r.get("run_id") == run_id]
    if variant:
        out = [r for r in out if r.get("variant") == variant]
    if last is not None and last > 0:
        out = out[-last:]
    return out


def format_duration_sec(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "?"
    return f"{duration_ms / 1000:.1f}s"


def format_cost_usd(cost: float | None) -> str:
    if cost is None:
        return "?"
    if cost >= 0.01:
        return f"${cost:.2f}"
    if cost > 0:
        return f"${cost:.4f}"
    return "$0"


def openrouter_completion_log_fields(
    completion: OpenRouterCompletion | None,
) -> dict[str, Any]:
    """Token/cost fields for expand-run.jsonl when a completion exists."""
    if completion is None:
        return {}
    return {
        "response_id": completion.response_id,
        "prompt_tokens": completion.prompt_tokens,
        "completion_tokens": completion.completion_tokens,
        "total_tokens": completion.total_tokens,
        "cost_usd": completion.cost_usd,
        "duration_ms": completion.duration_ms,
    }


def format_expand_usage_suffix(completion: OpenRouterCompletion) -> str:
    return (
        f"{format_compact_tokens(completion.prompt_tokens)} in / "
        f"{format_compact_tokens(completion.completion_tokens)} out  "
        f"{format_cost_usd(completion.cost_usd)}  "
        f"{format_duration_sec(completion.duration_ms)}"
    )


def print_expand_ok_line(
    *,
    episode_id: str,
    completion: OpenRouterCompletion,
    draft_rel: str,
) -> None:
    print(
        f"[ok] {episode_id}  "
        f"{format_expand_usage_suffix(completion)}  "
        f"→ {draft_rel}"
    )


def print_expand_error_line(
    *,
    episode_id: str,
    error: str,
    completion: OpenRouterCompletion | None = None,
) -> None:
    print(f"[error] {episode_id}: {error}")
    if completion is not None:
        print(f"         {format_expand_usage_suffix(completion)}")


def print_expand_batch_summary(
    records: list[dict[str, Any]],
    *,
    title: str | None = None,
) -> None:
    if not records:
        return
    if title:
        print()
        print(title)
    counts: dict[str, int] = {}
    prompt_tok = 0
    completion_tok = 0
    cost_sum = 0.0
    cost_known = 0
    for r in records:
        status = r.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
        if status == "ok":
            prompt_tok += int(r.get("prompt_tokens") or 0)
            completion_tok += int(r.get("completion_tokens") or 0)
            c = r.get("cost_usd")
            if c is not None:
                cost_sum += float(c)
                cost_known += 1
    print(
        f"  ok: {counts.get('ok', 0)}  "
        f"skipped: {counts.get('skipped', 0)}  "
        f"error: {counts.get('error', 0)}"
    )
    if prompt_tok or completion_tok:
        print(
            f"  tokens: {prompt_tok:,} in / {completion_tok:,} out"
        )
    if cost_known:
        print(f"  cost: ${cost_sum:.4f} ({cost_known} call(s) with usage.cost)")
    print(f"  log: {expand_run_log_path().relative_to(paths.ROOT)}")


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
