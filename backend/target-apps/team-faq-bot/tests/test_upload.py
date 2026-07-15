"""Tests for POST /api/v1/upload."""
import io
from unittest.mock import MagicMock


def test_upload_no_auth(client):
    """401 without admin API key."""
    file_content = b"Q: Test?\nA: Yes."
    response = client.post(
        "/api/v1/upload",
        files={"file": ("faq.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert response.status_code == 401


def test_upload_wrong_key(client, api_headers):
    """401 with user API key (not admin)."""
    file_content = b"Q: Test?\nA: Yes."
    response = client.post(
        "/api/v1/upload",
        files={"file": ("faq.txt", io.BytesIO(file_content), "text/plain")},
        headers=api_headers,  # user key, not admin key
    )
    assert response.status_code == 401


def test_upload_success(client, admin_headers, monkeypatch):
    """201 on valid upload with mocked Bedrock."""
    # Mock Bedrock embeddings
    mock_bedrock = MagicMock()
    mock_bedrock.invoke_embedding.return_value = [0.1] * 1024
    monkeypatch.setattr("app.routers.upload.get_bedrock_client", lambda: mock_bedrock)

    file_content = b"Q: How do I request PTO?\nA: Submit in BambooHR.\n\nQ: Deploy?\nA: Merge to main."
    response = client.post(
        "/api/v1/upload",
        files={"file": ("my-faq.txt", io.BytesIO(file_content), "text/plain")},
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "uploaded successfully" in data["message"]
    assert data["char_count"] > 0


def test_upload_too_large(client, admin_headers, monkeypatch):
    """400 when file exceeds 50000 chars."""
    # Set a low limit for testing
    monkeypatch.setenv("FAQ_MAX_CHARS", "100")
    # Clear settings cache
    from app.config import get_settings
    get_settings.cache_clear()

    mock_bedrock = MagicMock()
    monkeypatch.setattr("app.routers.upload.get_bedrock_client", lambda: mock_bedrock)

    file_content = b"x" * 200
    response = client.post(
        "/api/v1/upload",
        files={"file": ("big.txt", io.BytesIO(file_content), "text/plain")},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "exceeds maximum" in response.json()["detail"]

    # Restore
    get_settings.cache_clear()


def test_upload_empty_file(client, admin_headers, monkeypatch):
    """400 for empty file."""
    mock_bedrock = MagicMock()
    monkeypatch.setattr("app.routers.upload.get_bedrock_client", lambda: mock_bedrock)

    response = client.post(
        "/api/v1/upload",
        files={"file": ("empty.txt", io.BytesIO(b"   "), "text/plain")},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
