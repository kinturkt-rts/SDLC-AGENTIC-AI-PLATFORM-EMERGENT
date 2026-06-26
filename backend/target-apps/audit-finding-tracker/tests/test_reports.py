"""Tests for executive report endpoints."""

import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta
from app.models.audit import Audit
from app.models.finding import Finding


@pytest.fixture
def overdue_findings_data(db_session, seeded_users):
    """Create test data with overdue findings."""
    # Create an audit
    audit = Audit(
        title="Test Audit for Reports",
        created_by=seeded_users["auditor"]["id"]
    )
    db_session.add(audit)
    db_session.commit()
    
    # Create overdue finding
    overdue_date = date.today() - timedelta(days=5)
    overdue_finding = Finding(
        audit_id=audit.id,
        title="Overdue Finding",
        severity="high", 
        status="assigned",
        assigned_to=seeded_users["assignee"]["id"],
        due_date=overdue_date,
        created_by=seeded_users["auditor"]["id"]
    )
    
    # Create current finding
    future_date = date.today() + timedelta(days=10)
    current_finding = Finding(
        audit_id=audit.id,
        title="Current Finding",
        severity="medium",
        status="in_progress", 
        assigned_to=seeded_users["assignee"]["id"],
        due_date=future_date,
        created_by=seeded_users["auditor"]["id"]
    )
    
    db_session.add(overdue_finding)
    db_session.add(current_finding)
    db_session.commit()
    
    return {
        "audit": audit,
        "overdue_finding": overdue_finding,
        "current_finding": current_finding
    }


def test_executive_report_success(client: TestClient, auth_headers, seeded_users, overdue_findings_data):
    """Test executive report returns proper structure."""
    headers = auth_headers("executive")
    
    response = client.get("/api/v1/reports/executive", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields
    assert "overdue_findings" in data
    assert "severity_distribution" in data  
    assert "department_summaries" in data
    assert "total_findings" in data
    assert "total_overdue" in data
    assert "overdue_percentage" in data
    
    # Verify data types
    assert isinstance(data["overdue_findings"], list)
    assert isinstance(data["severity_distribution"], list)
    assert isinstance(data["department_summaries"], list)
    assert isinstance(data["total_findings"], int)
    assert isinstance(data["total_overdue"], int)
    assert isinstance(data["overdue_percentage"], (int, float))


def test_executive_report_overdue_findings(client: TestClient, auth_headers, seeded_users, overdue_findings_data):
    """Test overdue findings are properly identified."""
    headers = auth_headers("executive")
    
    response = client.get("/api/v1/reports/executive", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should have at least 1 overdue finding from our test data
    assert data["total_overdue"] >= 1
    
    # Check overdue finding structure
    if data["overdue_findings"]:
        overdue = data["overdue_findings"][0]
        assert "id" in overdue
        assert "title" in overdue
        assert "severity" in overdue
        assert "due_date" in overdue
        assert "days_overdue" in overdue
        assert overdue["days_overdue"] > 0


def test_executive_report_severity_distribution(client: TestClient, auth_headers, seeded_users, overdue_findings_data):
    """Test severity distribution is calculated correctly."""
    headers = auth_headers("executive")
    
    response = client.get("/api/v1/reports/executive", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should have severity distribution data
    assert len(data["severity_distribution"]) > 0
    
    # Check structure
    for dist in data["severity_distribution"]:
        assert "severity" in dist
        assert "count" in dist
        assert isinstance(dist["count"], int)
        assert dist["count"] > 0


def test_executive_report_unauthorized(client: TestClient):
    """Test executive report without auth returns 401.""" 
    response = client.get("/api/v1/reports/executive")
    
    assert response.status_code == 401


def test_executive_report_non_executive_forbidden(client: TestClient, auth_headers, seeded_users):
    """Test non-executive roles cannot access executive report."""
    headers = auth_headers("assignee")
    
    response = client.get("/api/v1/reports/executive", headers=headers)
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Executive access required"


def test_executive_report_auditor_forbidden(client: TestClient, auth_headers, seeded_users):
    """Test auditor role cannot access executive report."""
    headers = auth_headers("auditor")
    
    response = client.get("/api/v1/reports/executive", headers=headers)
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Executive access required"