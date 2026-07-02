"""Tests for web-crawler-agent helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "web-crawler" / "web_crawler_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("web_crawler_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


_mod = _load_agent_module()
content_hash = _mod.content_hash
extract_scrape_urls = _mod.extract_scrape_urls
task_requires_web_scraping = _mod.task_requires_web_scraping
url_to_filename = _mod.url_to_filename

from _shared.mcp_clients import firecrawl_api_key  # noqa: E402


def test_task_requires_web_scraping_from_keyword() -> None:
    assert task_requires_web_scraping("Please scrape competitor pricing pages") is True


def test_task_requires_web_scraping_from_context_flag() -> None:
    assert task_requires_web_scraping("Build checkout", {"webScrapeRequired": True}) is True


def test_task_requires_web_scraping_false_for_plain_task() -> None:
    assert task_requires_web_scraping("Implement FastAPI health endpoint") is False


def test_extract_scrape_urls_from_task_and_context() -> None:
    task = "Fetch https://example.com/docs and summarize"
    context = {"scrapeUrls": ["https://docs.example.com/api"]}
    urls = extract_scrape_urls(task, context)
    assert "https://example.com/docs" in urls
    assert "https://docs.example.com/api" in urls
    assert len(urls) == 2


def test_url_to_filename() -> None:
    name = url_to_filename("https://docs.example.com/api/v1/users")
    assert name.endswith(".md")
    assert "docs-example-com" in name


def test_content_hash_is_stable() -> None:
    text = "# Hello\n\nWorld"
    assert content_hash(text) == content_hash(text)
    assert len(content_hash(text)) == 64


def test_firecrawl_api_key_accepts_legacy_env_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.delenv("Firecrawl_API_Key", raising=False)
    monkeypatch.setenv("Firecrawl_API_Key", "fc-test-key")
    assert firecrawl_api_key() == "fc-test-key"


def test_task_requires_web_scraping_from_scrape_query() -> None:
    assert task_requires_web_scraping(
        "Build checkout",
        {"scrapeQuery": "AWS CUR pricing documentation 2024"},
    ) is True


def test_extract_scrape_queries_dedupes() -> None:
    queries = _mod.extract_scrape_queries(
        {"scrapeQuery": "finops benchmarks", "searchQuery": "finops benchmarks"}
    )
    assert queries == ["finops benchmarks"]


def test_scraped_output_rel_defaults_to_prd_scraped_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    rel = _mod._scraped_output_rel("inventory-app", None)
    assert rel == "docs/PRD/scraped/inventory-app"


def test_scraped_output_rel_cloud_uses_target_app_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    rel = _mod._scraped_output_rel("inventory-app", None)
    assert rel == "inventory-app/docs/PRD/scraped"


def test_artifact_rel_path_prefixes_target_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    rel = _mod._artifact_rel_path("docs/PRD/scraped/page.md", "inventory-app")
    assert rel == "inventory-app/docs/PRD/scraped/page.md"


def test_firecrawl_api_key_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("FIRECRAWL_API_KEY", "Firecrawl_API_Key", "FIRECRAWL_APIKEY"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="FIRECRAWL_API_KEY"):
        firecrawl_api_key()