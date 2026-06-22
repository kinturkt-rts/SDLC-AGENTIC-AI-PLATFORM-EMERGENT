"""Tests for Bug endpoints."""
import uuid


def test_create_bug_returns_201(client, standard_headers):
    resp = client.post(
        "/bugs",
        json={"title": "Test bug", "description": "A test description"},
        headers=standard_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "bug" in data
    assert data["bug"]["title"] == "Test bug"
    assert data["bug"]["status"] == "open"
    assert "similar_bugs" in data
    assert isinstance(data["similar_bugs"], list)
    assert "likely_duplicate" in data
    assert isinstance(data["likely_duplicate"], bool)


def test_create_bug_no_auth_returns_401(client):
    resp = client.post(
        "/bugs",
        json={"title": "Test", "description": "desc"},
    )
    assert resp.status_code == 401


def test_create_bug_invalid_key_returns_401(client):
    resp = client.post(
        "/bugs",
        json={"title": "Test", "description": "desc"},
        headers={"X-API-Key": "bad-key"},
    )
    assert resp.status_code == 401


def test_get_bug_by_id(client, standard_headers, sample_bug):
    resp = client.get(f"/bugs/{sample_bug['id']}", headers=standard_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sample_bug["id"]
    assert data["title"] == sample_bug["title"]
    assert "embedding" not in data


def test_get_bug_not_found(client, standard_headers):
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/bugs/{fake_id}", headers=standard_headers)
    assert resp.status_code == 404


def test_patch_bug_title_only(client, standard_headers, sample_bug):
    resp = client.patch(
        f"/bugs/{sample_bug['id']}",
        json={"title": "Updated title"},
        headers=standard_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bug"]["title"] == "Updated title"


def test_patch_bug_description_reembed(client, standard_headers, sample_bug, mock_bedrock):
    resp = client.patch(
        f"/bugs/{sample_bug['id']}",
        json={"description": "New description with different content"},
        headers=standard_headers,
    )
    assert resp.status_code == 200
    # Bedrock was called for re-embed
    mock_bedrock.embed.assert_called()


def test_mark_duplicate_admin(client, admin_headers, db_session):
    from app.models.bug import Bug
    # Create two bugs
    bug1_id = str(uuid.uuid4())
    bug2_id = str(uuid.uuid4())
    bug1 = Bug(id=bug1_id, title="Bug 1", description="Desc 1", status="open")
    bug2 = Bug(id=bug2_id, title="Bug 2", description="Desc 2", status="open")
    db_session.add_all([bug1, bug2])
    db_session.commit()

    resp = client.post(
        f"/bugs/{bug2_id}/duplicate",
        json={"canonical_bug_id": bug1_id},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "duplicate"
    assert data["duplicate_of"] == bug1_id


def test_mark_duplicate_standard_returns_403(client, standard_headers, sample_bug):
    fake_canonical = str(uuid.uuid4())
    resp = client.post(
        f"/bugs/{sample_bug['id']}/duplicate",
        json={"canonical_bug_id": fake_canonical},
        headers=standard_headers,
    )
    assert resp.status_code == 403


def test_resolve_bug_admin(client, admin_headers, db_session):
    from app.models.bug import Bug
    bug_id = str(uuid.uuid4())
    bug = Bug(id=bug_id, title="Bug to resolve", description="Desc", status="open")
    db_session.add(bug)
    db_session.commit()

    resp = client.post(f"/bugs/{bug_id}/resolve", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"


def test_resolve_bug_standard_returns_403(client, standard_headers, sample_bug):
    resp = client.post(f"/bugs/{sample_bug['id']}/resolve", headers=standard_headers)
    assert resp.status_code == 403


def test_health_no_auth_required(client):
    """GET /health should not require auth."""
    resp = client.get("/health")
    assert resp.status_code == 200
