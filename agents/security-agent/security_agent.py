"""Security agent — Strands + Bedrock + scoped scan tools + A2A.

Runs static analysis (bandit), dependency CVE audit (pip-audit), and a regex-based
secrets scan against target-apps/<service>/, classifies findings by severity, and
emits a structured handoff for devops-agent / developer-agent.

The agent is intentionally read-only on application code: it never edits app/ or
tests/. Its only write target is `target-apps/<service>/SECURITY_REPORT.md`.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGET_APPS = _REPO_ROOT / "target-apps"

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_design_doc_path,
    slugify,
)
from _shared.handoff_schemas import (
    DeveloperHandoff,
    HandoffValidationError,
    SecurityHandoff,
    load_handoff,
    write_handoff,
)
from _shared.telemetry import RunTelemetry, usage_from_event

load_repo_env()
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.decorator import tool

AGENT_NAME = "security-agent"
A2A_PORT = 9106

DEFAULT_PIPELINE_TASK = """\
Run a security review on targetApp using upstream handoff artifacts in Context.

**Step 1 — orient (read before scanning)**
1a. sec_list_tree(targetApp) — inventory the service; note app/, tests/, requirements.txt, .env.example.
1b. sec_read_file(designDocPath) when set — locate Auth, Rules, and Compliance sections to anchor findings.
1c. sec_read_file(qaHandoffPath) when set — note any test failures classified as security-relevant.
1d. sec_read_file(developerHandoffPath) when set — read envVarsRequired to spot secret-handling surface.

**Step 2 — run scanners (always run all four; missing tooling is itself a finding)**
2a. sec_run_bandit(targetApp) — Python SAST. Severity from bandit's HIGH/MEDIUM/LOW.
2b. sec_run_pip_audit(targetApp) — dependency CVE audit against requirements.txt.
2c. sec_run_secrets_scan(targetApp) — regex sweep for AWS keys, Slack tokens, PEM blocks, generic JWTs.
2d. sec_scan_pii(targetApp) — PII patterns in DB schemas, Pydantic models, logger/HTTPException calls.
    For each `response_schema` finding, sec_read_file the route(s) using that schema to check auth.

**Step 3 — classify and de-duplicate findings**
For each finding, assign:
- **severity** ∈ {critical, high, medium, low, info}
- **category** ∈ {sast, dependency, secret, config, compliance}
- **location** — file:line where actionable
- **remediation** — one concrete sentence

Suppress false positives WITH JUSTIFICATION. Never silently drop a real finding.

**Step 4 — write SECURITY_REPORT.md**
sec_write_file("target-apps/<service>/SECURITY_REPORT.md") with sections:
  1. Summary table (counts by severity)
  2. Critical / High findings (top of report — must-fix before deploy)
  3. Medium / Low findings (should-fix)
  4. Suppressed findings (with reason)
  5. Tooling status (each scanner: ran | missing | errored)
  6. Reproduction commands

**Step 5 — final response (LAST)**
Reply with these sections in order:
1. **status** — pass | fail | error
   - `pass` → no critical/high findings
   - `fail` → at least one critical/high finding
   - `error` → all scanners failed to run (env issue)
