#!/usr/bin/env python3
"""Write {folder}.expanded.draft.md via OpenRouter; promote validated drafts to .expanded.md."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from cli_args import add_episode_id_arg, ensure_catalog, resolve_episode_id_arg
from expand_llm import (
    append_expand_run_log,
    build_user_message,
    call_openrouter,
    default_prompt_path,
    load_prompt_template,
    parse_expanded_body,
    promote_draft,
    write_expanded_draft,
)
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
) -> str:
    """Return status: skipped | dry_run | wrote | error."""
    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    draft_path = expanded_draft_file_path(ep_id, slug, num)

    if draft_path.exists() and not force and not dry_run:
        return "skipped"

    npath = notes_file_path(ep_id, slug, num)
    tx_path = transcript_dir(ep_id, slug, num) / transcript_filename(ep_id, slug, num)
    notes_body = read_body(npath)
    transcript_body = read_body(tx_path)
    user_msg = build_user_message(user_template, notes=notes_body, transcript=transcript_body)

    if dry_run:
        est = len(notes_body) + len(transcript_body) + len(system) + len(user_msg)
        print(
            f"[dry-run] {ep_id} notes={len(notes_body)} tx={len(transcript_body)} "
            f"approx_chars={est}"
        )
        return "dry_run"

    try:
        raw = call_openrouter(
            system=system,
            user=user_msg,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0,
        )
        body = parse_expanded_body(raw)
        out = write_expanded_draft(row, body, model=model, prompt_path=prompt_path)
        print(f"[wrote] {out.relative_to(paths.ROOT)}")
        append_expand_run_log(
            {
                "episode_id": ep_id,
                "status": "ok",
                "error": None,
                "model": model,
                "at": utc_now_iso(),
            }
        )
        return "wrote"
    except Exception as e:
        print(f"[error] {ep_id}: {e}")
        append_expand_run_log(
            {
                "episode_id": ep_id,
                "status": "error",
                "error": str(e),
                "model": model,
                "at": utc_now_iso(),
            }
        )
        return "error"


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
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("Specify --dry-run or --apply")

    rows = ensure_catalog()
    prompt_path = args.prompt if args.prompt else default_prompt_path()
    system, user_template = load_prompt_template(prompt_path)

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

    if args.subprocess:
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
                cmd.extend(["--prompt", str(args.prompt)])
            print(f"[subprocess] {' '.join(str(x) for x in cmd)}")
            rc = subprocess.run(cmd, cwd=str(paths.ROOT)).returncode
            if rc != 0:
                print(f"[subprocess] exit {rc} for {row['id']}")
        return

    for row in selected:
        run_expand_one(
            row,
            system=system,
            user_template=user_template,
            prompt_path=prompt_path,
            model=model,
            api_key=api_key,
            base_url=base_url,
            dry_run=args.dry_run,
            force=args.force,
        )


if __name__ == "__main__":
    main()
