"""Tests for Runbook lifecycle management."""
import uuid


def test_create_runbook(client, api_headers, sample_service):
    body = {
        "title": "Test Runbook",
        "service_id": str(sample_service.id),
        "default_severity": "high",
        "short_summary": "A test runbook",
        "author": "tester",
    }
    resp = client.post("/api/v1/runbooks", json=body, headers=api_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Runbook"
    assert data["lifecycle_status"] == "draft"


def test_list_runbooks(client, api_headers, sample_runbook):
    resp = client.get("/api/v1/runbooks", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_get_runbook(client, api_headers, sample_runbook):
    resp = client.get(f"/api/v1/runbooks/{sample_runbook.id}", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(sample_runbook.id)


def test_activate_runbook_no_steps(client, api_headers, sample_runbook):
    """Cannot activate a runbook with zero steps."""
    resp = client.post(
        f"/api/v1/runbooks/{sample_runbook.id}/activate", headers=api_headers
    )
    assert resp.status_code == 422
    assert "at least one step" in resp.json()["detail"]


def test_activate_runbook_with_steps(client, api_headers, sample_runbook, sample_step):
    """Can activate a runbook that has steps."""
    resp = client.post(
        f"/api/v1/runbooks/{sample_runbook.id}/activate", headers=api_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "activated"


def test_activate_runbook_duplicate_title(client, api_headers, active_runbook, db_session):
    """Cannot activate if another active runbook has same title+service."""
    from app.models.runbook import Runbook
    from app.models.runbook_step import RunbookStep
    # Create a draft with same title
    draft = Runbook(
        id=str(uuid.uuid4()),
        title=active_runbook.title,
        service_id=active_runbook.service_id,
        default_severity="medium",
        author="test",
        lifecycle_status="draft",
    )
    db_session.add(draft)
    db_session.commit()
    # Add a step
    step = RunbookStep(
        id=str(uuid.uuid4()),
        runbook_id=draft.id,
        step_number=1,
        title="Step",
        body_text="Body",
    )
    db_session.add(step)
    db_session.commit()

    resp = client.post(f"/api/v1/runbooks/{draft.id}/activate", headers=api_headers)
    assert resp.status_code == 409


def test_retire_runbook(client, api_headers, active_runbook):
    resp = client.post(
        f"/api/v1/runbooks/{active_runbook.id}/retire", headers=api_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lifecycle_status"] == "retired"


def test_retire_non_active_runbook(client, api_headers, sample_runbook):
    """Cannot retire a draft."""
    resp = client.post(
        f"/api/v1/runbooks/{sample_runbook.id}/retire", headers=api_headers
    )
    assert resp.status_code == 422
