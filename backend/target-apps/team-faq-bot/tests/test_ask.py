"""Tests for POST /api/v1/ask."""
from unittest.mock import MagicMock, patch


def test_ask_no_api_key(client):
    """401 when no API key provided."""
    response = client.post("/api/v1/ask", json={"question": "test?"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_ask_answered(client, api_headers, seed_collection, monkeypatch):
    """Returns answer when Bedrock produces a cited response."""
    from app.services import faq_retriever

    # Mock retriever to return a match above threshold
    fake_match = faq_retriever.FaqMatch(
        chunk_id=1,
        heading="PTO Policy",
        chunk_text="Q: How do I request PTO?\nA: Submit in BambooHR.",
        score=0.9,
    )
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = [fake_match]

    # Patch PgVectorFaqRetriever constructor to return our mock
    monkeypatch.setattr(
        "app.routers.ask.PgVectorFaqRetriever",
        lambda db, bedrock: mock_retriever,
    )

    # Mock Bedrock client
    mock_bedrock = MagicMock()
    mock_bedrock.invoke_text.return_value = "Submit a PTO request in BambooHR at least 3 days in advance."
    monkeypatch.setattr("app.routers.ask.get_bedrock_client", lambda: mock_bedrock)

    response = client.post("/api/v1/ask", json={"question": "How do I request PTO?"}, headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Submit a PTO request in BambooHR at least 3 days in advance."
    assert data["citation"] == "PTO Policy"


def test_ask_not_in_faq(client, api_headers, seed_collection, monkeypatch):
    """Returns 'not in FAQ' when no relevant chunks."""
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = []  # no matches

    monkeypatch.setattr(
        "app.routers.ask.PgVectorFaqRetriever",
        lambda db, bedrock: mock_retriever,
    )

    mock_bedrock = MagicMock()
    monkeypatch.setattr("app.routers.ask.get_bedrock_client", lambda: mock_bedrock)

    response = client.post("/api/v1/ask", json={"question": "What is quantum computing?"}, headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "This question is not covered in the FAQ."
    assert data["citation"] is None


def test_ask_below_threshold(client, api_headers, seed_collection, monkeypatch):
    """Returns 'not in FAQ' when all matches are below confidence threshold."""
    from app.services import faq_retriever

    fake_match = faq_retriever.FaqMatch(
        chunk_id=1, heading="PTO", chunk_text="text", score=0.3,  # below 0.75 threshold
    )
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = [fake_match]

    monkeypatch.setattr(
        "app.routers.ask.PgVectorFaqRetriever",
        lambda db, bedrock: mock_retriever,
    )

    mock_bedrock = MagicMock()
    monkeypatch.setattr("app.routers.ask.get_bedrock_client", lambda: mock_bedrock)

    response = client.post("/api/v1/ask", json={"question": "something"}, headers=api_headers)
    assert response.status_code == 200
    assert response.json()["answer"] == "This question is not covered in the FAQ."
