"""Tests for finding endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.models.audit import Audit
from app.models.finding import Finding


@pytest.fixture
def sample_audit(db_session, seeded_users):
    """Create a sample audit for testing."""
    audit = Audit(
        title="Test Audit",
        description="Test audit description",
        created_by=seeded_users["auditor"]["id"]
    )
    db_session.add(audit)
    db_session.commit()
    db_session.refresh(audit)
    return audit


@pytest.fixture
def sample_finding(db_session, sample_audit, seeded_users):
    """Create a sample finding for testing.

    Also creates the initial status_history row that the POST /findings route
    would create — without this, the history test sees an empty list.
    """
    from app.models.status_history import StatusHistory

    finding = Finding(
        audit_id=sample_audit.id,
        title="Test Finding",
        description="Test finding description",
        severity="medium",
        status="draft",
        assigned_to=seeded_users["assignee"]["id"],
        created_by=seeded_users["auditor"]["id"]
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    initial_history = StatusHistory(
        finding_id=finding.id,
        from_status=None,
        to_status="draft",
        changed_by=seeded_users["auditor"]["id"],
        comment="Finding created"
    )
    db_session.add(initial_history)
    db_session.commit()

    return finding


def test_list_findings_auditor(client: TestClient, auth_headers, seeded_users, sample_finding):
    """Test auditor can list all findings."""
    headers = auth_headers("auditor")
    
    response = client.get("/api/v1/findings/", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "findings" in data
    assert "total" in data
    assert len(data["findings"]) >= 1


def test_list_findings_assignee_scoped(client: TestClient, auth_headers, seeded_users, sample_finding):
    """Test assignee only sees assigned findings."""
    headers = auth_headers("assignee")
    
    response = client.get("/api/v1/findings/", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # All findings should be assigned to this user
    for finding in data["findings"]:
        assert finding["assigned_to"] == seeded_users["assignee"]["id"]


def test_create_finding_success(client: TestClient, auth_headers, seeded_users, sample_audit):
    """Test successful finding creation by auditor."""
    headers = auth_headers("auditor")
    
    response = client.post(
        "/api/v1/findings/",
        headers=headers,
        json={
            "audit_id": sample_audit.id,
            "title": "New Test Finding",
            "description": "Test finding description",
            "severity": "high",
            "assigned_to": seeded_users["assignee"]["id"],
            "due_date": "2024-12-31"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["title"] == "New Test Finding"
    assert data["severity"] == "high"
    assert data["status"] == "draft"
    assert data["version"] == 1


def test_create_finding_assignee_forbidden(client: TestClient, auth_headers, seeded_users, sample_audit):
    """Test assignee cannot create findings."""
    headers = auth_headers("assignee")
    
    response = client.post(
        "/api/v1/findings/",
        headers=headers,
        json={
            "audit_id": sample_audit.id,
            "title": "New Test Finding",
            "severity": "medium"
        }
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Only auditors can create findings"


def test_update_finding_status_success(client: TestClient, auth_headers, seeded_users, sample_finding):
    """Test successful finding status update."""
    headers = auth_headers("assignee")
    headers["If-Match"] = f'"{sample_finding.version}"'
    
    response = client.put(
        f"/api/v1/findings/{sample_finding.id}/status",
        headers=headers,
        json={
            "status": "assigned",
            "comment": "Starting work on this finding"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "assigned"
    assert data["version"] == sample_finding.version + 1


def test_update_finding_status_invalid_transition(client: TestClient, auth_headers, seeded_users, sample_finding):
    """Test invalid status transition returns 422."""
    headers = auth_headers("assignee")
    headers["If-Match"] = f'"{sample_finding.version}"'
    
    response = client.put(
        f"/api/v1/findings/{sample_finding.id}/status",
        headers=headers,
        json={
            "status": "closed",  # Cannot go directly from draft to closed
            "comment": "Trying invalid transition"
        }
    )
    
    assert response.status_code == 422
    assert "Invalid transition" in response.json()["detail"]


def test_update_finding_status_missing_if_match(client: TestClient, auth_headers, seeded_users, sample_finding):
    """Test status update without If-Match header returns 428."""
    headers = auth_headers("assignee")
    
    response = client.put(
        f"/api/v1/findings/{sample_finding.id}/status",
        headers=headers,
        json={"status": "assigned"}
    )
    
    assert response.status_code == 428
    assert "If-Match header required" in response.json()["detail"]


def test_update_finding_status_version_conflict(client: TestClient, auth_headers, seeded_users, sample_finding):
    """Test optimistic locking with stale version returns 409."""
    headers = auth_headers("assignee")
    headers["If-Match"] = f'"{sample_finding.version + 10}"'  # Stale version
    
    response = client.put(
        f"/api/v1/findings/{sample_finding.id}/status",
        headers=headers,
        json={"status": "assigned"}
    )
    
    assert response.status_code == 409
    assert "Version mismatch" in response.json()["detail"]


def test_get_finding_history(client: TestClient, auth_headers, seeded_users, sample_finding):
    """Test retrieving finding status history."""
    headers = auth_headers("assignee")
    
    response = client.get(f"/api/v1/findings/{sample_finding.id}/history", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "history" in data
    assert isinstance(data["history"], list)
    # Should have at least the initial creation entry
    assert len(data["history"]) >= 1


def test_create_comment_success(client: TestClient, auth_headers, seeded_users, sample_finding):
    """Test successful comment creation."""
    headers = auth_headers("assignee")
    
    response = client.post(
        f"/api/v1/findings/{sample_finding.id}/comments",
        headers=headers,
        json={
            "content": "This is a test comment",
            "parent_id": None
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["content"] == "This is a test comment"
    assert data["finding_id"] == sample_finding.id
    assert data["author_id"] == seeded_users["assignee"]["id"]