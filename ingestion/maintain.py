#!/usr/bin/env python3
"""Interactive console for vault notes, expansion, and search maintenance."""

from __future__ import annotations

import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parent
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

for _sub in ("notes", "search", "pipeline"):
    _p = _INGESTION / _sub
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

from dotenv import load_dotenv

from catalog import load_catalog
from cli_args import resolve_episode_id_arg
from expand_prompt import (
    ExpandEstimate,
    default_prompt_path,
    estimate_expand_for_row,
    filter_expand_run_log,
    load_expand_run_log,
    load_prompt_template,
    print_expand_batch_summary,
    print_expand_dry_run_summary,
    promote_draft,
    validate_expanded_draft,
)
from gaps_report import (
    compute_catalog_health,
    count_expanded_coverage,
    count_phase2_coverage,
    write_gaps_report,
)
from layout import scan_layout_violations
from markdown_io import has_timestamp_datapoints, read_markdown_body
import paths
from paths import GAPS_PATH, ROOT, expanded_draft_file_path, notes_file_path

load_dotenv(paths.ROOT / ".env")

DEFAULT_NOTES_FROM = 190

MENU = """
Founders Notes — maintenance console
------------------------------------
 1. Status / coverage (regenerate gaps.md)
 2. Next episode needing notes
 3. Expand one episode
 4. Expand backlog (--missing-expanded)
 5. Dry-run expansion cost
 6. List pending expanded drafts
 7. Promote drafts
 8. Rebuild search index (chunks + embeddings)
 9. Recent expand run log
 0. Quit
"""


@dataclass(frozen=True)
class CoverageStats:
    catalog_rows: int
    numbered: int
    transcripts_complete: int
    notes_files: int
    notes_with_datapoints: int
    bullets_missing_timestamp: int
    episodes_bullets_missing_timestamp: int
    posts: int
    expanded: int
    expanded_drafts: int
    missing_expanded_count: int
    unmapped_colossus: int
    blocking_transcript_gaps: int
    layout_errors: int


