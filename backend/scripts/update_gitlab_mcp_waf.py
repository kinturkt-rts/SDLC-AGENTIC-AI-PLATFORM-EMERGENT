"""Scope CloudFront WAF CommonRuleSet away from /mcp so GitLab MCP publish works."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WEB_ACL_NAME = "CreatedByCloudFront-0a676d76"
WEB_ACL_ID = "0c9ad62c-c1ea-43b7-8390-781637eea7b9"
REGION = "us-east-1"
COMMON_RULE_NAME = "AWS-AWSManagedRulesCommonRuleSet"


def _run_aws(*args: str) -> dict:
    proc = subprocess.run(
        ["aws", *args, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    what_if = "--what-if" in sys.argv
    data = _run_aws(
        "wafv2",
        "get-web-acl",
        "--name",
        WEB_ACL_NAME,
        "--scope",
        "CLOUDFRONT",
        "--id",
        WEB_ACL_ID,
        "--region",
        REGION,
    )
    acl = data["WebACL"]
    lock_token = data["LockToken"]
    rules = acl["Rules"]
    common = next((r for r in rules if r["Name"] == COMMON_RULE_NAME), None)
    if common is None:
        print(f"Rule {COMMON_RULE_NAME} not found", file=sys.stderr)
        return 1

    mgr = common["Statement"]["ManagedRuleGroupStatement"]
    mgr.pop("ScopeDownStatement", None)
    mgr["ExcludedRules"] = [{"Name": "GenericLFI_BODY"}]

    payload = {
        "Name": acl["Name"],
        "Scope": "CLOUDFRONT",
        "Id": acl["Id"],
        "DefaultAction": acl["DefaultAction"],
        "Description": acl.get("Description") or "CloudFront WAF for GitLab MCP",
        "Rules": rules,
        "VisibilityConfig": acl["VisibilityConfig"],
        "LockToken": lock_token,
    }
    out = Path(__file__).resolve().parent / ".gitlab-mcp-waf-update.json"
    out.write_text(json.dumps(payload), encoding="utf-8")

    if what_if:
        print(f"[what-if] would update {WEB_ACL_NAME} via {out}")
        return 0

    subprocess.run(
        [
            "aws",
            "wafv2",
            "update-web-acl",
            "--cli-input-json",
            f"file://{out.as_posix()}",
            "--region",
            REGION,
        ],
        check=True,
    )
    print("WAF updated: excluded GenericLFI_BODY from AWSManagedRulesCommonRuleSet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
