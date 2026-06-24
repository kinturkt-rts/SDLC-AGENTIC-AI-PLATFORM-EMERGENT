"""Tests for /api/v1/notices routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── List notices ──────────────────────────────────────────────────────────────

def test_list_notices_empty(client: TestClient) -> None:
    resp = client.get("/api/v1/notices")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1


def test_list_notices_returns_active(client: TestClient, sample_notice) -> None:
    resp = client.get("/api/v1/notices")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Test Notice"


def test_list_notices_excludes_archived(client: TestClient, archived_notice) -> None:
    resp = client.get("/api/v1/notices")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


def test_list_notices_filter_by_category(client: TestClient, sample_notice, sample_category) -> None:
    resp = client.get("/api/v1/notices", params={"category_id": sample_category.id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


def test_list_notices_filter_by_category_no_match(client: TestClient, sample_notice) -> None:
    resp = client.get("/api/v1/notices", params={"category_id": 9999})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_notices_search(client: TestClient, sample_notice) -> None:
    resp = client.get("/api/v1/notices", params={"search": "test notice"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_notices_search_no_match(client: TestClient, sample_notice) -> None:
    resp = client.get("/api/v1/notices", params={"search": "xyz_no_match"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_notices_pagination(client: TestClient, sample_notice) -> None:
    resp = client.get("/api/v1/notices", params={"page": 1, "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 5
    assert data["pages"] >= 1


# ── Create notice ─────────────────────────────────────────────────────────────

def test_create_notice_success(client: TestClient, organizer_headers: dict, sample_category) -> None:
    payload = {
        "title": "New Notice",
        "body": "Body text here.",
        "category_id": sample_category.id,
        "author_display_name": "Org Author",
    }
    resp = client.post("/api/v1/notices", json=payload, headers=organizer_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "New Notice"
    assert data["archived"] is False


def test_create_notice_no_auth(client: TestClient, sample_category) -> None:
    payload = {
        "title": "Unauthorized",
        "body": "Body.",
        "category_id": sample_category.id,
        "author_display_name": "Nobody",
    }
    resp = client.post("/api/v1/notices", json=payload)
    assert resp.status_code == 401


def test_create_notice_wrong_secret(client: TestClient, sample_category) -> None:
    payload = {
        "title": "Unauthorized",
        "body": "Body.",
        "category_id": sample_category.id,
        "author_display_name": "Nobody",
    }
    resp = client.post(
        "/api/v1/notices",
        json=payload,
        headers={"X-Organizer-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401


def test_create_notice_invalid_category(client: TestClient, organizer_headers: dict) -> None:
    payload = {
        "title": "Bad Category Notice",
        "body": "Body.",
        "category_id": 9999,
        "author_display_name": "Author",
    }
    resp = client.post("/api/v1/notices", json=payload, headers=organizer_headers)
    assert resp.status_code == 400


def test_create_notice_no_category(client: TestClient, organizer_headers: dict) -> None:
    payload = {
        "title": "No Category Notice",
        "body": "Body without category.",
        "author_display_name": "Author",
    }
    resp = client.post("/api/v1/notices", json=payload, headers=organizer_headers)
    assert resp.status_code == 201
    assert resp.json()["category_id"] is None


# ── Update notice ─────────────────────────────────────────────────────────────

def test_update_notice_success(client: TestClient, organizer_headers: dict, sample_notice) -> None:
    resp = client.put(
        f"/api/v1/notices/{sample_notice.id}",
        json={"title": "Updated Title"},
        headers=organizer_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


def test_update_notice_not_found(client: TestClient, organizer_headers: dict) -> None:
    resp = client.put(
        "/api/v1/notices/9999",
        json={"title": "Ghost"},
        headers=organizer_headers,
    )
    assert resp.status_code == 404


def test_update_notice_no_auth(client: TestClient, sample_notice) -> None:
    resp = client.put(f"/api/v1/notices/{sample_notice.id}", json={"title": "X"})
    assert resp.status_code == 401


# ── Archive notice ─────────────────────────────────────────────────────────────

def test_archive_notice_success(client: TestClient, organizer_headers: dict, sample_notice) -> None:
    resp = client.delete(
        f"/api/v1/notices/{sample_notice.id}/archive",
        headers=organizer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert str(sample_notice.id) in data["message"]


def test_archive_notice_not_found(client: TestClient, organizer_headers: dict) -> None:
    resp = client.delete("/api/v1/notices/9999/archive", headers=organizer_headers)
    assert resp.status_code == 404


def test_archive_notice_no_auth(client: TestClient, sample_notice) -> None:
    resp = client.delete(f"/api/v1/notices/{sample_notice.id}/archive")
    assert resp.status_code == 401


def test_archived_notice_hidden_from_list(client: TestClient, organizer_headers: dict, sample_notice) -> None:
    # Archive the notice
    client.delete(f"/api/v1/notices/{sample_notice.id}/archive", headers=organizer_headers)
    # Now it should not appear in browse list
    resp = client.get("/api/v1/notices")
    assert resp.json()["total"] == 0
