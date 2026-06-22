"""Tests for bug deduplication endpoints."""

from fastapi.testclient import TestClient

from tests.conftest import make_similar


def test_create_bug_requires_api_key(client: TestClient) -> None:
    response = client.post(
        "/bugs/",
        json={"title": "T", "description": "Something broke"},
    )
    assert response.status_code == 401


def test_create_bug_success(client: TestClient, api_headers: dict, mock_dedup) -> None:
    payload = {
        "title": "Checkout timeout",
        "description": "Payment page hangs after clicking Pay.",
    }
    response = client.post("/bugs/", json=payload, headers=api_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["bug"]["title"] == payload["title"]
    assert data["likely_duplicate"] is False
    mock_dedup.embed_description.assert_called_once_with(payload["description"])
    mock_dedup.store_embedding.assert_called_once()


def test_near_duplicate_flagged_high_score(
    client: TestClient,
    api_headers: dict,
    mock_dedup,
    seeded_open_bug,
) -> None:
    mock_dedup.find_similar.return_value = [make_similar(seeded_open_bug, 0.92)]
    payload = {
        "title": "Safari login broken",
        "description": "Cannot authenticate on Safari iOS 17.",
    }
    response = client.post("/bugs/", json=payload, headers=api_headers)
    assert response.status_code == 201
    data = response.json()
    assert len(data["similar_bugs"]) == 1
    assert data["similar_bugs"][0]["id"] == seeded_open_bug.id
    assert data["similar_bugs"][0]["similarity_score"] == 0.92
    assert data["likely_duplicate"] is True
    assert data["top_similarity_score"] == 0.92


def test_unrelated_bug_low_score(
    client: TestClient,
    api_headers: dict,
    mock_dedup,
    seeded_open_bug,
) -> None:
    mock_dedup.find_similar.return_value = [make_similar(seeded_open_bug, 0.31)]
    payload = {
        "title": "Dark mode glitch",
        "description": "Sidebar colors wrong in dark theme.",
    }
    response = client.post("/bugs/", json=payload, headers=api_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["likely_duplicate"] is False
    assert data["top_similarity_score"] == 0.31


def test_patch_description_reembeds(
    client: TestClient,
    api_headers: dict,
    mock_dedup,
    seeded_open_bug,
) -> None:
    mock_dedup.find_similar.return_value = []
    new_description = "Updated repro steps for Safari login failure."
    response = client.patch(
        f"/bugs/{seeded_open_bug.id}",
        json={"description": new_description},
        headers=api_headers,
    )
    assert response.status_code == 200
    mock_dedup.embed_description.assert_called_once_with(new_description)
    mock_dedup.store_embedding.assert_called_once()
    mock_dedup.find_similar.assert_called_once()
    call_kwargs = mock_dedup.find_similar.call_args.kwargs
    assert call_kwargs["exclude_bug_id"] == seeded_open_bug.id


def test_mark_duplicate_requires_admin(
    client: TestClient,
    api_headers: dict,
    seeded_open_bug,
    db_session,
) -> None:
    from app.models.bug import Bug, BugStatus
    import uuid

    new_bug = Bug(
        id=str(uuid.uuid4()),
        title="Duplicate report",
        description="Same Safari issue",
        status=BugStatus.OPEN,
    )
    db_session.add(new_bug)
    db_session.commit()

    response = client.post(
        f"/bugs/{new_bug.id}/mark-duplicate",
        json={"duplicate_of_id": seeded_open_bug.id},
        headers=api_headers,
    )
    assert response.status_code == 403


def test_mark_duplicate_success(
    client: TestClient,
    admin_headers: dict,
    seeded_open_bug,
    db_session,
) -> None:
    import uuid

    from app.models.bug import Bug, BugStatus

    new_bug = Bug(
        id=str(uuid.uuid4()),
        title="Duplicate report",
        description="Same Safari issue",
        status=BugStatus.OPEN,
    )
    db_session.add(new_bug)
    db_session.commit()

    response = client.post(
        f"/bugs/{new_bug.id}/mark-duplicate",
        json={"duplicate_of_id": seeded_open_bug.id},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "duplicate"
    assert data["duplicate_of_id"] == seeded_open_bug.id


def test_close_bug_excludes_from_search_via_status_filter(
    client: TestClient,
    api_headers: dict,
    mock_dedup,
    seeded_closed_bug,
) -> None:
    mock_dedup.find_similar.return_value = []
    payload = {
        "title": "Safari login",
        "description": "Safari auth fails on mobile.",
    }
    response = client.post("/bugs/", json=payload, headers=api_headers)
    assert response.status_code == 201
    assert response.json()["similar_bugs"] == []
    mock_dedup.find_similar.assert_called_once()
