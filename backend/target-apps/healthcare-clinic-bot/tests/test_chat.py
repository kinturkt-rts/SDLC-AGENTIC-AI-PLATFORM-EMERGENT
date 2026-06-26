"""Tests for chat endpoints."""
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_bedrock(monkeypatch):
    """Mock the Bedrock client to avoid live AWS calls."""
    fake = MagicMock()
    fake.invoke_text.return_value = "The clinic is open Monday to Friday 8 AM to 6 PM."
    monkeypatch.setattr("app.routers.chat.get_bedrock_client", lambda: fake)
    return fake


def test_create_session(client):
    response = client.post("/chat/sessions", json={"session_label": "Test Session"})
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert "created_at" in data


def test_create_session_no_label(client):
    response = client.post("/chat/sessions", json={})
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data


def test_send_message_session_not_found(client):
    response = client.post(
        "/chat/message",
        json={"session_id": "00000000-0000-0000-0000-000000000000", "message": "Hello"},
    )
    assert response.status_code == 404


def test_send_message_fallback(client):
    """When no FAQ matches, response should be a fallback."""
    # Create a session first
    session_resp = client.post("/chat/sessions", json={})
    session_id = session_resp.json()["session_id"]

    response = client.post(
        "/chat/message",
        json={"session_id": session_id, "message": "What is quantum physics?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_fallback"] is True
    assert "disclaimer" in data
    assert data["session_id"] == session_id


def test_send_message_with_faq_match(client, db_session):
    """When FAQ matches, Bedrock is called and response is grounded."""
    from app.models.faq_entry import FaqEntry

    faq = FaqEntry(
        category="office_hours",
        question="What are the clinic office hours?",
        answer="Open Monday to Friday 8 AM to 6 PM.",
    )
    db_session.add(faq)
    db_session.commit()

    session_resp = client.post("/chat/sessions", json={})
    session_id = session_resp.json()["session_id"]

    response = client.post(
        "/chat/message",
        json={"session_id": session_id, "message": "What are the clinic office hours?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_fallback"] is False
    assert "disclaimer" in data


def test_send_message_sensitive_data(client):
    """Sensitive data should trigger a redirect response without storing the message."""
    session_resp = client.post("/chat/sessions", json={})
    session_id = session_resp.json()["session_id"]

    response = client.post(
        "/chat/message",
        json={"session_id": session_id, "message": "My SSN is 123-45-6789"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "not able to collect" in data["reply"] or "personal medical" in data["reply"].lower()
    assert "disclaimer" in data


def test_get_session_messages(client):
    """After sending a message, messages should be retrievable."""
    session_resp = client.post("/chat/sessions", json={})
    session_id = session_resp.json()["session_id"]

    client.post(
        "/chat/message",
        json={"session_id": session_id, "message": "Hello"},
    )

    response = client.get(f"/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    messages = response.json()
    # Should have user message + assistant reply (or just assistant for fallback)
    assert len(messages) >= 1


def test_get_session_messages_not_found(client):
    response = client.get("/chat/sessions/00000000-0000-0000-0000-000000000000/messages")
    assert response.status_code == 404