2. **summary** — counts by severity
3. **critical_findings** — list with category, location, remediation
4. **high_findings** — same shape
5. **tooling_status** — which scanners ran successfully
6. **recommendations** — ordered remediations for developer-agent
7. **commands** — exact shell commands to reproduce each scan
8. **handoff_json** — fenced ```json block with keys:
   targetApp, status, severityCounts, criticalCount, highCount, mediumCount, lowCount,
   findings (array), toolingStatus, reportPath, recommendations, jiraKey (or null).
   This block is consumed by devops-agent and orchestrator-agent.

Write ONLY `SECURITY_REPORT.md` under target-apps/<service>/. Never edit app/ or tests/.
"""

_READ_PREFIXES = (
    _TARGET_APPS,
    _REPO_ROOT / "docs",
    _REPO_ROOT / "agents",
    _REPO_ROOT / "inputs",
)

_written_files: list[str] = []
_last_scan_results: dict[str, dict[str, Any]] = {}

SECURITY_SYS_PROMPT = """\
You are the Security Agent for the Autonomous SDLC platform. You run **after qa-agent**
as the seventh pipeline step: product → architect → web-crawler → database → developer → qa → **YOU**.

Your job is to **find security issues** in the generated service under target-apps/<service>/.
You do NOT fix them — you classify and hand off remediations to developer-agent.

## MVP scope (current platform default)

- **In scope (Python/FastAPI services):**
  - SAST via `bandit` — flags eval/exec, hardcoded crypto, weak random, unsafe yaml.load, SQL string concat, etc.
  - Dependency CVE audit via `pip-audit` against `requirements.txt`.
  - Secrets scan — regex sweep for AWS access keys, Slack/Discord tokens, PEM private keys, generic high-entropy strings near `password`/`token`/`secret` identifiers, `Authorization: Bearer ...` literals.
- **Out of scope (Phase 2):** DAST, container image scanning, IaC scanning (Terraform → devops-agent), license compliance.

## Inputs — read ALL that are present before scanning

| Context key | Read how | What it contains |
|-------------|----------|-----------------|
| `targetApp` | Context JSON | Service folder name under target-apps/ |
| `designDocPath` | `sec_read_file` | Auth rules, secret-handling expectations, compliance scope |
| `developerHandoffPath` | `sec_read_file` | envVarsRequired — every env var is a secret surface |
| `qaHandoffPath` | `sec_read_file` | Test failures already classified as security-relevant |
| `prdPath` | `sec_read_file` | Compliance / regulatory hints (e.g. PII, HIPAA, SOC2) |

## Tools — use in this order

| Tool | Purpose |
|------|---------|
| `sec_list_tree` | List files under target-apps/<service>/ |
| `sec_read_file` | Read PRD, design, app code (read-only) |
| `sec_run_bandit` | Static analysis on Python app/ — JSON output |
| `sec_run_pip_audit` | CVE check on requirements.txt — JSON output |
| `sec_run_secrets_scan` | Regex sweep for secrets in all repo text files |
| `sec_scan_pii` | PII detection: columns in SQL, fields in Pydantic schemas, logger/HTTPException leaks |
| `sec_write_file` | Write **only** `SECURITY_REPORT.md` under the service |

## Severity classification rules

| Severity | Examples | Action |
|----------|----------|--------|
| **critical** | Hardcoded production secrets in source; RCE; SQL injection in handler; known-exploited CVE in direct dep | Block deploy. Tag developer-agent. |
| **high** | weak crypto (md5/sha1 for passwords); yaml.load (unsafe); subprocess shell=True with user input; CVE with public PoC | Fix before merge. |
| **medium** | random.random() for tokens; broad exception handlers hiding errors; missing CSRF on state-changing route; CVE with no PoC | Plan fix this sprint. |
| **low** | hardcoded test fixtures; missing security headers; dev-only DEBUG flags reachable in prod path | Acknowledge in report. |
| **info** | tooling absent (e.g. bandit not installed); informational finding | No action required. |

## False positive policy

- Suppress findings ONLY when justified (e.g. `bandit` flags `assert` in tests/ — fine).
- Suppression goes under "Suppressed findings" in the report **with one-line reason**.
- Never silently drop a real finding to make the report look clean.

## Respect documented design decisions — do not re-litigate the design

If the **design doc** explicitly states an MVP scope choice (e.g. "Single shared API key for write operations — no per-user keys", "API-key only auth — no JWT", "no rate limiting in MVP"), treat that as an **intentional decision**, not a finding. The security agent's job is to find issues with the implementation against the design, not to argue against the design itself.

Acceptable in the report:
- `info` note acknowledging the documented scope choice ("Design specifies API-key only; per-user keys / JWT deferred to Phase 2")
- Flagging an **inconsistency** between code and design (code uses per-user lookup but design says shared key — that IS a finding)

Not acceptable:
- Marking a documented scope choice as `high` / `medium` finding requiring a fix
- Listing "upgrade to JWT" as a remediation when the design explicitly chose API-key auth

## Tooling absence

If `bandit` or `pip-audit` are not installed in the agent's Python env, the scanner returns a clean error message. Document this in the report's tooling-status section AS a finding (severity: info). The agent should NOT attempt to pip-install missing scanners on its own.

## Writing rules

- Write ONLY `target-apps/<service>/SECURITY_REPORT.md` via `sec_write_file`.
- Never modify app/, tests/, requirements.txt, or .env.example — those edits belong to developer-agent.
- Read app/ via `sec_read_file` to enrich findings with code context. Do not edit.

## PII detection — proactive, not reactive

Always run `sec_scan_pii` even when PRD/design doesn't explicitly call out compliance scope. PII handling is a baseline expectation. The tool returns findings categorized by **surface**:

| Surface | What it means | How to classify |
|---------|--------------|-----------------|
| `db_schema` | PII column in SQL DDL | `medium`. Upgrade to `high` if design specifies HIPAA/PCI and DDL has no encryption note. |
| `response_schema` | PII field in a Pydantic response model | Cross-check `app/routers/` for the route that uses this schema. If the route has NO auth dependency, upgrade to `high` (PII reachable by anonymous callers). |
| `orm_model` | PII column on SQLAlchemy model | `medium` (informational — confirm encryption at rest is documented elsewhere). |
| `log_leak` | Sensitive variable interpolated into `logger.<level>(...)` | `high`. Logs are typically lower-trust than the DB. |
| `error_leak` | Sensitive variable interpolated into `HTTPException(detail=...)` | `high` — visible in 4xx response body to any caller. |

Severity is the *base*; elevate when compliance scope is named (HIPAA → patient_id leak = `critical`; PCI → credit_card field in response = `critical`).

Suppress finding when:
- The match is in `tests/` or `conftest.py` (the scanner already skips these dirs for log/error patterns; if you see one in `db/sql/` it's still real).
- The field name matches the pattern but the data isn't PII in this app's context (e.g. `phone` field on a `support_ticket` table is a callback phone — flag for review but classify `low`). Document the suppression reason.

## Compliance hints (when PRD or design mentions scope)

- **GDPR / general PII** — confirm data-retention notes in design, redaction in logs.
- **HIPAA** — flag plaintext patient data, missing audit log; elevate PII findings.
- **SOC2 / PCI** — flag missing audit log; flag absence of access-control documentation; elevate financial PII findings.

If PRD is silent on compliance, default-classify PII findings per the table above.

## Response format

Always end with **handoff_json** (fenced ```json) for orchestrator and devops-agent.
Keep prose concise; put finding details in structured `findings` array.
"""


def _resolve_repo_path(relative_path: str, *, write: bool) -> Path:
    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = (
        (_REPO_ROOT / raw).resolve()
        if not Path(raw).is_absolute()
        else Path(raw).resolve()
    )
    if not str(candidate).startswith(str(_REPO_ROOT.resolve())):
        raise ValueError(f"path must stay inside repo: {relative_path}")
    if write:
        if not str(candidate).startswith(str(_TARGET_APPS.resolve())):
            raise ValueError("writes only allowed under target-apps/")
        return candidate
    allowed = (
        any(str(candidate).startswith(str(p.resolve())) for p in _READ_PREFIXES)
        or candidate == _REPO_ROOT.resolve()
    )
    if not allowed:
        raise ValueError(f"read not allowed for path: {relative_path}")
    return candidate


def _service_dir(service: str) -> Path:
    return _TARGET_APPS / slugify(service)


def _ensure_service_exists(service: str) -> Path:
    dest = _service_dir(service)
    if not dest.is_dir():
        raise ValueError(f"service not found: target-apps/{slugify(service)}/")
    return dest


def _allowed_write_path(file_path: Path, service: str) -> bool:
    """Writes limited to SECURITY_REPORT.md under the service directory."""
    root = _service_dir(service).resolve()
    rel = file_path.resolve()
    if not str(rel).startswith(str(root)):
        return False
    rel_to_service = rel.relative_to(root)
    return rel_to_service.as_posix() == "SECURITY_REPORT.md"


def _service_python(service_dir: Path) -> str:
    """Prefer the service venv interpreter when present."""
    if os.name == "nt":
        venv_py = service_dir / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = service_dir / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def _run_subprocess(args: list[str], cwd: Path, timeout: int = 180) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return completed.returncode, completed.stdout or "", completed.stderr or ""
    except FileNotFoundError as exc:
        return 127, "", f"executable not found: {exc}"
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", f"timeout after {timeout}s"


_tool_available_cache: dict[tuple[str, str], bool] = {}


def _tool_available(python: str, module: str) -> bool:
    """Check if a Python module is importable in the given interpreter. Cached per run."""
    key = (python, module)
    if key in _tool_available_cache:
        return _tool_available_cache[key]
    rc, _, _ = _run_subprocess([python, "-c", f"import {module}"], cwd=_REPO_ROOT, timeout=15)
    _tool_available_cache[key] = rc == 0
    return _tool_available_cache[key]


# ── Scanners ─────────────────────────────────────────────────────────────────

def _run_bandit_impl(service: str) -> str:
    """Run bandit on app/ under target-apps/<service>/. JSON output for the LLM to parse."""
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return json.dumps({"tool": "bandit", "status": "error", "error": str(exc)})

    python = _service_python(service_dir)
    if not _tool_available(python, "bandit"):
        result = {
            "tool": "bandit",
            "status": "missing",
            "remediation": (
                "Install bandit in the service venv: "
                f"cd target-apps/{slugify(service)} && pip install bandit"
            ),
        }
        _last_scan_results["bandit"] = result
        return json.dumps(result)

    app_dir = service_dir / "app"
    if not app_dir.is_dir():
        result = {"tool": "bandit", "status": "skipped", "reason": "no app/ directory"}
        _last_scan_results["bandit"] = result
        return json.dumps(result)

    rc, stdout, stderr = _run_subprocess(
        [python, "-m", "bandit", "-r", "app", "-f", "json", "-q"],
        cwd=service_dir,
        timeout=120,
    )
    # bandit exits non-zero when issues are found — that is success for us.
    try:
        parsed = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {}
    findings = [
        {
            "id": item.get("test_id"),
            "name": item.get("test_name"),
            "severity": (item.get("issue_severity") or "").lower(),
            "confidence": (item.get("issue_confidence") or "").lower(),
            "file": item.get("filename"),
            "line": item.get("line_number"),
            "text": item.get("issue_text"),
        }
        for item in parsed.get("results", [])
    ]
    result = {
        "tool": "bandit",
        "status": "ran",
        "exitCode": rc,
        "findings": findings,
        "metrics": parsed.get("metrics", {}),
        "stderrTail": stderr[-2000:] if stderr else "",
    }
    _last_scan_results["bandit"] = result
    return json.dumps(result)


def _run_pip_audit_impl(service: str) -> str:
    """Run pip-audit against requirements.txt. JSON output for the LLM to parse."""
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return json.dumps({"tool": "pip-audit", "status": "error", "error": str(exc)})

    python = _service_python(service_dir)
    if not _tool_available(python, "pip_audit"):
        result = {
            "tool": "pip-audit",
            "status": "missing",
            "remediation": (
                "Install pip-audit in the service venv: "
                f"cd target-apps/{slugify(service)} && pip install pip-audit"
            ),
        }
        _last_scan_results["pip-audit"] = result
        return json.dumps(result)

    reqs = service_dir / "requirements.txt"
    if not reqs.is_file():
        result = {"tool": "pip-audit", "status": "skipped", "reason": "no requirements.txt"}
        _last_scan_results["pip-audit"] = result
        return json.dumps(result)

    rc, stdout, stderr = _run_subprocess(
        [python, "-m", "pip_audit", "-r", "requirements.txt", "-f", "json", "--strict"],
        cwd=service_dir,
        timeout=180,
    )
    try:
        parsed = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {"dependencies": []}

    findings: list[dict[str, Any]] = []
    for dep in parsed.get("dependencies", []):
        name = dep.get("name") or dep.get("package")
        version = dep.get("version")
        for vuln in dep.get("vulns", []) or []:
            findings.append(
                {
                    "package": name,
                    "version": version,
                    "id": vuln.get("id"),
                    "fixVersions": vuln.get("fix_versions", []),
                    "description": vuln.get("description", "")[:400],
                    "aliases": vuln.get("aliases", []),
                }
            )

    result = {
        "tool": "pip-audit",
        "status": "ran",
        "exitCode": rc,
        "findings": findings,
        "stderrTail": stderr[-2000:] if stderr else "",
    }
    _last_scan_results["pip-audit"] = result
    return json.dumps(result)


# Regex patterns ordered by specificity — most specific first to avoid double-flagging.
# Compiled once at import time so scanning many files doesn't re-parse the pattern strings.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = tuple(
    (name, re.compile(pattern), severity)
    for name, pattern, severity in (
        ("aws_access_key_id", r"\bAKIA[0-9A-Z]{16}\b", "high"),
        ("aws_secret_access_key", r"(?i)aws[_ ]?secret[_ ]?access[_ ]?key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?", "critical"),
        ("github_pat", r"\bghp_[A-Za-z0-9]{36,}\b", "critical"),
        ("github_pat_new", r"\bgithub_pat_[A-Za-z0-9_]{82}\b", "critical"),
        ("gitlab_pat", r"\bglpat-[A-Za-z0-9_\-]{20,}\b", "critical"),
        ("slack_bot_token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "high"),
        ("private_key_block", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----", "critical"),
        ("jwt_token", r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b", "medium"),
        ("generic_password_assignment", r"(?i)\b(password|passwd|pwd)\s*=\s*['\"][^'\"\n]{6,}['\"]", "medium"),
        ("generic_api_key_assignment", r"(?i)\b(api[_-]?key|secret[_-]?key)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "high"),
    )
)

_SECRETS_SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml", ".toml",
    ".env", ".ini", ".cfg", ".sh", ".ps1", ".md", ".sql", ".tf",
}
_SECRETS_SCAN_SKIP_DIRS = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".git"}
_SECRETS_SCAN_SKIP_BASENAMES = {".env.example"}  # canonical example file is fine
_SECRETS_SCAN_MAX_BYTES = 1_000_000  # 1 MB — anything bigger is likely generated/binary
# Filename patterns where "password = ..." / API keys are intentional test fixtures.
_SECRETS_SCAN_TEST_PATH_HINTS = ("/tests/", "/test_", "conftest.py")


def _run_secrets_scan_impl(service: str) -> str:
    """Regex-based secrets scan across the service tree. No external deps required."""
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return json.dumps({"tool": "secrets-scan", "status": "error", "error": str(exc)})

    findings: list[dict[str, Any]] = []
    files_scanned = 0
    files_skipped_large = 0
    for path in service_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SECRETS_SCAN_SKIP_DIRS for part in path.parts):
            continue
        if path.name in _SECRETS_SCAN_SKIP_BASENAMES:
            continue
        if path.suffix and path.suffix not in _SECRETS_SCAN_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > _SECRETS_SCAN_MAX_BYTES:
                files_skipped_large += 1
                continue
        except OSError:
            continue
        rel = path.relative_to(_REPO_ROOT).as_posix()
        is_test_file = any(hint in rel for hint in _SECRETS_SCAN_TEST_PATH_HINTS)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_scanned += 1

        # Pre-compute newline positions once → O(n+m) line lookups instead of O(n*m).
        newline_positions: list[int] | None = None

        def _line_for(offset: int) -> int:
            nonlocal newline_positions
            if newline_positions is None:
                newline_positions = [i for i, ch in enumerate(text) if ch == "\n"]
            # bisect: count of newlines before offset = line index (0-based); +1 for human line.
            return bisect.bisect_left(newline_positions, offset) + 1

        for name, compiled, severity in _SECRET_PATTERNS:
            # Test fixtures legitimately use placeholder credentials — skip generic patterns there.
            if is_test_file and name in {"generic_password_assignment", "generic_api_key_assignment"}:
                continue
            for match in compiled.finditer(text):
                snippet = match.group(0)
                # Redact so the report never echoes the secret itself.
                if len(snippet) > 12:
                    snippet = snippet[:4] + "…" + snippet[-2:]
                findings.append(
                    {
                        "rule": name,
                        "severity": severity,
                        "file": rel,
                        "line": _line_for(match.start()),
                        "match": snippet,
                    }
                )

    result = {
        "tool": "secrets-scan",
        "status": "ran",
        "filesScanned": files_scanned,
        "filesSkippedLarge": files_skipped_large,
        "findings": findings,
    }
    _last_scan_results["secrets-scan"] = result
    return json.dumps(result)


# ── PII scanner ──────────────────────────────────────────────────────────────

# PII field-name patterns. The token is matched as a whole word, case-insensitive.
# `severity` is the *base* severity; the LLM upgrades to `high` when the field is
# exposed on an unauthenticated route (it has the route auth context, the scanner
# does not).
_PII_FIELD_PATTERNS: tuple[tuple[str, str, str], ...] = (
    # National IDs
    ("national_id", r"(?i)\b(ssn|social_security_number|sin|tin|nid|aadhaar|passport_number|drivers_license|national_id)\b", "high"),
    # Financial
    ("financial", r"(?i)\b(credit_card|credit_card_number|card_number|cvv|cvc|iban|bank_account|account_number|routing_number|tax_id)\b", "high"),
    # Health
    ("health", r"(?i)\b(medical_record|health_insurance|patient_id|diagnosis|prescription|mrn)\b", "high"),
    # Date of birth (commonly used for identity confirmation)
    ("dob", r"(?i)\b(date_of_birth|dob|birth_date|birthdate)\b", "medium"),
    # Contact PII
    ("contact", r"(?i)\b(email|email_address|phone_number|home_phone|mobile|cell_phone)\b", "medium"),
    # Location PII (more granular than country)
    ("location", r"(?i)\b(street_address|home_address|mailing_address|zip_code|postal_code|latitude|longitude|gps_coordinates)\b", "medium"),
    # Other sensitive
    ("auth_secrets", r"(?i)\b(password_hash|mother_maiden|security_question|security_answer)\b", "medium"),
)

_PII_LOG_INTERPOLATION = re.compile(
    r"(?:logger|logging|log)\.\w+\([^)]*\{?\s*(?P<var>\w+)",
    re.IGNORECASE,
)
_PII_HTTPEXC_INTERPOLATION = re.compile(
    r"HTTPException\([^)]*detail\s*=\s*[fF]?['\"][^'\"]*\{(?P<var>\w+)",
)

_PII_SENSITIVE_VAR_NAMES = re.compile(
    r"(?i)\b(ssn|email|phone|password|dob|birth|address|credit|card|cvv|patient|medical|aadhaar|passport|national_id|tax_id|iban)\b"
)

_PII_SCAN_DIRS = ("db/sql", "app/models", "app/routers", "schemas", "app/services")
_PII_SCAN_EXTS = {".sql", ".py"}


def _run_pii_scan_impl(service: str) -> str:
    """Pattern-based PII detection across SQL, ORM models, schemas, routers, services.

    Categorizes each finding by surface (db_schema, response_schema, log_leak, error_leak)
    so the LLM can correlate response_schema findings with route auth dependencies.
    """
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return json.dumps({"tool": "pii-scan", "status": "error", "error": str(exc)})

    findings: list[dict[str, Any]] = []
    files_scanned = 0

    for sub in _PII_SCAN_DIRS:
        base = service_dir / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in _PII_SCAN_EXTS:
                continue
            if any(part in _SECRETS_SCAN_SKIP_DIRS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files_scanned += 1
            rel = path.relative_to(_REPO_ROOT).as_posix()

            # Pre-compute newline offsets once for fast line lookups.
            newline_positions = [i for i, ch in enumerate(text) if ch == "\n"]

            def _line_for(offset: int) -> int:
                return bisect.bisect_left(newline_positions, offset) + 1

            # Determine the "surface" of this file — drives how findings are categorized.
            if "/db/sql/" in rel:
                surface = "db_schema"
            elif "/schemas/" in rel or "/schema/" in rel:
                surface = "response_schema"
            elif "/app/routers/" in rel:
                surface = "router"
            elif "/app/models/" in rel:
                surface = "orm_model"
            else:
                surface = "service"

            # 1. PII field/column name matches across all in-scope files.
            for name, pattern, severity in _PII_FIELD_PATTERNS:
                for match in re.finditer(pattern, text):
                    findings.append(
                        {
                            "category": name,
                            "surface": surface,
                            "severity": severity,
                            "file": rel,
                            "line": _line_for(match.start()),
                            "match": match.group(0),
                            "hint": (
                                "Exposed via response schema — verify route auth"
                                if surface == "response_schema"
                                else (
                                    "PII column — confirm encryption at rest + access control"
                                    if surface == "db_schema"
                                    else "PII field present — verify handling rules"
                                )
                            ),
                        }
                    )

            # 2. PII interpolation in logger calls (router/service files only).
            if surface in {"router", "service"}:
                for match in _PII_LOG_INTERPOLATION.finditer(text):
                    var = match.group("var") or ""
                    if _PII_SENSITIVE_VAR_NAMES.search(var):
                        findings.append(
                            {
                                "category": "log_leak",
                                "surface": surface,
                                "severity": "medium",
                                "file": rel,
                                "line": _line_for(match.start()),
                                "match": f"logger.…({var}…)",
                                "hint": "Logging a sensitive variable — redact or remove",
                            }
                        )

            # 3. PII interpolation in HTTPException detail (router files).
            if surface == "router":
                for match in _PII_HTTPEXC_INTERPOLATION.finditer(text):
                    var = match.group("var") or ""
                    if _PII_SENSITIVE_VAR_NAMES.search(var):
                        findings.append(
                            {
                                "category": "error_leak",
                                "surface": surface,
                                "severity": "high",
                                "file": rel,
                                "line": _line_for(match.start()),
                                "match": f"HTTPException(detail=…{{{var}}}…)",
                                "hint": "PII in 4xx response body — unauthenticated callers may see this",
                            }
                        )

    result = {
        "tool": "pii-scan",
        "status": "ran",
        "filesScanned": files_scanned,
        "findings": findings,
    }
    _last_scan_results["pii-scan"] = result
    return json.dumps(result)


# ── Tools (Strands) ──────────────────────────────────────────────────────────

@tool
def sec_list_tree(service: str, subpath: str = "") -> str:
    """List files under target-apps/<service>/ (optionally under subpath)."""
    try:
        root = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"
    base = (root / subpath).resolve()
    if not str(base).startswith(str(root.resolve())):
        return "Error: subpath escapes service directory"
    if not base.exists():
        return f"Error: not found: {base.relative_to(_REPO_ROOT).as_posix()}"
    lines: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and ".venv" not in path.parts:
            lines.append(path.relative_to(_REPO_ROOT).as_posix())
    return "\n".join(lines) if lines else "(no files)"


@tool
def sec_read_file(path: str) -> str:
    """Read a repo file. Allowed: target-apps/, docs/, agents/, inputs/."""
    try:
        file_path = _resolve_repo_path(path, write=False)
    except ValueError as exc:
        return f"Error: {exc}"
    if not file_path.is_file():
        return f"Error: not a file: {path}"
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: binary or non-utf8 file: {path}"
    if len(text) > 120_000:
        return text[:120_000] + "\n\n... (truncated)"
    return text


@tool
def sec_write_file(path: str, content: str) -> str:
    """Write SECURITY_REPORT.md under target-apps/<service>/. No other writes allowed."""
    try:
        file_path = _resolve_repo_path(path, write=True)
    except ValueError as exc:
        return f"Error: {exc}"

    parts = file_path.relative_to(_TARGET_APPS).parts
    if not parts:
        return "Error: cannot write at target-apps/ root"
    service = parts[0]
    if not _allowed_write_path(file_path, service):
        return "Error: writes limited to SECURITY_REPORT.md under the service directory"

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8", newline="\n")
    rel = file_path.relative_to(_REPO_ROOT).as_posix()
    if rel not in _written_files:
        _written_files.append(rel)
    return f"wrote {rel} ({len(content)} chars)"


@tool
def sec_run_bandit(service: str) -> str:
    """Run bandit SAST on the service's app/ directory. Returns JSON."""
    return _run_bandit_impl(service)


