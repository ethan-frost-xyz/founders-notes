#!/usr/bin/env python3
"""Sandboxed A/B prompt tuning on a fixed 10-episode batch (subprocess per episode)."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from catalog import load_catalog
from cli_args import resolve_episode_id_arg
from expand_llm import (
    ExpandEstimate,
    _count_datapoint_headings,
    default_prompt_path,
    estimate_expand_for_row,
    print_expand_dry_run_summary,
    prompt_file_hash,
    promote_draft,
    validate_expanded_draft,
)
from markdown_io import TIMESTAMP_BULLET_RE, read_markdown_body, utc_now_iso
import paths
from paths import (
    INGESTION_DIR,
    expanded_draft_file_path,
    notes_file_path,
    staging_draft_file_path,
)

EXPAND_RUNS_DIR = INGESTION_DIR / "fixtures" / "expand-runs"
DEFAULT_BATCH_FILE = paths.ROOT / "catalog" / "expand-tune-batch.json"
PROMPT_A = INGESTION_DIR / "prompts" / "expand_datapoints.md"
PROMPT_B = INGESTION_DIR / "prompts" / "expand_datapoints.candidate.md"
LLM_SCRIPT = INGESTION_DIR / "notes" / "expand_datapoints_llm.py"

load_dotenv(paths.ROOT / ".env")


def load_batch_file(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = data.get("episode_ids")
    if not ids:
        raise SystemExit(f"No episode_ids in {path.relative_to(paths.ROOT)}")
    return list(ids)


def catalog_rows_by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def run_dir(run_id: str) -> Path:
    return EXPAND_RUNS_DIR / run_id


def manifest_path(run_id: str) -> Path:
    return run_dir(run_id) / "manifest.json"


def load_manifest(run_id: str) -> dict[str, Any]:
    p = manifest_path(run_id)
    if not p.exists():
        raise SystemExit(f"No manifest at {p.relative_to(paths.ROOT)} — run init first")
    return json.loads(p.read_text(encoding="utf-8"))


def save_manifest(run_id: str, manifest: dict[str, Any]) -> None:
    p = manifest_path(run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_prompt(variant: str, prompt_arg: Path | None) -> Path:
    if prompt_arg is not None:
        return prompt_arg if prompt_arg.is_absolute() else (paths.ROOT / prompt_arg).resolve()
    if variant == "A":
        return PROMPT_A
    return PROMPT_B


def cmd_init(args: argparse.Namespace) -> None:
    rd = run_dir(args.run_id)
    if rd.exists() and not args.force:
        raise SystemExit(
            f"Run dir exists: {rd.relative_to(paths.ROOT)} (use --force to re-init)"
        )
    rd.mkdir(parents=True, exist_ok=True)
    if not PROMPT_B.exists() or args.force:
        shutil.copy2(PROMPT_A, PROMPT_B)
        print(f"[init] seeded {PROMPT_B.relative_to(paths.ROOT)} from baseline")
    manifest = {
        "run_id": args.run_id,
        "created_at": utc_now_iso(),
        "batch_file": str(
            args.batch_file.relative_to(paths.ROOT)
            if args.batch_file.resolve().is_relative_to(paths.ROOT.resolve())
            else args.batch_file
        ),
        "variants": {},
    }
    save_manifest(args.run_id, manifest)
    print(f"[init] {rd.relative_to(paths.ROOT)}")


def build_child_cmd(
    *,
    episode_id: str,
    run_id: str,
    variant: str,
    prompt_path: Path,
    apply: bool,
    force: bool,
    model: str | None,
) -> list[str]:
    cmd: list[str] = [
        sys.executable,
        str(LLM_SCRIPT),
        "--id",
        episode_id,
        "--staging-dir",
        str(run_dir(run_id)),
        "--variant",
        variant,
        "--prompt",
        str(prompt_path),
    ]
    if apply:
        cmd.append("--apply")
    else:
        cmd.append("--dry-run")
    if force:
        cmd.append("--force")
    if model:
        cmd.extend(["--model", model])
    return cmd


def update_manifest_variant(
    run_id: str,
    variant: str,
    *,
    prompt_path: Path,
    model: str | None,
) -> None:
    manifest = load_manifest(run_id)
    variants = manifest.setdefault("variants", {})
    entry: dict[str, Any] = {
        "prompt_path": str(prompt_path.relative_to(paths.ROOT)),
        "prompt_hash": prompt_file_hash(prompt_path),
        "last_expand_at": utc_now_iso(),
    }
    if model:
        entry["model"] = model
    variants[variant] = entry
    save_manifest(run_id, manifest)


def cmd_expand(args: argparse.Namespace) -> None:
    if not manifest_path(args.run_id).exists():
        raise SystemExit(f"Run not initialized: {args.run_id}")
    episode_ids = load_batch_file(args.batch_file)
    rows = load_catalog()
    by_id = catalog_rows_by_id(rows)
    prompt_path = resolve_prompt(args.variant, args.prompt)
    model_display = (args.model or os.environ.get("OPENROUTER_MODEL", "")).strip() or "(unset)"
    model = (args.model or os.environ.get("OPENROUTER_MODEL", "")).strip() or None

    if args.apply and not os.environ.get("OPENROUTER_API_KEY", "").strip():
        raise SystemExit("Set OPENROUTER_API_KEY in .env for --apply")

    errors = 0

    if args.dry_run:
        estimates: list[ExpandEstimate] = []
        for ep_id in episode_ids:
            row = by_id.get(ep_id)
            if not row:
                print(f"[skip] {ep_id}: not in catalog")
                errors += 1
                continue
            resolve_episode_id_arg(rows, ep_id)
            try:
                estimates.append(estimate_expand_for_row(row, prompt_path=prompt_path))
            except (FileNotFoundError, ValueError) as e:
                print(f"[error] {ep_id}: {e}")
                errors += 1
        ab_hint = (
            f"Full A/B on this batch: ~{len(estimates) * 2} API calls "
            f"(run variant A and B with --apply)"
        )
        print_expand_dry_run_summary(
            estimates,
            title=f"Expand dry-run  run={args.run_id}  variant={args.variant}",
            prompt_path=prompt_path,
            model=model_display,
            extra_footer_lines=[ab_hint],
        )
    else:
        for ep_id in episode_ids:
            if ep_id not in by_id:
                print(f"[skip] {ep_id}: not in catalog")
                errors += 1
                continue
            resolve_episode_id_arg(rows, ep_id)
            cmd = build_child_cmd(
                episode_id=ep_id,
                run_id=args.run_id,
                variant=args.variant,
                prompt_path=prompt_path,
                apply=True,
                force=args.force,
                model=model,
            )
            print(f"[expand] {ep_id} variant {args.variant}")
            rc = subprocess.run(cmd, cwd=str(paths.ROOT)).returncode
            if rc != 0:
                print(f"[error] {ep_id}: subprocess exit {rc}")
                errors += 1

    if args.apply or args.dry_run:
        update_manifest_variant(args.run_id, args.variant, prompt_path=prompt_path, model=model)

    if errors:
        raise SystemExit(f"{errors} episode(s) failed")


def draft_report_row(row: dict, variant: str, run_id: str) -> dict[str, Any]:
    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    staging = run_dir(run_id)
    draft = staging_draft_file_path(staging, variant, ep_id, slug, num)
    npath = notes_file_path(ep_id, slug, num)
    out: dict[str, Any] = {
        "episode_id": ep_id,
        "variant": variant,
        "draft_exists": draft.exists(),
    }
    if not draft.exists():
        out["errors"] = ["no draft"]
        return out
    body = read_markdown_body(draft)
    n_bullets = len(TIMESTAMP_BULLET_RE.findall(read_markdown_body(npath)))
    val_errors, val_warnings = validate_expanded_draft(npath, body)
    out["n_bullets"] = n_bullets
    out["n_sections"] = _count_datapoint_headings(body)
    out["validation_errors"] = val_errors
    out["validation_warnings"] = val_warnings
    text = draft.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if line.startswith("model:"):
                    out["model"] = line.split(":", 1)[1].strip().strip('"')
                if line.startswith("prompt_hash:"):
                    out["prompt_hash"] = line.split(":", 1)[1].strip().strip('"')
    return out


def _batch_path_from_args(args: argparse.Namespace, manifest: dict[str, Any] | None) -> Path:
    if manifest and manifest.get("batch_file"):
        bp = Path(manifest["batch_file"])
        return bp if bp.is_absolute() else paths.ROOT / bp
    return args.batch_file


def cmd_report(args: argparse.Namespace) -> None:
    manifest = load_manifest(args.run_id)
    batch_path = _batch_path_from_args(args, manifest)
    episode_ids = load_batch_file(batch_path)

    rows = load_catalog()
    by_id = catalog_rows_by_id(rows)

    print(f"Run: {args.run_id}")
    if manifest.get("variants"):
        for v, meta in manifest["variants"].items():
            print(
                f"  variant {v}: prompt={meta.get('prompt_path')} "
                f"hash={meta.get('prompt_hash')} model={meta.get('model', '(env)')}"
            )
    print()
    print(f"{'episode':<12} {'A secs':>8} {'A err':>6} {'B secs':>8} {'B err':>6}  notes")
    print("-" * 60)

    for ep_id in episode_ids:
        row = by_id.get(ep_id)
        if not row:
            print(f"{ep_id:<12}  (not in catalog)")
            continue
        ra = draft_report_row(row, "A", args.run_id)
        rb = draft_report_row(row, "B", args.run_id)
        a_secs = ra.get("n_sections", "-") if ra["draft_exists"] else "-"
        b_secs = rb.get("n_sections", "-") if rb["draft_exists"] else "-"
        a_err = len(ra.get("validation_errors", [])) if ra["draft_exists"] else "-"
        b_err = len(rb.get("validation_errors", [])) if rb["draft_exists"] else "-"
        bullets = ra.get("n_bullets", rb.get("n_bullets", "?"))
        note = ""
        if ra["draft_exists"] and rb["draft_exists"]:
            if a_err == 0 and b_err > 0:
                note = "A ok, B fail"
            elif b_err == 0 and a_err > 0:
                note = "B ok, A fail"
            elif a_secs != b_secs:
                note = f"section mismatch (bullets={bullets})"
        elif not ra["draft_exists"] or not rb["draft_exists"]:
            note = "missing draft"
        print(f"{ep_id:<12} {str(a_secs):>8} {str(a_err):>6} {str(b_secs):>8} {str(b_err):>6}  {note}")

        for label, r in (("A", ra), ("B", rb)):
            for w in r.get("validation_warnings", []):
                print(f"  [{label} warn] {ep_id}: {w}")
            for e in r.get("validation_errors", []):
                print(f"  [{label} error] {ep_id}: {e}")


def cmd_promote(args: argparse.Namespace) -> None:
    manifest = load_manifest(args.run_id) if manifest_path(args.run_id).exists() else None
    batch_path = _batch_path_from_args(args, manifest)
    episode_ids = load_batch_file(batch_path)
    if args.episode_id:
        episode_ids = [args.episode_id]

    rows = load_catalog()
    by_id = catalog_rows_by_id(rows)
    staging = run_dir(args.run_id)
    dry = args.dry_run

    for ep_id in episode_ids:
        row = by_id.get(ep_id)
        if not row:
            print(f"[skip] {ep_id}: not in catalog")
            continue
        slug = row["slug"]
        num = row.get("episode_number")
        src = staging_draft_file_path(staging, args.variant, ep_id, slug, num)
        if not src.exists():
            print(f"[error] {ep_id}: no staging draft for variant {args.variant}")
            continue
        dest = expanded_draft_file_path(ep_id, slug, num)
        if dry:
            print(
                f"[dry-run promote] {ep_id}: "
                f"{src.relative_to(paths.ROOT)} → {dest.relative_to(paths.ROOT)}"
            )
            draft_for_promote = src
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            draft_for_promote = dest
        path_or_none, errors, warnings = promote_draft(
            row, dry_run=dry, draft_path=draft_for_promote
        )
        for w in warnings:
            print(f"[warn] {ep_id}: {w}")
        if errors:
            for err in errors:
                print(f"[error] {ep_id}: {err}")
            continue
        if dry:
            print(f"[dry-run promote] {ep_id} → .expanded.md ok")
        else:
            rel = path_or_none.relative_to(paths.ROOT) if path_or_none else ""
            print(f"[promoted] {rel}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sandboxed A/B prompt tuning (10-episode batch, subprocess per episode)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create run dir and manifest")
    p_init.add_argument("--run-id", required=True)
    p_init.add_argument("--force", action="store_true", help="Re-init and re-seed candidate prompt")
    p_init.add_argument(
        "--batch-file",
        type=Path,
        default=DEFAULT_BATCH_FILE,
        help="Episode list JSON",
    )

    p_expand = sub.add_parser("expand", help="Expand batch via one subprocess per episode")
    p_expand.add_argument("--run-id", required=True)
    p_expand.add_argument("--variant", required=True, choices=("A", "B"))
    p_expand.add_argument("--prompt", type=Path, help="Override prompt file for this variant")
    p_expand.add_argument("--model", help="Override OPENROUTER_MODEL")
    p_expand.add_argument("--force", action="store_true", help="Overwrite existing staging drafts")
    p_expand.add_argument("--dry-run", action="store_true")
    p_expand.add_argument("--apply", action="store_true")
    p_expand.add_argument("--batch-file", type=Path, default=DEFAULT_BATCH_FILE)

    p_report = sub.add_parser("report", help="Compare variant A vs B per episode")
    p_report.add_argument("--run-id", required=True)
    p_report.add_argument("--batch-file", type=Path, default=DEFAULT_BATCH_FILE)

    p_promote = sub.add_parser("promote", help="Copy staging winner → notes → .expanded.md")
    p_promote.add_argument("--run-id", required=True)
    p_promote.add_argument("--variant", required=True, choices=("A", "B"))
    p_promote.add_argument("--id", dest="episode_id", help="Single episode (default: full batch)")
    p_promote.add_argument("--dry-run", action="store_true")
    p_promote.add_argument("--apply", action="store_true")
    p_promote.add_argument("--batch-file", type=Path, default=DEFAULT_BATCH_FILE)

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "expand":
        if not args.dry_run and not args.apply:
            p_expand.error("Specify --dry-run or --apply")
        cmd_expand(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "promote":
        if not args.dry_run and not args.apply:
            p_promote.error("Specify --dry-run or --apply")
        cmd_promote(args)


if __name__ == "__main__":
    main()
