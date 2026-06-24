"""Tests for Runbook step management."""


def test_create_step(client, api_headers, sample_runbook):
    body = {
        "step_number": 1,
        "title": "First Step",
        "body_text": "Do the first thing.",
        "estimated_minutes": 5,
    }
    resp = client.post(
        f"/api/v1/runbooks/{sample_runbook.id}/steps", json=body, headers=api_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "First Step"
    assert data["step_number"] == 1


def test_list_steps(client, api_headers, sample_runbook, sample_step):
    resp = client.get(
        f"/api/v1/runbooks/{sample_runbook.id}/steps", headers=api_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["step_number"] == 1


def test_get_step(client, api_headers, sample_runbook, sample_step):
    resp = client.get(
        f"/api/v1/runbooks/{sample_runbook.id}/steps/{sample_step.id}",
        headers=api_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(sample_step.id)


def test_update_step(client, api_headers, sample_runbook, sample_step):
    resp = client.put(
        f"/api/v1/runbooks/{sample_runbook.id}/steps/{sample_step.id}",
        json={"title": "Updated Title"},
        headers=api_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


def test_delete_step(client, api_headers, sample_runbook, sample_step):
    resp = client.delete(
        f"/api/v1/runbooks/{sample_runbook.id}/steps/{sample_step.id}",
        headers=api_headers,
    )
    assert resp.status_code == 204
