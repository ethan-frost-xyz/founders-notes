#!/usr/bin/env python3
"""Write {folder}.expanded.draft.md via OpenRouter; promote validated drafts to .expanded.md."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from cli_args import add_episode_id_arg, ensure_catalog, resolve_episode_id_arg
from expand_llm import (
    ExpandEstimate,
    _count_datapoint_headings,
    build_user_message,
    call_openrouter,
    default_prompt_path,
    estimate_expand_for_row,
    expand_log_context_from_env,
    filter_expand_run_log,
    load_expand_run_log,
    load_prompt_template,
    log_expand_event,
    parse_expanded_body,
    print_expand_batch_summary,
    print_expand_dry_run_summary,
    print_expand_ok_line,
    promote_draft,
    prompt_file_hash,
    resolve_draft_path,
    validate_expanded_draft,
    write_expanded_draft,
)
from markdown_io import TIMESTAMP_BULLET_RE
from markdown_io import has_timestamp_datapoints, read_markdown_body, utc_now_iso
import paths
from paths import (
    expanded_draft_file_path,
    expanded_file_path,
    notes_file_path,
    transcript_dir,
    transcript_filename,
)

load_dotenv(paths.ROOT / ".env")


def read_body(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Missing file: {path.relative_to(paths.ROOT)}")
    return read_markdown_body(path)


def select_expand_rows(
    rows: list[dict],
    *,
    episode_id: str | None,
    episode_from: int | None,
    episode_to: int | None,
    missing_expanded: bool,
    limit: int | None,
) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        num = row.get("episode_number")
        if num is None:
            continue
        if row.get("transcript_status") != "complete":
            continue
        if episode_from is not None and num < episode_from:
            continue
        if episode_to is not None and num > episode_to:
            continue
        if episode_id is not None and row["id"] != episode_id:
            continue
        ep_id = row["id"]
        slug = row["slug"]
        npath = notes_file_path(ep_id, slug, num)
        if not npath.exists() or not has_timestamp_datapoints(npath):
            continue
        if missing_expanded and expanded_file_path(ep_id, slug, num).exists():
            continue
        out.append(row)
    out.sort(key=lambda r: r["episode_number"] or 0)
    if limit is not None:
        out = out[:limit]
    return out


def select_promote_rows(
    rows: list[dict],
    *,
    episode_id: str | None,
    episode_from: int | None,
    episode_to: int | None,
) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        num = row.get("episode_number")
        if num is None:
            continue
        if episode_from is not None and num < episode_from:
            continue
        if episode_to is not None and num > episode_to:
            continue
        if episode_id is not None and row["id"] != episode_id:
            continue
        ep_id = row["id"]
        slug = row["slug"]
        if not expanded_draft_file_path(ep_id, slug, num).exists():
            continue
        out.append(row)
    out.sort(key=lambda r: r["episode_number"] or 0)
    return out


def _prompt_rel(prompt_path: Path) -> str:
    try:
        return str(prompt_path.relative_to(paths.ROOT))
    except ValueError:
        return str(prompt_path)


def _expand_run_log_base(
    *,
    ep_id: str,
    model: str,
    prompt_path: Path,
    staging_dir: Path | None,
    variant: str | None,
    n_bullets: int,
    input_chars: int | None = None,
) -> dict:
    record: dict = {
        "episode_id": ep_id,
        "model": model,
        "prompt_hash": prompt_file_hash(prompt_path),
        "prompt_path": _prompt_rel(prompt_path),
        "at": utc_now_iso(),
    }
    if staging_dir is not None:
        try:
            record["staging_dir"] = str(staging_dir.relative_to(paths.ROOT))
        except ValueError:
            record["staging_dir"] = str(staging_dir)
    if variant:
        record["variant"] = variant
    if n_bullets:
        record["n_bullets"] = n_bullets
    if input_chars is not None:
        record["input_chars"] = input_chars
    record.update(expand_log_context_from_env())
    return record


def run_expand_one(
    row: dict,
    *,
    system: str,
    user_template: str,
    prompt_path: Path,
    model: str,
    api_key: str,
    base_url: str | None,
    dry_run: bool,
    force: bool,
    staging_dir: Path | None = None,
    variant: str | None = None,
) -> tuple[str, dict | None]:
    """Return (status, log record). status: skipped | dry_run | wrote | error."""
    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    draft_path = resolve_draft_path(row, staging_root=staging_dir, variant=variant)

    npath = notes_file_path(ep_id, slug, num)
    tx_path = transcript_dir(ep_id, slug, num) / transcript_filename(ep_id, slug, num)
    notes_body = read_body(npath)
    transcript_body = read_body(tx_path)
    user_msg = build_user_message(user_template, notes=notes_body, transcript=transcript_body)
    n_bullets = len(TIMESTAMP_BULLET_RE.findall(notes_body))
    input_chars = len(system) + len(user_msg)

    if draft_path.exists() and not force and not dry_run:
        print(f"[skip] {ep_id} (draft exists)")
        log_rec = _expand_run_log_base(
            ep_id=ep_id,
            model=model,
            prompt_path=prompt_path,
            staging_dir=staging_dir,
            variant=variant,
            n_bullets=n_bullets,
            input_chars=input_chars,
        )
        log_rec.update(
            {
                "status": "skipped",
                "draft_path": str(draft_path.relative_to(paths.ROOT)),
            }
        )
        return "skipped", log_expand_event(log_rec)

    if dry_run:
        return "dry_run", None

    print(f"[expand] {ep_id}  {n_bullets} bullets  model={model}")

    try:
        completion = call_openrouter(
            system=system,
            user=user_msg,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0,
        )
        body = parse_expanded_body(completion.content)
        out = write_expanded_draft(
            row,
            body,
            model=model,
            prompt_path=prompt_path,
            staging_root=staging_dir,
            variant=variant,
        )
        n_sections = _count_datapoint_headings(body)
        val_errors, _ = validate_expanded_draft(npath, body)
        draft_rel = str(out.relative_to(paths.ROOT))
        print_expand_ok_line(
            episode_id=ep_id,
            completion=completion,
            draft_rel=draft_rel,
        )
        log_rec = _expand_run_log_base(
            ep_id=ep_id,
            model=model,
            prompt_path=prompt_path,
            staging_dir=staging_dir,
            variant=variant,
            n_bullets=n_bullets,
            input_chars=input_chars,
        )
        log_rec.update(
            {
                "status": "ok",
                "error": None,
                "draft_path": draft_rel,
                "n_sections": n_sections,
                "validation_errors": val_errors,
                "response_id": completion.response_id,
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "total_tokens": completion.total_tokens,
                "cost_usd": completion.cost_usd,
                "duration_ms": completion.duration_ms,
            }
        )
        return "wrote", log_expand_event(log_rec)
    except Exception as e:
        print(f"[error] {ep_id}: {e}")
        log_rec = _expand_run_log_base(
            ep_id=ep_id,
            model=model,
            prompt_path=prompt_path,
            staging_dir=staging_dir,
            variant=variant,
            n_bullets=n_bullets,
            input_chars=input_chars,
        )
        log_rec.update({"status": "error", "error": str(e)})
        return "error", log_expand_event(log_rec)


def cmd_summarize_log(args: argparse.Namespace) -> None:
    records = load_expand_run_log()
    filtered = filter_expand_run_log(
        records, run_id=args.log_run_id, variant=args.log_variant, last=args.last
    )
    if not filtered:
        print("No expand-run log entries matched")
        return
    label_parts = []
    if args.log_run_id:
        label_parts.append(f"run={args.log_run_id}")
    if args.log_variant:
        label_parts.append(f"variant={args.log_variant}")
    title = "--- expand log summary"
    if label_parts:
        title += f" ({', '.join(label_parts)})"
    title += " ---"
    print_expand_batch_summary(filtered, title=title)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Datapoint expansion via OpenRouter → .expanded.draft.md; --promote → .expanded.md"
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote drafts to .expanded.md (use with --dry-run or --apply)",
    )
    parser.add_argument("--from", dest="episode_from", type=int, help="Min episode number")
    parser.add_argument("--to", dest="episode_to", type=int, help="Max episode number")
    add_episode_id_arg(parser, required=False)
    parser.add_argument(
        "--missing-expanded",
        action="store_true",
        help="Only episodes with datapoints and no .expanded.md yet",
    )
    parser.add_argument(
        "--all-ready",
        action="store_true",
        help="With --promote: every episode that has a .expanded.draft.md",
    )
    parser.add_argument("--dry-run", action="store_true", help="No API writes; promote validates only")
    parser.add_argument("--apply", action="store_true", help="Call API (expand) or write files (promote)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing draft when expanding")
    parser.add_argument(
        "--subprocess",
        action="store_true",
        help="Run each episode as a separate process (clean memory per episode)",
    )
    parser.add_argument("--limit", type=int, help="Max episodes per selection (expand mode)")
    parser.add_argument("--model", help="Override OPENROUTER_MODEL")
    parser.add_argument(
        "--prompt",
        type=Path,
        help="Override prompt markdown (must contain <<<SYSTEM>>> and <<<USER>>>)",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        help="Write drafts under {staging-dir}/{variant}/ (tune sandbox; requires --variant)",
    )
    parser.add_argument(
        "--variant",
        choices=("A", "B"),
        help="A/B variant subfolder when using --staging-dir",
    )
    parser.add_argument(
        "--summarize-log",
        action="store_true",
        help="Print rollup from catalog/expand-run.jsonl (no expand/promote)",
    )
    parser.add_argument(
        "--run-id",
        dest="log_run_id",
        help="With --summarize-log: filter by EXPAND_RUN_ID / tune run_id",
    )
    parser.add_argument(
        "--log-variant",
        choices=("A", "B"),
        help="With --summarize-log: filter by variant",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=None,
        help="With --summarize-log: only last N log rows after filters",
    )
    args = parser.parse_args()

    if args.summarize_log:
        cmd_summarize_log(args)
        return

    if args.staging_dir and not args.variant:
        parser.error("--staging-dir requires --variant A or B")

    if not args.dry_run and not args.apply:
        parser.error("Specify --dry-run or --apply")

    rows = ensure_catalog()
    prompt_path = args.prompt if args.prompt else default_prompt_path()
    if args.prompt and not args.prompt.is_absolute():
        prompt_path = (paths.ROOT / args.prompt).resolve()
    system, user_template = load_prompt_template(prompt_path)
    staging_dir = None
    if args.staging_dir:
        staging_dir = (
            args.staging_dir
            if args.staging_dir.is_absolute()
            else (paths.ROOT / args.staging_dir).resolve()
        )

    if args.promote:
        if args.all_ready:
            selected = [
                r
                for r in rows
                if r.get("episode_number") is not None
                and expanded_draft_file_path(r["id"], r["slug"], r["episode_number"]).exists()
            ]
            if args.episode_from is not None:
                selected = [
                    r for r in selected if (r.get("episode_number") or 0) >= args.episode_from
                ]
            if args.episode_to is not None:
                selected = [
                    r for r in selected if (r.get("episode_number") or 0) <= args.episode_to
                ]
            selected.sort(key=lambda r: r["episode_number"] or 0)
        else:
            if not args.episode_id and args.episode_from is None and args.episode_to is None:
                parser.error("--promote requires --id, --from/--to, or --all-ready")
            episode_id = None
            if args.episode_id:
                resolve_episode_id_arg(rows, args.episode_id)
                episode_id = args.episode_id
            selected = select_promote_rows(
                rows,
                episode_id=episode_id,
                episode_from=args.episode_from,
                episode_to=args.episode_to,
            )
        if not selected:
            print("No drafts matched selection")
            return
        dry = args.dry_run
        for row in selected:
            ep_id = row["id"]
            path_or_none, errors, warnings = promote_draft(row, dry_run=dry)
            for w in warnings:
                print(f"[warn] {ep_id}: {w}")
            if errors:
                for err in errors:
                    print(f"[error] {ep_id}: {err}")
                continue
            if dry:
                print(
                    f"[dry-run promote] {ep_id} → "
                    f"{path_or_none.relative_to(paths.ROOT) if path_or_none else ''}"
                )
            else:
                print(
                    f"[promoted] {path_or_none.relative_to(paths.ROOT) if path_or_none else ''}"
                )
        return

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = (args.model or os.environ.get("OPENROUTER_MODEL", "")).strip()
    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or None

    if args.apply and not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY in .env for --apply")
    if args.apply and not model:
        raise SystemExit("Set OPENROUTER_MODEL or pass --model")

    episode_id = args.episode_id
    if episode_id:
        resolve_episode_id_arg(rows, episode_id)
    if not episode_id and args.episode_from is None and args.episode_to is None and not args.missing_expanded:
        parser.error("Expand mode requires --id, --from/--to, or --missing-expanded")

    selected = select_expand_rows(
        rows,
        episode_id=episode_id,
        episode_from=args.episode_from,
        episode_to=args.episode_to,
        missing_expanded=args.missing_expanded,
        limit=args.limit,
    )
    if not selected:
        print("No episodes matched selection")
        return

    if args.subprocess and not args.dry_run:
        script = Path(__file__).resolve()
        for row in selected:
            cmd: list[str | Path] = [
                sys.executable,
                str(script),
                "--id",
                row["id"],
                "--apply" if args.apply else "--dry-run",
            ]
            if args.force:
                cmd.append("--force")
            if args.model:
                cmd.extend(["--model", args.model])
            if args.prompt:
                cmd.extend(["--prompt", str(prompt_path)])
            if staging_dir:
                cmd.extend(["--staging-dir", str(staging_dir)])
            if args.variant:
                cmd.extend(["--variant", args.variant])
            print(f"[subprocess] {' '.join(str(x) for x in cmd)}")
            rc = subprocess.run(cmd, cwd=str(paths.ROOT)).returncode
            if rc != 0:
                print(f"[subprocess] exit {rc} for {row['id']}")
        if args.apply and len(selected) > 1:
            ctx = expand_log_context_from_env()
            filtered = filter_expand_run_log(
                load_expand_run_log(),
                run_id=ctx.get("run_id"),
                variant=ctx.get("variant") or args.variant,
            )
            if filtered:
                print_expand_batch_summary(
                    filtered[-len(selected) :],
                    title=f"--- expand batch summary ({len(selected)} episodes) ---",
                )
        return

    if args.dry_run:
        estimates: list[ExpandEstimate] = []
        dry_errors = 0
        for row in selected:
            try:
                estimates.append(estimate_expand_for_row(row, prompt_path=prompt_path))
            except (FileNotFoundError, ValueError) as e:
                print(f"[error] {row['id']}: {e}")
                dry_errors += 1
        print_expand_dry_run_summary(
            estimates,
            title="Expand dry-run",
            prompt_path=prompt_path,
            model=model or "(unset)",
        )
        if dry_errors:
            raise SystemExit(f"{dry_errors} episode(s) failed")
        return

    batch_records: list[dict] = []
    for row in selected:
        status, log_rec = run_expand_one(
            row,
            system=system,
            user_template=user_template,
            prompt_path=prompt_path,
            model=model,
            api_key=api_key,
            base_url=base_url,
            dry_run=False,
            force=args.force,
            staging_dir=staging_dir,
            variant=args.variant,
        )
        if log_rec:
            batch_records.append(log_rec)

    if len(selected) > 1 and batch_records:
        ctx = expand_log_context_from_env()
        label = f"--- expand batch summary ({len(selected)} episodes)"
        if ctx.get("run_id"):
            label += f", run={ctx['run_id']}"
        if ctx.get("variant") or args.variant:
            label += f", variant={ctx.get('variant') or args.variant}"
        label += " ---"
        print_expand_batch_summary(batch_records, title=label)


if __name__ == "__main__":
    main()
