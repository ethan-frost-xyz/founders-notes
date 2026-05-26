#!/usr/bin/env python3
"""Build datapoint expansion prompt from {folder}.notes.md + {folder}.transcript.md."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
import subprocess
import sys
from pathlib import Path

from cli_args import add_episode_id_arg, ensure_catalog, resolve_episode_id_arg
from expand_llm import (
    build_combined_prompt_for_clipboard,
    build_user_message,
    default_prompt_path,
    load_prompt_template,
)
from markdown_io import read_markdown_body
from paths import ROOT, expanded_file_path, notes_file_path, transcript_dir, transcript_filename


def read_body(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Missing file: {path.relative_to(ROOT)}")
    return read_markdown_body(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Datapoint expansion prompt builder")
    add_episode_id_arg(parser, required=True)
    parser.add_argument("--copy", action="store_true", help="Copy prompt to macOS clipboard")
    parser.add_argument("--write", action="store_true", help="Write expanded.md scaffold")
    parser.add_argument(
        "--prompt",
        type=Path,
        help="Prompt markdown (<<<SYSTEM>>> / <<<USER>>>); default prompts/expand_datapoints.md",
    )
    args = parser.parse_args()

    rows = ensure_catalog()
    row = resolve_episode_id_arg(rows, args.episode_id)
    assert row is not None
    slug = row["slug"]
    ep_id = row["id"]
    num = row.get("episode_number")

    npath = notes_file_path(ep_id, slug, num)
    tx_path = transcript_dir(ep_id, slug, num) / transcript_filename(ep_id, slug, num)

    notes_body = read_body(npath)
    transcript_body = read_body(tx_path)
    prompt_path = args.prompt if args.prompt else default_prompt_path()
    system, user_tpl = load_prompt_template(prompt_path)
    user_msg = build_user_message(user_tpl, notes=notes_body, transcript=transcript_body)
    prompt = build_combined_prompt_for_clipboard(system, user_msg)

    if args.write:
        out = expanded_file_path(ep_id, slug, num)
        out.parent.mkdir(parents=True, exist_ok=True)
        content = f"<!-- Run expand_datapoints.py --id {ep_id} and replace below -->\n\n{prompt}\n"
        out.write_text(content, encoding="utf-8")
        print(f"Wrote scaffold {out.relative_to(ROOT)}")
        return

    if args.copy:
        try:
            subprocess.run(["pbcopy"], input=prompt.encode("utf-8"), check=True)
            print("Copied prompt to clipboard")
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("pbcopy unavailable; printing to stdout", file=sys.stderr)

    print(prompt)


if __name__ == "__main__":
    main()
