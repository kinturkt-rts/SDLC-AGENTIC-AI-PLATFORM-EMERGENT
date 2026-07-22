"""SHA-256 API-key seed helpers (opaque X-API-Key auth, not bcrypt).

Apps that store ``sha256(raw_key).hexdigest()`` in ``api_keys.key_hash`` (or similar)
must not invent fake ``sha256_foo_001`` strings — those never match a live lookup.
Database-agent writes labeled sentinels; apply_sql / materialize replace them with
real digests computed on the host.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# Labeled: '__SHA256_PLACEHOLDER:demo-standard__'
# Unlabeled (discouraged when UNIQUE): '__SHA256_PLACEHOLDER__'
_SHA256_LABELED_RE = re.compile(
    r"__SHA256_PLACEHOLDER:([A-Za-z0-9_-]+)__",
)
_SHA256_BARE = "__SHA256_PLACEHOLDER__"

# -- API key for demo-standard: "demo-standard-key-2024"
_API_KEY_COMMENT_RE = re.compile(
    r'--\s*API\s+key\s+for\s+([A-Za-z0-9_-]+)\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)

# Fake LLM invents: sha256_standard_demo_001 (not a 64-char hex digest)
_FAKE_SHA256_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])sha256_[A-Za-z0-9_]+(?![A-Fa-f0-9]{20})",
)

_HEX64_RE = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)


def sha256_hex(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def documented_api_keys(seed_text: str) -> dict[str, str]:
    """Parse ``-- API key for <label>: "<plaintext>"`` comments → label → plaintext."""
    return {m.group(1): m.group(2) for m in _API_KEY_COMMENT_RE.finditer(seed_text)}


def seed_text_has_sha256_placeholders(seed_text: str) -> bool:
    return _SHA256_BARE in seed_text or bool(_SHA256_LABELED_RE.search(seed_text))


def seed_text_has_fake_sha256_tokens(seed_text: str) -> bool:
    """True when seed invents non-hex ``sha256_*`` tokens (never valid digests)."""
    return bool(_FAKE_SHA256_TOKEN_RE.search(seed_text))


def is_real_sha256_hex(value: str) -> bool:
    return bool(_HEX64_RE.fullmatch((value or "").strip()))


def is_sha256_placeholder_or_fake(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    if v == _SHA256_BARE or v.startswith("__SHA256_PLACEHOLDER:"):
        return True
    if _FAKE_SHA256_TOKEN_RE.fullmatch(v):
        return True
    return False


def seed_sql_has_sha256_work(app_dir: Path) -> bool:
    """True when seed needs SHA-256 preprocess/materialize (placeholders or fakes)."""
    sql_dir = app_dir / "db" / "sql"
    if not sql_dir.is_dir():
        return False
    for seed in sorted(sql_dir.glob("*seed*.sql")):
        if "fix" in seed.name.lower():
            continue
        text = seed.read_text(encoding="utf-8")
        if seed_text_has_sha256_placeholders(text) or seed_text_has_fake_sha256_tokens(text):
            return True
    return False


def collect_documented_api_keys(app_dir: Path) -> dict[str, str]:
    """Merge API-key comments from all seed SQL files under the app."""
    sql_dir = app_dir / "db" / "sql"
    keys: dict[str, str] = {}
    if not sql_dir.is_dir():
        return keys
    for seed in sorted(sql_dir.glob("*seed*.sql")):
        if "fix" in seed.name.lower():
            continue
        keys.update(documented_api_keys(seed.read_text(encoding="utf-8")))
    return keys


def replace_sha256_placeholders(sql: str) -> tuple[str, int, list[str]]:
    """Replace labeled/bare SHA-256 placeholders with real digests.

    Returns (new_sql, replaced_count, errors).
    """
    keys = documented_api_keys(sql)
    errors: list[str] = []
    replaced = 0

    def _labeled(match: re.Match[str]) -> str:
        nonlocal replaced
        label = match.group(1)
        raw = keys.get(label)
        if not raw:
            errors.append(
                f"__SHA256_PLACEHOLDER:{label}__ without matching "
                f'`-- API key for {label}: "…"` comment'
            )
            return match.group(0)
        replaced += 1
        return sha256_hex(raw)

    # Replace inside SQL string literals first (quoted forms)
    def _sub_quoted(text: str, quote: str) -> str:
        nonlocal replaced

        def repl(m: re.Match[str]) -> str:
            nonlocal replaced
            inner = m.group(1)
            labeled = _SHA256_LABELED_RE.fullmatch(inner)
            if labeled:
                label = labeled.group(1)
                raw = keys.get(label)
                if not raw:
                    errors.append(
                        f"__SHA256_PLACEHOLDER:{label}__ without matching "
                        f'`-- API key for {label}: "…"` comment'
                    )
                    return m.group(0)
                replaced += 1
                return f"{quote}{sha256_hex(raw)}{quote}"
            if inner == _SHA256_BARE:
                # Bare placeholder: require a single documented key or password comment
                if len(keys) == 1:
                    raw = next(iter(keys.values()))
                else:
                    from _shared.verify_seed_bcrypt import documented_password

                    raw = documented_password(sql)
                if not raw:
                    errors.append(
                        f"{_SHA256_BARE} without `-- API key for <label>: \"…\"` "
                        "(or a single shared password comment)"
                    )
                    return m.group(0)
                replaced += 1
                return f"{quote}{sha256_hex(raw)}{quote}"
            return m.group(0)

        pattern = re.compile(
            rf"{re.escape(quote)}({re.escape(_SHA256_BARE)}|"
            rf"__SHA256_PLACEHOLDER:[A-Za-z0-9_-]+__){re.escape(quote)}"
        )
        return pattern.sub(repl, text)

    out = _sub_quoted(sql, "'")
    out = _sub_quoted(out, '"')

    # Also replace unquoted occurrences (defensive)
    out2 = _SHA256_LABELED_RE.sub(_labeled, out)
    return out2, replaced, errors


def validate_seed_sha256_api_keys(sql_dir: Path) -> list[str]:
    """Blocking checks for SHA-256 API-key seed rows."""
    errors: list[str] = []
    if not sql_dir.is_dir():
        return errors
    for seed in sorted(sql_dir.glob("*seed*.sql")):
        if "fix" in seed.name.lower():
            continue
        text = seed.read_text(encoding="utf-8")
        if seed_text_has_fake_sha256_tokens(text):
            errors.append(
                f"{seed.name}: invented `sha256_*` key_hash tokens are not real digests — "
                'use `__SHA256_PLACEHOLDER:<label>__` plus `-- API key for <label>: "…"` '
                "(host replaces with sha256 hex). Never invent fake sha256_… strings."
            )
        if seed_text_has_sha256_placeholders(text):
            keys = documented_api_keys(text)
            for label in _SHA256_LABELED_RE.findall(text):
                if label not in keys:
                    errors.append(
                        f"{seed.name}: __SHA256_PLACEHOLDER:{label}__ missing "
                        f'`-- API key for {label}: "…"` comment'
                    )
            if _SHA256_BARE in text and not keys:
                from _shared.verify_seed_bcrypt import documented_password

                if not documented_password(text):
                    errors.append(
                        f"{seed.name}: {_SHA256_BARE} without API key comments or "
                        "documented password"
                    )
    return errors
