"""RDS network preflight: AWS API + TCP:5432 + optional psycopg."""

from __future__ import annotations

import os
import socket
import sys
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env

load_repo_env()

INSTANCE = os.environ.get("POSTGRES_MCP_INSTANCE_IDENTIFIER", "agenticaidbinstance")
REGION = os.environ.get("POSTGRES_MCP_REGION", os.environ.get("AWS_REGION", "us-east-2"))
PORT = int(os.environ.get("POSTGRES_MCP_PORT", "5432"))


def _public_ip() -> str:
    try:
        with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=10) as resp:
            return resp.read().decode().strip()
    except OSError as exc:
        return f"<could not detect: {exc}>"


def _tcp(host: str, port: int, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "reachable"
    except OSError as exc:
        return False, str(exc)


def main() -> int:
    print(f"Region={REGION}  instance={INSTANCE}\n", file=sys.stderr)

    try:
        import boto3
    except ImportError:
        print("Install boto3: pip install boto3", file=sys.stderr)
        return 1

    try:
        rds = boto3.client("rds", region_name=REGION)
        ec2 = boto3.client("ec2", region_name=REGION)
        inst = rds.describe_db_instances(DBInstanceIdentifier=INSTANCE)["DBInstances"][0]
    except Exception as exc:
        print(f"AWS API failed: {exc}", file=sys.stderr)
        print("Ensure AWS_PROFILE/credentials work: aws sts get-caller-identity", file=sys.stderr)
        return 1

    host = inst["Endpoint"]["Address"]
    port = int(inst["Endpoint"]["Port"])
    public = inst.get("PubliclyAccessible", False)
    sg_ids = [g["VpcSecurityGroupId"] for g in inst.get("VpcSecurityGroups", [])]
    subnet_group = inst.get("DBSubnetGroup", {}).get("DBSubnetGroupName", "?")

    my_ip = _public_ip()
    print("--- RDS instance ---")
    print(f"  Endpoint:        {host}:{port}")
    print(f"  Public access:   {public}")
    print(f"  Subnet group:    {subnet_group}")
    print(f"  Security groups: {', '.join(sg_ids) or '(none)'}")
    print(f"  Your public IP:  {my_ip}")

    if env_host := os.environ.get("POSTGRES_MCP_DB_ENDPOINT", "").strip():
        if env_host != host:
            print(f"\n  WARNING: .env endpoint differs from AWS:")
            print(f"    .env:  {env_host}")
            print(f"    AWS:   {host}")

    print("\n--- Security group inbound (port 5432) ---")
    has_pg_from_anywhere = False
    has_my_ip = False
    if my_ip and not my_ip.startswith("<"):
        my_cidr = f"{my_ip}/32"
    else:
        my_cidr = None

    for sg_id in sg_ids:
        resp = ec2.describe_security_groups(GroupIds=[sg_id])
        for sg in resp["SecurityGroups"]:
            print(f"  [{sg_id}] {sg.get('GroupName', '')}")
            rules = sg.get("IpPermissions", [])
            pg_rules = [r for r in rules if r.get("FromPort", 0) <= 5432 <= r.get("ToPort", 65535)]
            if not pg_rules:
                print("    (no inbound rule covering port 5432)")
                continue
            for rule in pg_rules:
                for ip_range in rule.get("IpRanges", []):
                    cidr = ip_range.get("CidrIp", "")
                    desc = ip_range.get("Description", "")
                    print(f"    allow {cidr}  {desc}")
                    if cidr == "0.0.0.0/0":
                        has_pg_from_anywhere = True
                    if my_cidr and cidr == my_cidr:
                        has_my_ip = True

    print("\n--- TCP probe ---")
    ok, msg = _tcp(host, port)
    print(f"  {host}:{port} -> {msg}")

    print("\n--- Verdict ---")
    issues: list[str] = []
    if not public:
        issues.append("RDS is NOT publicly accessible — enable it (Modify instance) or use VPN/bastion.")
    if not has_pg_from_anywhere and not has_my_ip and my_cidr:
        issues.append(
            f"Add inbound rule: PostgreSQL 5432 from {my_cidr} on security group(s) above."
        )
    if not ok:
        issues.append("TCP still blocked — fix SG/public access, wait ~1 min, re-run this script.")

    if issues:
        for i, line in enumerate(issues, 1):
            print(f"  {i}. {line}")
        print("\nAfter TCP is reachable:")
        print("  python scripts/apply_sql_to_rds.py --target-app <feature>")
        print("  python scripts/postgres_mcp_smoke.py")
        return 1

    print("  Network looks OK. Run: python scripts/apply_sql_to_rds.py --target-app <feature>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
