"""Load optional agent context from --context-json or --context-file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]


def load_context_extra(parser: argparse.ArgumentParser) -> dict[str, Any] | None:
    """Register --context-json / --context-file on parser; call after parse_args()."""
    parser.add_argument(
        "--context-json",
        help="Optional JSON object for handoff fields (designDocPath, prdPath, ...).",
    )
    parser.add_argument(
        "--context-file",
        help="Path to JSON context file (preferred on Windows PowerShell).",
    )
    return None  # registration only; use parse_context_args(args)


def parse_context_args(args: argparse.Namespace) -> dict[str, Any] | None:
    if getattr(args, "context_file", None) and getattr(args, "context_json", None):
        print("ERROR: Use only one of --context-file or --context-json", file=sys.stderr)
        sys.exit(1)
    if getattr(args, "context_file", None):
        ctx_path = Path(args.context_file)
        if not ctx_path.is_absolute():
            ctx_path = (_REPO_ROOT / ctx_path).resolve()
        if not ctx_path.is_file():
            print(f"ERROR: --context-file not found: {ctx_path}", file=sys.stderr)
            sys.exit(1)
        try:
            parsed = json.loads(ctx_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            print(f"ERROR: --context-file is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(parsed, dict):
            print("ERROR: --context-file JSON must be an object", file=sys.stderr)
            sys.exit(1)
        return parsed
    if getattr(args, "context_json", None):
        try:
            parsed = json.loads(args.context_json)
        except json.JSONDecodeError as exc:
            print(f"ERROR: --context-json is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)
        if isinstance(parsed, dict):
            return parsed
        print("ERROR: --context-json must be an object", file=sys.stderr)
        sys.exit(1)
    return None