"""Q&A (ask) endpoint tests with mocked Bedrock."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.models.collection import Collection
from app.models.document import Document
from app.models.document_chunk import DocumentChunk


@pytest.fixture()
def mock_bedrock(monkeypatch):
    fake = MagicMock()
    fake.invoke_text.return_value = "The deductible is $500."
    fake.invoke_embed.return_value = [0.0] * 1024
    monkeypatch.setattr("app.routers.collections.get_bedrock_client", lambda: fake)
    return fake


def _seed_collection_with_chunks(db_session, user_id: str) -> str:
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    coll = Collection(
        id=coll_id,
        name=f"QACol-{coll_id[:8]}",
        description="test",
        created_by=user_id,
    )
    doc = Document(
        id=doc_id,
        collection_id=coll_id,
        filename="benefits.pdf",
        file_type="application/pdf",
        status="ready",
        uploaded_by=user_id,
    )
    chunk = DocumentChunk(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        chunk_index=0,
        chunk_text="The PPO Standard plan has a $500 individual deductible.",
    )
    db_session.add_all([coll, doc, chunk])
    db_session.commit()
    return coll_id


def test_ask_question_with_answer(client, employee_headers, db_session, seed_users, mock_bedrock):
    coll_id = _seed_collection_with_chunks(db_session, seed_users["contributor_id"])
    resp = client.post(
        f"/api/v1/collections/{coll_id}/ask",
        json={"question": "What is the deductible?"},
        headers=employee_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "citations" in data
    assert data["answer"] == "The deductible is $500."
    assert len(data["citations"]) >= 1


def test_ask_question_not_found(client, employee_headers, db_session, seed_users, monkeypatch):
    coll_id = str(uuid.uuid4())
    coll = Collection(
        id=coll_id,
        name=f"Empty-{coll_id[:8]}",
        description="empty",
        created_by=seed_users["contributor_id"],
    )
    db_session.add(coll)
    db_session.commit()

    fake = MagicMock()
    fake.invoke_embed.return_value = [0.0] * 1024
    monkeypatch.setattr("app.routers.collections.get_bedrock_client", lambda: fake)

    resp = client.post(
        f"/api/v1/collections/{coll_id}/ask",
        json={"question": "Random question?"},
        headers=employee_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Not found in documents"
    assert data["citations"] == []


def test_ask_collection_not_found(client, employee_headers, seed_users, mock_bedrock):
    resp = client.post(
        f"/api/v1/collections/{str(uuid.uuid4())}/ask",
        json={"question": "test"},
        headers=employee_headers,
    )
    assert resp.status_code == 404
