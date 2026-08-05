"""RDS + UI parity checks for run-sdlc-local.ps1 local verify (mirrors dev_validate_app gates)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.validate_rds_parity import validate_rds_parity, validate_rds_parity_warnings  # noqa: E402
from _shared.validate_ui_parity import validate_ui_parity, validate_ui_parity_blocking  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RDS and UI parity for a target app")
    parser.add_argument("--target-app", required=True)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT))
    args = parser.parse_args()

    root = Path(args.repo_root)
    app_dir = root / "target-apps" / args.target_app
    if not app_dir.is_dir():
        print(f"FAILED: target-apps/{args.target_app}/ not found", file=sys.stderr)
        return 1

    errors = validate_rds_parity(app_dir)
    errors.extend(validate_ui_parity_blocking(app_dir, root))

    for warn in validate_rds_parity_warnings(app_dir):
        print(f"WARN: {warn}", file=sys.stderr)
    for msg in validate_ui_parity(app_dir, root):
        if " WARN:" in msg:
            print(f"WARN: {msg}", file=sys.stderr)

    if errors:
        for err in errors:
            print(f"FAILED: {err}", file=sys.stderr)
        return 1

    print(f"parity OK: {args.target_app}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
