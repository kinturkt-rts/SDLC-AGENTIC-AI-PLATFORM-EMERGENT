---
name: web-crawler-agent
description: Crawls and extracts web/PRD content for downstream agents. Use when working on web-crawler-agent, docs/PRD ingestion, or external spec URLs.
---

# Web Crawler Agent

## What this agent does

Runs **after architect-agent** when requirements mention web scraping, URL ingestion, or external documentation. Uses **Firecrawl MCP** to scrape pages, writes normalized markdown under `docs/PRD/scraped/<target-app>/`, and optionally persists rows in Postgres (`scraped_web_content` table) via the same Postgres MCP as database-agent.

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/web-crawler/web_crawler_agent.py` |
| A2A port | 9109 |
| MCP | Firecrawl (`firecrawl-mcp` via npx); Postgres optional (`--with-postgres`) |

## Env

| Variable | Purpose |
|----------|---------|
| `FIRECRAWL_API_KEY` | Firecrawl API key (`.env.local` `Firecrawl_API_Key` also works) |
| `POSTGRES_MCP_*` | Same as database-agent when using `--with-postgres` |

## Pipeline position

```
product-agent → architect-agent → web-crawler-agent (if scrape needed) → database-agent → developer-agent
```

Detect scrape intent with `--check-only` or set `webScrapeRequired: true` / `scrapeUrls` in pipeline context JSON.

## Cursor workflow

1. Respect robots/terms; do not store credentials in repo.
2. Output markdown under `docs/PRD/scraped/` and/or Postgres `scraped_web_content`.
3. Hand off summaries to product-agent — do not create Jira tickets from crawls alone.

## CLI examples

```bash
# Check whether a task needs scraping
python agents/web-crawler/web_crawler_agent.py --check-only --task "Scrape https://example.com/docs"

# Scrape with pipeline context + Postgres persistence
python agents/web-crawler/web_crawler_agent.py \
  --target-app finops-web-app \
  --context-file agents/pipeline/finops-web-app.context.json \
  --with-postgres \
  --task "Scrape competitor pricing from https://example.com/pricing"

# A2A server
python agents/web-crawler/web_crawler_agent.py --serve-a2a --with-postgres
```