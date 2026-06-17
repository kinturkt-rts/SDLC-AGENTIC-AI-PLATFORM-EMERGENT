---
name: security-agent
description: Vulnerability and secrets review with remediation priorities. Use when working on security-agent, dependencies, or compliance checks.
---

# Security Agent

## What this agent does

Reviews code and dependencies for vulnerabilities, secrets, and compliance gaps. Returns prioritized findings; may delegate fixes to developer-agent via A2A.

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/security-agent/security_agent.py` → `_shared/runner.py` |
| System prompt | `SECURITY_SYS_PROMPT` in `security_agent.py` |
| A2A port | 9106 |

## MCP tools

None required by default; optional SonarQube / AWS Security MCP for deeper scans.

## Run standalone

```bash
python agents/security-agent/security_agent.py --task "Audit finops-web-app dependencies"
```

## Cursor workflow

- Never commit secrets; flag `.env` leakage and hardcoded tokens.
- Severity: Critical → High → Medium → Low with concrete remediation steps.
