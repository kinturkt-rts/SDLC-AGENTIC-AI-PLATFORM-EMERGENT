"""Tests for search endpoint (vector store mocked/disabled)."""
from unittest.mock import patch


def test_search_returns_empty_when_no_vector_store(client, api_headers):
    """Without chromadb installed, search returns empty results."""
    body = {"query": "Redis connection pool", "top_k": 5}
    resp = client.post("/api/v1/search", json=body, headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_search_with_mocked_results(client, api_headers, active_runbook):
    """Mock vector store to return results."""
    mock_results = [{
        "step_id": "fake-step-id",
        "runbook_id": str(active_runbook.id),
        "service_id": str(active_runbook.service_id),
        "service_name": "test-payments-api",
        "runbook_title": active_runbook.title,
        "step_number": 1,
        "step_title": "Active Step",
        "excerpt": "Active step body text for testing.",
        "score": 0.85,
    }]
    with patch("app.services.vector_store.query_steps", return_value=mock_results):
        body = {"query": "test query"}
        resp = client.post("/api/v1/search", json=body, headers=api_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["runbook_title"] == active_runbook.title


def test_search_unauthorized(client):
    body = {"query": "test"}
    resp = client.post("/api/v1/search", json=body)
    assert resp.status_code == 401
