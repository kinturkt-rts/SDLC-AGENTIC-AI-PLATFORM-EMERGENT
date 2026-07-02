"""Local diagram generation tools — drop-in replacement for the yanked awslabs.aws-diagram-mcp-server.

Exposes the same three tool names the architect-agent's system prompt expects:
  awsdiagram_get_diagram_examples
  awsdiagram_list_icons
  awsdiagram_generate_diagram

No external MCP server required; uses the `diagrams` Python library + system Graphviz directly.
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from strands.tools.decorator import tool

# ---------------------------------------------------------------------------
# Pre-amble injected before the agent's DSL code
# ---------------------------------------------------------------------------

_PREAMBLE = textwrap.dedent("""
    import os as _os
    _os.makedirs(workspace_dir, exist_ok=True)
    from diagrams import Diagram, Cluster, Edge
    try:
        from diagrams.aws.compute import EC2, Lambda, ECS, Fargate, EKS, AutoScaling, ElasticBeanstalk
    except ImportError:
        pass
    try:
        from diagrams.aws.database import RDS, Aurora, Dynamodb, ElastiCache
    except ImportError:
        pass
    try:
        from diagrams.aws.network import ELB, ALB, NLB, CloudFront, Route53, APIGateway, VPC
    except ImportError:
        pass
    try:
        from diagrams.aws.storage import S3, EFS
    except ImportError:
        pass
    try:
        from diagrams.aws.security import IAM, Cognito, WAF, KMS
    except ImportError:
        pass
    try:
        from diagrams.aws.integration import SQS, SNS, Eventbridge
    except ImportError:
        pass
    try:
        from diagrams.aws.management import Cloudwatch, Cloudformation
    except ImportError:
        pass
    try:
        from diagrams.aws.analytics import Athena, Kinesis
    except ImportError:
        pass
    try:
        from diagrams.aws.devtools import CodeBuild, CodePipeline
    except ImportError:
        pass
    try:
        from diagrams.onprem.client import User, Users
    except ImportError:
        pass
    try:
        from diagrams.onprem.network import Internet
    except ImportError:
        pass
""").strip()

_EXAMPLES = {
    "aws": textwrap.dedent("""
        Example 1 — FastAPI + RDS (simple 3-tier):
        ```python
        with Diagram("Contacts API", filename=filename, show=False, direction="LR"):
            with Cluster("App"):
                user = Users("Client")
                api  = ECS("FastAPI")
            with Cluster("Data"):
                db = RDS("Postgres")
            user >> api >> db
        ```

        Example 2 — Serverless (API Gateway + Lambda + DynamoDB):
        ```python
        with Diagram("Order Service", filename=filename, show=False, direction="LR"):
            with Cluster("API"):
                gw  = APIGateway("API GW")
                fn  = Lambda("Handler")
            with Cluster("Store"):
                ddb = Dynamodb("Orders")
            gw >> fn >> ddb
        ```

        Example 3 — ECS + ALB + RDS (containerised web app):
        ```python
        with Diagram("Inventory App", filename=filename, show=False, direction="LR"):
            with Cluster("Users"):
                user = Users("Users")
                alb  = ALB("ALB")
            with Cluster("App"):
                svc = ECS("API Container")
            with Cluster("Data"):
                db  = RDS("Postgres")
                cch = ElastiCache("Redis")
            user >> alb >> svc >> db
            svc >> cch
        ```

        Rules:
        - Start with `with Diagram(` — no import lines, they are pre-imported.
        - Use `filename=filename` (variable injected by runtime, no .png suffix).
        - `show=False` always.
        - ASCII-only labels. Max 14 nodes, max 3 clusters.
    """).strip(),
}

_ICONS = textwrap.dedent("""
    # Compute
    EC2, Lambda, ECS, Fargate, EKS, AutoScaling, ElasticBeanstalk

    # Database
    RDS, Aurora, Dynamodb, ElastiCache

    # Network
    ALB, ELB, NLB, CloudFront, Route53, APIGateway, VPC

    # Storage
    S3, EFS

    # Security
    IAM, Cognito, WAF, KMS

    # Messaging
    SQS, SNS, Eventbridge

    # Management
    Cloudwatch, Cloudformation

    # Analytics
    Athena, Kinesis

    # DevTools
    CodeBuild, CodePipeline

    # Generic / on-prem
    User, Users, Internet
    Cluster, Edge  (layout helpers, not nodes)
""").strip()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def awsdiagram_get_diagram_examples(diagram_type: str = "aws") -> str:
    """Return Python DSL examples for AWS architecture diagrams.

    Args:
        diagram_type: Diagram category to fetch examples for (use "aws").

    Returns:
        Multi-line string with annotated DSL code examples.
    """
    return _EXAMPLES.get(diagram_type.lower().strip(), _EXAMPLES["aws"])


@tool
def awsdiagram_list_icons(provider: str = "aws") -> str:
    """List available icon class names for the diagrams library.

    Args:
        provider: Icon provider namespace (use "aws").

    Returns:
        Newline-separated list of class names grouped by category.
    """
    return _ICONS


@tool
def awsdiagram_generate_diagram(code: str, filename: str, workspace_dir: str) -> str:
    """Generate an AWS architecture PNG from Python DSL code using the diagrams library.

    The runtime pre-imports all common diagram classes so the `code` block must NOT
    contain import statements — start directly with `with Diagram(...)`.

    Args:
        code: Python DSL code block. Must begin with `with Diagram("Title",
              filename=filename, show=False, direction="LR"):`.
              Use `filename` (injected variable) for the output path.
        filename: Absolute POSIX path for the output PNG (no .png suffix).
                  Pass `diagramOutputFile` from context.
        workspace_dir: Directory where the PNG should be saved.
                       Pass `diagramOutputDir` from context.

    Returns:
        Absolute path of the saved PNG on success, or an error description.
    """
    script = (
        f"filename = {filename!r}\n"
        f"workspace_dir = {workspace_dir!r}\n"
        f"{_PREAMBLE}\n"
        f"{code}\n"
    )

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "ERROR: diagram generation timed out (90s)"

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        detail = stderr or stdout or "unknown error"
        return f"ERROR (exit {proc.returncode}): {detail[:1000]}"

    png_path = Path(f"{filename}.png")
    if png_path.is_file():
        return str(png_path)

    matches = glob.glob(os.path.join(workspace_dir, "**", "*.png"), recursive=True)
    if matches:
        newest = max(matches, key=os.path.getmtime)
        return newest

    return (
        f"ERROR: diagram script exited 0 but no PNG found at {filename}.png "
        f"or under {workspace_dir}. stdout={proc.stdout[:400]!r}"
    )


def local_diagram_tools() -> list[Any]:
    """Return the three local diagram tools to pass to the architect-agent."""
    return [awsdiagram_get_diagram_examples, awsdiagram_list_icons, awsdiagram_generate_diagram]