@tool
def sec_run_pip_audit(service: str) -> str:
    """Run pip-audit against the service's requirements.txt. Returns JSON."""
    return _run_pip_audit_impl(service)


@tool
def sec_run_secrets_scan(service: str) -> str:
    """Regex-based secrets scan across the service tree. Returns JSON."""
    return _run_secrets_scan_impl(service)


@tool
def sec_scan_pii(service: str) -> str:
    """Pattern-based PII detection in db/sql, app/models, schemas, app/routers, app/services.

    Returns categorized findings:
      - db_schema      : PII column names in SQL DDL
      - response_schema: PII fields in Pydantic response schemas (LLM must check route auth)
      - orm_model     : PII columns in SQLAlchemy models
      - log_leak       : PII variables interpolated in logger calls
      - error_leak     : PII variables interpolated in HTTPException detail (response body)
    """
    return _run_pii_scan_impl(service)


# ── Model + agent ────────────────────────────────────────────────────────────

class _SecurityCallbackHandler:
    """Stream tool progress to stderr and feed telemetry."""

    def __init__(self, telemetry: RunTelemetry | None = None) -> None:
        self.telemetry = telemetry

    def __call__(self, **kwargs: Any) -> None:
        event = kwargs.get("event", {})
        tool_use = (
            event.get("contentBlockStart", {}).get("start", {}).get("toolUse")
        )
        if tool_use:
            name = tool_use.get("name", "<unknown>")
            if self.telemetry is not None:
                self.telemetry.record_tool(name)
                print(
                    f"\n[security-agent] Tool #{self.telemetry.tool_count}: {name}",
                    file=sys.stderr,
                )
            else:
                print(f"\n[security-agent] Tool: {name}", file=sys.stderr)

        # Capture Bedrock usage tokens from metadata events.
        if self.telemetry is not None:
            usage = usage_from_event(kwargs) or usage_from_event(event)
            if usage:
                self.telemetry.record_usage(usage)


