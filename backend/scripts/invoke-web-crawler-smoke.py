"""Smoke invoke for web-crawler-agent AgentCore runtime (Firecrawl MCP, standalone).

Example:
  python scripts/invoke-web-crawler-smoke.py --app demo-api --run-id wc-smoke-1 \\
    --url https://example.com
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a


def _build_task(*, target_app: str, run_id: str, url: str, query: str) -> str:
    context: dict[str, object] = {
        "targetApp": target_app,
        "runId": run_id,
        "webScrapeRequired": True,
        "scrapedOutputDir": f"{target_app}/docs/PRD/scraped",
    }
    if url:
        context["scrapeUrls"] = [url]
    if query:
        context["scrapeQuery"] = query

    task = (
        "Scrape the requested web content via Firecrawl and persist markdown.\n"
        "Call wc_set_handoff_context with the Context JSON first, then scrape and write files.\n"
    )
    if url:
        task += f"\nPrimary URL: {url}\n"
    if query:
        task += f"\nSearch query: {query}\n"
    return f"{task}\nContext:\n{json.dumps(context, indent=2)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke web-crawler-agent on AgentCore")
    parser.add_argument("--app", required=True, help="Target app slug (artifact prefix)")
    parser.add_argument("--run-id", required=True, help="Run ID for S3 artifact prefix")
    parser.add_argument("--url", default="https://example.com", help="URL to scrape")
    parser.add_argument("--query", default="", help="Optional firecrawl_search query instead of URL")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    message = _build_task(
        target_app=args.app,
        run_id=args.run_id,
        url=args.url.strip(),
        query=args.query.strip(),
    )
    print(f"Invoking web-crawler-agent (runId={args.run_id})...")
    result = invoke_agent_runtime_a2a("web-crawler-agent", message, timeout=args.timeout)
    if result.get("status") != "success":
        print(json.dumps(result, indent=2), file=sys.stderr)
        raise SystemExit(1)

    text = result.get("text") or extract_text_from_a2a_jsonrpc(result.get("response") or {})
    print(text)
    print(f"\nArtifacts (if successful): s3://<bucket>/runs/{args.run_id}/{args.app}/docs/PRD/scraped/")


if __name__ == "__main__":
    main()