def prompt_line(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else default


def prompt_int(label: str, default: int | None = None) -> int | None:
    raw = prompt_line(label, str(default) if default is not None else "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Invalid number.")
        return default


def confirm_yes(message: str) -> bool:
    answer = input(f"{message} [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def load_rows() -> list[dict]:
    rows = load_catalog()
    if not rows:
        print("catalog/episodes.jsonl is empty — run pipeline/build_catalog.py")
    return rows


def refresh_coverage_report(rows: list[dict]) -> tuple[CoverageStats, list[str]]:
    """Regenerate gaps.md and return stats plus blocking verification messages."""
    health = compute_catalog_health(rows)

    (
        notes_files,
        notes_with_datapoints,
        posts_n,
        _,
        _,
        _,
        missing_timestamp_episodes,
    ) = count_phase2_coverage(rows)
    bullets_missing_timestamp = sum(c for _, c in missing_timestamp_episodes)
    expanded_n, expanded_drafts_n, missing_expanded = count_expanded_coverage(rows)
    layout_errors = scan_layout_violations(rows)
    write_gaps_report(rows, layout_errors=layout_errors)

    stats = CoverageStats(
        catalog_rows=len(rows),
        numbered=len(health.numbered),
        transcripts_complete=len(health.complete),
        notes_files=notes_files,
        notes_with_datapoints=notes_with_datapoints,
        bullets_missing_timestamp=bullets_missing_timestamp,
        episodes_bullets_missing_timestamp=len(missing_timestamp_episodes),
        posts=posts_n,
        expanded=expanded_n,
        expanded_drafts=expanded_drafts_n,
        missing_expanded_count=len(missing_expanded),
        unmapped_colossus=len(health.unmapped),
        blocking_transcript_gaps=len(health.blocking),
        layout_errors=len(layout_errors),
    )

    blocking_msgs = health.blocking_messages(len(rows), layout_errors)

    return stats, blocking_msgs


def print_coverage_stats(stats: CoverageStats, blocking_msgs: list[str]) -> None:
    print(f"Catalog: {stats.catalog_rows} rows ({stats.numbered} numbered)")
    print(f"Transcripts complete: {stats.transcripts_complete}")
    print(
        f"Notes: {stats.notes_files} files | {stats.notes_with_datapoints} with timestamp datapoints | "
        f"Posts: {stats.posts}"
    )
    if stats.bullets_missing_timestamp:
        print(
            f"  Bullets missing timestamp: {stats.bullets_missing_timestamp} across "
            f"{stats.episodes_bullets_missing_timestamp} episode(s) (`- —` without MM:SS)"
        )
    print(
        f"Expanded: {stats.expanded} canonical | {stats.expanded_drafts} drafts pending | "
        f"backlog (datapoints, no expanded): {stats.missing_expanded_count}"
    )
    print(f"Wrote {GAPS_PATH.relative_to(ROOT)}")
    if blocking_msgs:
        print()
        print("Blocking verification issues (Phase 1 / layout):")
        for msg in blocking_msgs:
            print(f"  - {msg}")
    else:
        print("No blocking verification issues (Phase 2 gaps are informational).")


def action_status_coverage() -> None:
    rows = load_rows()
    if not rows:
        return
    stats, blocking = refresh_coverage_report(rows)
    print_coverage_stats(stats, blocking)


def find_next_notes_path(
    rows: list[dict],
    *,
    episode_from: int = DEFAULT_NOTES_FROM,
) -> Path | None:
    """First complete-transcript episode from episode_from without timestamp datapoints."""
    from scaffold_notes import eligible_rows

    selected = eligible_rows(
        rows,
        episode_from=episode_from,
        episode_to=None,
        episode_id=None,
        missing_only=False,
    )
    for row in selected:
        ep_id = row["id"]
        slug = row["slug"]
        num = row["episode_number"]
        path = notes_file_path(ep_id, slug, num)
        if not path.exists() or not has_timestamp_datapoints(path):
            return path
    return None


def action_next_notes() -> None:
    rows = load_rows()
    if not rows:
        return
    ep_from = prompt_int("Min episode number", DEFAULT_NOTES_FROM) or DEFAULT_NOTES_FROM
    path = find_next_notes_path(rows, episode_from=ep_from)
    if path is None:
        print("No episode in selection needs notes (all have datapoints).")
        return
    print(path.relative_to(ROOT))


def resolve_episode_id(rows: list[dict], raw: str) -> dict | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return resolve_episode_id_arg(rows, raw)
    except SystemExit:
        print(f"Unknown episode id: {raw}")
        return None


def _expand_env() -> tuple[str, str | None]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = (os.environ.get("OPENROUTER_MODEL", "") or "").strip()
    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or None
    return api_key, model, base_url


def _run_expand_batch(
    selected: list[dict],
    *,
    dry_run: bool,
    force: bool,
    subprocess_per_episode: bool,
) -> None:
    from expand_datapoints_llm import run_expand_one

    prompt_path = default_prompt_path()
    system, user_template = load_prompt_template(prompt_path)
    api_key, model, base_url = _expand_env()

    if dry_run:
        estimates: list[ExpandEstimate] = []
        errors = 0
        for row in selected:
            try:
                estimates.append(estimate_expand_for_row(row, prompt_path=prompt_path))
            except (FileNotFoundError, ValueError) as e:
                print(f"[error] {row['id']}: {e}")
                errors += 1
        print_expand_dry_run_summary(
            estimates,
            title="Expand dry-run",
            prompt_path=prompt_path,
            model=model or "(unset)",
        )
        if errors:
            print(f"{errors} episode(s) failed estimation")
        return

    if not api_key:
        print("Set OPENROUTER_API_KEY in .env for apply.")
        return
    if not model:
        print("Set OPENROUTER_MODEL or pass --model for apply.")
        return

    if subprocess_per_episode and len(selected) > 1:
        script = _INGESTION / "notes" / "expand_datapoints_llm.py"
        for batch_i, row in enumerate(selected, start=1):
            cmd = [
                sys.executable,
                str(script),
                "--id",
                row["id"],
                "--apply",
            ]
            if force:
                cmd.append("--force")
            print(f"[expand] {batch_i}/{len(selected)} {row['id']}")
            rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
            if rc != 0:
                print(f"[subprocess] exit {rc} for {row['id']}")
        return

    batch_records: list[dict] = []
    batch_n = len(selected)
    for batch_i, row in enumerate(selected, start=1):
        if batch_n > 1:
            print(f"[expand] {batch_i}/{batch_n} {row['id']}", flush=True)
        status, log_rec = run_expand_one(
            row,
            system=system,
            user_template=user_template,
            prompt_path=prompt_path,
            model=model,
            api_key=api_key,
            base_url=base_url,
            dry_run=False,
            force=force,
        )
        if log_rec:
            batch_records.append(log_rec)
        if status == "error":
            print(f"[error] {row['id']} expand failed")

    if batch_n > 1 and batch_records:
        print_expand_batch_summary(
            batch_records,
            title=f"--- expand batch summary ({batch_n} episodes) ---",
        )


def _select_expand(
    rows: list[dict],
    *,
    episode_id: str | None,
    episode_from: int | None,
    episode_to: int | None,
    missing_expanded: bool,
    limit: int | None,
) -> list[dict]:
    from expand_datapoints_llm import select_expand_rows

    if episode_id:
        resolve_episode_id_arg(rows, episode_id)
    return select_expand_rows(
        rows,
        episode_id=episode_id,
        episode_from=episode_from,
        episode_to=episode_to,
        missing_expanded=missing_expanded,
        limit=limit,
    )


def action_expand_one() -> None:
    rows = load_rows()
    if not rows:
        return
    ep_id = prompt_line("Episode id (e.g. ep-0200)")
    if not resolve_episode_id(rows, ep_id):
        return
    force = confirm_yes("Overwrite existing draft if present?")
    dry_run = not confirm_yes("Call OpenRouter and write draft? (--apply)")
    selected = _select_expand(
        rows,
        episode_id=ep_id,
        episode_from=None,
        episode_to=None,
        missing_expanded=False,
        limit=None,
    )
    if not selected:
        print("Episode not eligible (needs transcript + datapoints).")
        return
    _run_expand_batch(selected, dry_run=dry_run, force=force, subprocess_per_episode=False)


def action_expand_backlog() -> None:
    rows = load_rows()
    if not rows:
        return
    ep_from = prompt_int("From episode number (blank = any)")
    ep_to = prompt_int("To episode number (blank = any)")
    limit = prompt_int("Limit (blank = no limit)")
    force = confirm_yes("Overwrite existing drafts?")
    dry_run = not confirm_yes("Call OpenRouter and write drafts? (--apply)")
    use_subprocess = False
    if not dry_run:
        use_subprocess = confirm_yes("Run each episode in a separate subprocess?")
    selected = _select_expand(
        rows,
        episode_id=None,
        episode_from=ep_from,
        episode_to=ep_to,
        missing_expanded=True,
        limit=limit,
    )
    if not selected:
        print("No episodes matched selection.")
        return
    print(f"Selected {len(selected)} episode(s)")
    _run_expand_batch(
        selected,
        dry_run=dry_run,
        force=force,
        subprocess_per_episode=use_subprocess,
    )


def action_expand_dry_run() -> None:
    rows = load_rows()
    if not rows:
        return
    mode = prompt_line("Scope: one | backlog", "backlog").lower()
    ep_id: str | None = None
    ep_from: int | None = None
    ep_to: int | None = None
    missing = False
    limit: int | None = None
    if mode.startswith("o"):
        ep_id = prompt_line("Episode id")
        if not ep_id:
            return
    else:
        missing = True
        ep_from = prompt_int("From episode number (blank = any)")
        ep_to = prompt_int("To episode number (blank = any)")
        limit = prompt_int("Limit (blank = no limit)")
    selected = _select_expand(
        rows,
        episode_id=ep_id,
        episode_from=ep_from,
        episode_to=ep_to,
        missing_expanded=missing,
        limit=limit,
    )
    if not selected:
        print("No episodes matched selection.")
        return
    _run_expand_batch(selected, dry_run=True, force=False, subprocess_per_episode=False)


@dataclass
class DraftSummary:
    episode_id: str
    draft_path: Path
    n_errors: int
    n_warnings: int
    errors: list[str]
    warnings: list[str]


def collect_production_drafts(rows: list[dict]) -> list[DraftSummary]:
    out: list[DraftSummary] = []
    for row in rows:
        num = row.get("episode_number")
        if num is None:
            continue
        ep_id = row["id"]
        slug = row["slug"]
        draft = expanded_draft_file_path(ep_id, slug, num)
        if not draft.exists():
            continue
        npath = notes_file_path(ep_id, slug, num)
        body = read_markdown_body(draft)
        errors, warnings = validate_expanded_draft(npath, body)
        out.append(
            DraftSummary(
                episode_id=ep_id,
                draft_path=draft,
                n_errors=len(errors),
                n_warnings=len(warnings),
                errors=errors,
                warnings=warnings,
            )
        )
    out.sort(key=lambda d: d.episode_id)
    return out


def action_list_drafts() -> None:
    rows = load_rows()
    if not rows:
        return
    drafts = collect_production_drafts(rows)
    if not drafts:
        print("No production .expanded.draft.md files pending review.")
        return
    print(f"{'episode':<12} {'errors':>6} {'warnings':>8}  path")
    print("-" * 72)
    for d in drafts:
        rel = d.draft_path.relative_to(ROOT)
        print(f"{d.episode_id:<12} {d.n_errors:>6} {d.n_warnings:>8}  {rel}")
    print()
    show_detail = confirm_yes("Show validation details?")
    if show_detail:
        for d in drafts:
            for w in d.warnings:
                print(f"[warn] {d.episode_id}: {w}")
            for e in d.errors:
                print(f"[error] {d.episode_id}: {e}")


def _select_promote_rows(
    rows: list[dict],
    *,
    episode_id: str | None,
    episode_from: int | None,
    episode_to: int | None,
    all_ready: bool,
) -> list[dict]:
    from expand_datapoints_llm import select_promote_rows

    if all_ready:
        selected = [
            r
            for r in rows
            if r.get("episode_number") is not None
            and expanded_draft_file_path(r["id"], r["slug"], r["episode_number"]).exists()
        ]
        if episode_from is not None:
            selected = [r for r in selected if (r.get("episode_number") or 0) >= episode_from]
        if episode_to is not None:
            selected = [r for r in selected if (r.get("episode_number") or 0) <= episode_to]
        selected.sort(key=lambda r: r["episode_number"] or 0)
        return selected
    if episode_id:
        resolve_episode_id_arg(rows, episode_id)
    return select_promote_rows(
        rows,
        episode_id=episode_id,
        episode_from=episode_from,
        episode_to=episode_to,
    )


def _promote_selected(selected: list[dict], *, dry_run: bool) -> None:
    promoted = 0
    blocked = 0
    for row in selected:
        ep_id = row["id"]
        path_or_none, errors, warnings = promote_draft(row, dry_run=dry_run)
        for w in warnings:
            print(f"[warn] {ep_id}: {w}")
        if errors:
            blocked += 1
            for err in errors:
                print(f"[error] {ep_id}: {err}")
            continue
        if dry_run:
            rel = path_or_none.relative_to(ROOT) if path_or_none else ""
            print(f"[dry-run promote] {ep_id} → {rel}")
        else:
            rel = path_or_none.relative_to(ROOT) if path_or_none else ""
            print(f"[promoted] {rel}")
            promoted += 1
    print(f"Done: {promoted} promoted, {blocked} blocked")


def action_promote_drafts() -> None:
    rows = load_rows()
    if not rows:
        return
    mode = prompt_line("Mode: id | range | all-ready", "all-ready").lower()
    ep_id: str | None = None
    ep_from: int | None = None
    ep_to: int | None = None
    all_ready = mode.startswith("a")
    if mode.startswith("i"):
        ep_id = prompt_line("Episode id")
        if not ep_id:
            return
    elif not all_ready:
        ep_from = prompt_int("From episode number (blank = any)")
        ep_to = prompt_int("To episode number (blank = any)")
    dry_run = not confirm_yes("Write canonical .expanded.md and delete drafts? (--apply)")
    selected = _select_promote_rows(
        rows,
        episode_id=ep_id,
        episode_from=ep_from,
        episode_to=ep_to,
        all_ready=all_ready,
    )
    if not selected:
        print("No drafts matched selection.")
        return
    print(f"Selected {len(selected)} draft(s)")
    if not dry_run and not confirm_yes(f"Promote {len(selected)} episode(s)?"):
        print("Cancelled.")
        return
    _promote_selected(selected, dry_run=dry_run)


def action_rebuild_index() -> None:
    if not confirm_yes(
        "Rebuild chunks + embeddings (requires OPENROUTER_API_KEY + OPENROUTER_EMBED_MODEL)?"
    ):
        print("Cancelled.")
        return
    from reindex_vault import reindex_vault

    code, msg = reindex_vault(ROOT)
    if code != 0:
        print(f"Reindex failed (exit {code}):\n{msg}")
        return
    print(msg)


def action_expand_log() -> None:
    records = load_expand_run_log()
    if not records:
        print("No entries in catalog/expand-run.jsonl (file missing or empty).")
        return
    run_id = prompt_line("Filter run_id (blank = all)")
    variant = prompt_line("Filter variant A|B (blank = all)")
    last_n = prompt_int("Last N entries (blank = all after filters)", None)
    filtered = filter_expand_run_log(
        records,
        run_id=run_id or None,
        variant=variant if variant in ("A", "B") else None,
        last=last_n,
    )
    if not filtered:
        print("No expand-run log entries matched.")
        return
    label_parts = []
    if run_id:
        label_parts.append(f"run={run_id}")
    if variant in ("A", "B"):
        label_parts.append(f"variant={variant}")
    title = "--- expand log summary"
    if label_parts:
        title += f" ({', '.join(label_parts)})"
    title += " ---"
    print_expand_batch_summary(filtered, title=title)
    show_rows = confirm_yes("List individual episodes?")
    if show_rows:
        for r in filtered[-20:]:
            ep = r.get("episode_id", "?")
            status = r.get("status", "?")
            cost = r.get("cost_usd")
            cost_s = f" ${cost:.4f}" if cost is not None else ""
            print(f"  {ep}  {status}{cost_s}")


ACTIONS: dict[str, Callable[[], None]] = {
    "1": action_status_coverage,
    "2": action_next_notes,
    "3": action_expand_one,
    "4": action_expand_backlog,
    "5": action_expand_dry_run,
    "6": action_list_drafts,
    "7": action_promote_drafts,
    "8": action_rebuild_index,
    "9": action_expand_log,
}


def run_menu_loop() -> None:
    print("Founders Notes maintenance console")
    print(f"Repo: {ROOT}")
    while True:
        print(MENU)
        choice = prompt_line("Choice")
        if choice == "0":
            print("Bye.")
            return
        action = ACTIONS.get(choice)
        if action is None:
            print("Unknown choice.")
            continue
        try:
            action()
        except KeyboardInterrupt:
            print("\n(interrupted)")
        except SystemExit as e:
            if e.code:
                print(f"Command exited with status {e.code}")


def main() -> None:
    run_menu_loop()


if __name__ == "__main__":
    main()
