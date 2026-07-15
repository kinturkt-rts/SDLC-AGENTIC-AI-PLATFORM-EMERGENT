"""Load monorepo / backend `.env` and `.env.local` into the process environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_MONOREPO_ROOT = _BACKEND_ROOT.parent

_AWS_STATIC_KEYS = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    }
)

_CALLER_SETTABLE_KEYS = frozenset(
    {"ARTIFACT_STORE", "PRODUCT_ARTIFACT_LAYOUT", "PRODUCT_PRD_LAYOUT"}
)


def load_repo_env() -> None:
    if os.getenv("SDLC_SKIP_REPO_ENV", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    merged: dict[str, str | None] = {}
    for path in (
        _MONOREPO_ROOT / ".env",
        _MONOREPO_ROOT / ".env.local",
        _BACKEND_ROOT / ".env",
        _BACKEND_ROOT / ".env.local",
    ):
        if path.is_file():
            merged.update(dotenv_values(path))

    use_profile = bool(os.environ.get("AWS_PROFILE") or merged.get("AWS_PROFILE"))

    for key, value in merged.items():
        if value is None or not str(value).strip():
            continue
        if use_profile and key in _AWS_STATIC_KEYS:
            continue
        if key not in os.environ:
            os.environ[key] = str(value).strip()

    local_path = _BACKEND_ROOT / ".env.local"
    if not local_path.is_file():
        local_path = _MONOREPO_ROOT / ".env.local"
    if local_path.is_file():
        local_vals = dotenv_values(local_path)
        use_profile = bool(
            os.environ.get("AWS_PROFILE")
            or local_vals.get("AWS_PROFILE")
            or merged.get("AWS_PROFILE")
        )
        for key, value in local_vals.items():
            if value is None or not str(value).strip():
                continue
            if use_profile and key in _AWS_STATIC_KEYS:
                continue
            if key in _CALLER_SETTABLE_KEYS and key in os.environ:
                continue
            os.environ[key] = str(value).strip()