def _max_output_tokens() -> int:
    return int(
        os.getenv(
            "SECURITY_AGENT_MAX_TOKENS",
            os.getenv("BEDROCK_MAX_OUTPUT_TOKENS", "16384"),
        )
    )


def _security_model() -> BedrockModel:
    model_id = os.getenv(
        "SECURITY_MODEL_ID",
        os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
    )
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    return BedrockModel(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        max_tokens=_max_output_tokens(),
        streaming=True,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
        boto_client_config=botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )


def _build_agent(telemetry: RunTelemetry | None = None) -> Agent:
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description=(
            "Runs bandit (SAST), pip-audit (CVE), and a regex secrets scan on target-apps "
            "services, classifies findings by severity, and produces a structured handoff "
            "for devops-agent and developer-agent."
        ),
        model=_security_model(),
        system_prompt=SECURITY_SYS_PROMPT,
        tools=[
            sec_list_tree,
            sec_read_file,
            sec_write_file,
            sec_run_bandit,
            sec_run_pip_audit,
            sec_run_secrets_scan,
            sec_scan_pii,
        ],
        callback_handler=_SecurityCallbackHandler(telemetry),
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _enrich_security_context(ctx: dict[str, Any]) -> None:
    """Add security-specific paths from upstream handoffs."""
    app = slugify(str(ctx["targetApp"]))
    service_dir = _REPO_ROOT / "target-apps" / app

    ctx.setdefault("targetAppDir", service_dir.relative_to(_REPO_ROOT).as_posix())
    ctx.setdefault(
        "banditCommand",
        f"cd target-apps/{app} && python -m bandit -r app -q",
    )
    ctx.setdefault(
        "pipAuditCommand",
        f"cd target-apps/{app} && python -m pip_audit -r requirements.txt",
    )

    if not ctx.get("developerHandoffPath"):
        candidate = _REPO_ROOT / "agents" / "pipeline" / f"{app}.developer-handoff.json"
        if candidate.is_file():
            ctx["developerHandoffPath"] = candidate.relative_to(_REPO_ROOT).as_posix()

    # Validate the developer handoff up front — fail loud if upstream schema drifted.
    dev_path = ctx.get("developerHandoffPath")
    if dev_path:
        try:
            dev = load_handoff(dev_path, DeveloperHandoff)
            # Surface a few high-signal fields into context for the LLM to use directly.
            if dev.deploymentHandoff and dev.deploymentHandoff.envVarNames:
                ctx.setdefault("envVarNames", dev.deploymentHandoff.envVarNames)
            if dev.runCommand:
                ctx.setdefault("upstreamRunCommand", dev.runCommand)
        except HandoffValidationError as exc:
            print(
                f"[security-agent] WARNING: developer handoff schema mismatch — "
                f"continuing with raw context. Details: {exc}",
                file=sys.stderr,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"[security-agent] WARNING: could not load dev handoff: {exc}", file=sys.stderr)

    if not ctx.get("qaHandoffPath"):
        candidate = _REPO_ROOT / "agents" / "pipeline" / f"{app}.qa-handoff.json"
        if candidate.is_file():
            ctx["qaHandoffPath"] = candidate.relative_to(_REPO_ROOT).as_posix()


