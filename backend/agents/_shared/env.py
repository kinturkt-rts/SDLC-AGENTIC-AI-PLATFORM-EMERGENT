"""
Load .env then .env.local from monorepo root and backend/.

Priority:
  1. Merge files in order: monorepo .env, monorepo .env.local, backend .env, backend .env.local
  2. Later files override earlier for keys they define
  3. If AWS_PROFILE is set (shell or file), do NOT load static AWS_ACCESS_KEY_ID /
     AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN from files
"""

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


def load_repo_env() -> None:
    merged: dict[str, str | None] = {}
    env_paths = [
        _MONOREPO_ROOT / ".env",
        _MONOREPO_ROOT / ".env.local",
        _BACKEND_ROOT / ".env",
        _BACKEND_ROOT / ".env.local",
    ]
    for path in env_paths:
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

    # .env.local wins over .env for every key it defines (monorepo then backend).
    for local_path in (_MONOREPO_ROOT / ".env.local", _BACKEND_ROOT / ".env.local"):
        if not local_path.is_file():
            continue
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
            os.environ[key] = str(value).strip()
