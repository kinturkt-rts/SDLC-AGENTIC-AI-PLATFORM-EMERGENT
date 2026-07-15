"""Document upload and list tests."""
import io
import uuid

from app.models.collection import Collection


def _create_collection(db_session, user_id: str) -> str:
    coll = Collection(
        id=str(uuid.uuid4()),
        name=f"Col-{uuid.uuid4().hex[:8]}",
        description="test",
        created_by=user_id,
    )
    db_session.add(coll)
    db_session.commit()
    return str(coll.id)


def test_upload_document(client, contributor_headers, db_session, seed_users):
    coll_id = _create_collection(db_session, seed_users["contributor_id"])
    file_content = b"Hello world benefits summary"
    resp = client.post(
        f"/api/v1/collections/{coll_id}/documents",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        headers=contributor_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "test.txt"
    assert data["status"] == "waiting"


def test_upload_unsupported_type(client, contributor_headers, db_session, seed_users):
    coll_id = _create_collection(db_session, seed_users["contributor_id"])
    resp = client.post(
        f"/api/v1/collections/{coll_id}/documents",
        files={"file": ("data.xlsx", io.BytesIO(b"fake"), "application/vnd.ms-excel")},
        headers=contributor_headers,
    )
    assert resp.status_code == 422


def test_upload_employee_forbidden(client, employee_headers, db_session, seed_users):
    coll_id = _create_collection(db_session, seed_users["contributor_id"])
    resp = client.post(
        f"/api/v1/collections/{coll_id}/documents",
        files={"file": ("test.txt", io.BytesIO(b"hi"), "text/plain")},
        headers=employee_headers,
    )
    assert resp.status_code == 403


def test_list_documents(client, contributor_headers, db_session, seed_users):
    coll_id = _create_collection(db_session, seed_users["contributor_id"])
    # Upload a file
    client.post(
        f"/api/v1/collections/{coll_id}/documents",
        files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        headers=contributor_headers,
    )
    resp = client.get(
        f"/api/v1/collections/{coll_id}/documents",
        headers=contributor_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