def _build_context(
    *,
    target_app: str,
    jira_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    service_path = _ensure_service_exists(target_app)
    ctx: dict[str, Any] = {
        "targetApp": target_app,
        "targetAppDir": service_path.relative_to(_REPO_ROOT).as_posix(),
    }
    if jira_key:
        ctx["jiraKey"] = jira_key
    if extra:
        ctx.update(extra)
    return ctx


def _write_security_handoff(app: str, payload: dict[str, Any]) -> str:
    """Validate the payload against SecurityHandoff before writing.

    If validation fails, fall back to writing the raw dict but log a loud warning —
    downstream agents will still get *something*, just not a guaranteed-shape file.
    """
    try:
        model = SecurityHandoff.model_validate(payload)
        out = write_handoff(model, slugify(app), "security-handoff")
    except Exception as exc:
        print(
            f"[security-agent] WARNING: handoff payload failed SecurityHandoff validation; "
            f"writing raw dict. Cause: {exc}",
            file=sys.stderr,
        )
        pipeline_dir = _REPO_ROOT / "agents" / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        out = pipeline_dir / f"{slugify(app)}.security-handoff.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out.relative_to(_REPO_ROOT).as_posix()


def _aggregate_scan_summary() -> dict[str, Any]:
    """Combine the three scanner results into a single counts/findings payload."""
    severity_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    all_findings: list[dict[str, Any]] = []
    tooling_status: dict[str, str] = {}

    for tool_name, result in _last_scan_results.items():
        tooling_status[tool_name] = result.get("status", "unknown")
        for f in result.get("findings", []) or []:
            sev = (f.get("severity") or "info").lower()
            if sev not in severity_counts:
                sev = "info"
            severity_counts[sev] += 1
            all_findings.append({"tool": tool_name, **f})

    return {
        "severityCounts": severity_counts,
        "findings": all_findings,
        "toolingStatus": tooling_status,
    }


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    jira_key: str | None = None,
) -> tuple[str, list[str], str | None]:
    global _written_files, _last_scan_results
    _written_files = []
    _last_scan_results = {}

    app = target_app or (context or {}).get("targetApp")
    if not app:
        raise TargetAppRequiredError("--target-app or context.targetApp required")
    app = slugify(str(app))

    ctx = context if context is not None else _build_context(target_app=app, jira_key=jira_key)
    ctx.setdefault("targetApp", app)
    ctx.setdefault("targetAppDir", _ensure_service_exists(app).relative_to(_REPO_ROOT).as_posix())

    enrich_handoff_context(ctx, include_db_paths=True)
    _enrich_security_context(ctx)

    if jira_key:
        ctx.setdefault("jiraKey", jira_key)

    telemetry = RunTelemetry(AGENT_NAME, target_app=app)
    agent = _build_agent(telemetry)
    summary = str(agent(_user_message(task, ctx)))

    aggregate = _aggregate_scan_summary()
    counts = aggregate["severityCounts"]
    status = "pass"
    if counts["critical"] > 0 or counts["high"] > 0:
        status = "fail"
    if not aggregate["toolingStatus"] or all(
        v in {"error", "missing"} for v in aggregate["toolingStatus"].values()
    ):
        status = "error"

    handoff: dict[str, Any] = {
        "targetApp": app,
        "status": status,
        "severityCounts": counts,
        "criticalCount": counts["critical"],
        "highCount": counts["high"],
        "mediumCount": counts["medium"],
        "lowCount": counts["low"],
        "findings": aggregate["findings"],
        "toolingStatus": aggregate["toolingStatus"],
        "reportPath": next(
            (p for p in _written_files if p.endswith("SECURITY_REPORT.md")), None
        ),
        "writtenFiles": _written_files,
        "jiraKey": ctx.get("jiraKey"),
        "designDocPath": ctx.get("designDocPath"),
        "prdPath": ctx.get("prdPath"),
    }
    handoff_rel = _write_security_handoff(app, handoff)

    # Telemetry: surface tokens, cache hits, wall-clock; persist for next-run delta.
    telemetry.extra = {
        "scanners": {k: v.get("status") for k, v in _last_scan_results.items()},
        "severityCounts": counts,
    }
    telemetry.print_summary()
    telemetry.persist()

    return summary, list(_written_files), handoff_rel


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    skills = [
        AgentSkill(
            id="security_review",
            name="security_review",
            description=(
                "Run SAST + dependency CVE audit + secrets scan on a target-apps service "
                "and produce a structured findings report."
            ),
            tags=["security", "sast", "cve", "secrets", "fastapi", "python"],
        )
    ]
    agent = _build_agent()
    A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Security agent — Strands + Bedrock + scan tools")
    parser.add_argument("--task", help="Optional task override. Default: full pipeline task.")
    parser.add_argument(
        "--target-app",
        help="Service folder under target-apps/ (or context targetApp / SECURITY_TARGET_APP env).",
    )
    parser.add_argument(
        "--no-auto-context",
        action="store_true",
        help="Do not load agents/pipeline/<target-app>.context.json automatically.",
    )
    parser.add_argument("--jira-key", help="Jira key (e.g. SAAP-3)")
    load_context_extra(parser)
    parser.add_argument(
        "--serve-a2a", action="store_true", help=f"Start A2A server on :{A2A_PORT}"
    )
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    if not args.task:
        args.task = DEFAULT_PIPELINE_TASK

    try:
        extra, target = resolve_cli_context(
            args.target_app,
            parse_context_args(args),
            no_auto_context=args.no_auto_context,
            env_var="SECURITY_TARGET_APP",
        )
    except TargetAppRequiredError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if extra.get("_contextFile"):
        print(f"[security-agent] Context (auto): {extra['_contextFile']}", file=sys.stderr)

    enrich_handoff_context(extra, include_db_paths=True)
    _enrich_security_context(extra)

    ctx = _build_context(target_app=target, jira_key=args.jira_key, extra=extra or None)

    model_id = os.getenv(
        "SECURITY_MODEL_ID",
        os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
    )
    print("", file=sys.stderr)
    print("=" * 64, file=sys.stderr)
    print(f"  AGENT: {AGENT_NAME}  |  prompt-cache: auto  |  cache_tools: default", file=sys.stderr)
    print("=" * 64, file=sys.stderr)
    print(f"[security-agent] Model      : {model_id}", file=sys.stderr)
    print(f"[security-agent] Target app : {ctx['targetAppDir']}", file=sys.stderr)
    print(f"[security-agent] Design doc : {resolve_design_doc_path(ctx)}", file=sys.stderr)
    if ctx.get("developerHandoffPath"):
        print(f"[security-agent] Dev handoff: {ctx['developerHandoffPath']}", file=sys.stderr)
    if ctx.get("qaHandoffPath"):
        print(f"[security-agent] QA handoff : {ctx['qaHandoffPath']}", file=sys.stderr)
    print("[security-agent] Running...", file=sys.stderr)

    result, written, handoff_rel = run_task(
        args.task,
        ctx,
        target_app=target,
        jira_key=args.jira_key,
    )
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(result)
    if written:
        print(
            f"[security-agent] Wrote {len(written)} file(s) under {ctx['targetAppDir']}/",
            file=sys.stderr,
        )
    if handoff_rel:
        print(f"[security-agent] Handoff   : {handoff_rel}", file=sys.stderr)


if __name__ == "__main__":
    main()
