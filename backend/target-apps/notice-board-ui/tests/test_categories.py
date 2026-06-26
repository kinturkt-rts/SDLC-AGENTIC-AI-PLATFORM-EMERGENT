"""Tests for /api/v1/categories routes."""
from __future__ import annotations

from fastapi.testclient import TestClient


# ── List categories ────────────────────────────────────────────────────────────

def test_list_categories_empty(client: TestClient) -> None:
    resp = client.get("/api/v1/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_categories_returns_all(client: TestClient, sample_category) -> None:
    resp = client.get("/api/v1/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "General"


# ── Create category ────────────────────────────────────────────────────────────

def test_create_category_success(client: TestClient, organizer_headers: dict) -> None:
    resp = client.post(
        "/api/v1/categories",
        json={"name": "IT", "description": "Tech updates"},
        headers=organizer_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "IT"
    assert data["id"] is not None


def test_create_category_no_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/categories", json={"name": "HR"})
    assert resp.status_code == 401


def test_create_category_wrong_secret(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/categories",
        json={"name": "Events"},
        headers={"X-Organizer-Secret": "bad-secret"},
    )
    assert resp.status_code == 401


def test_create_category_duplicate_name(client: TestClient, organizer_headers: dict, sample_category) -> None:
    resp = client.post(
        "/api/v1/categories",
        json={"name": "General"},  # same as sample_category
        headers=organizer_headers,
    )
    assert resp.status_code == 409


def test_create_category_no_description(client: TestClient, organizer_headers: dict) -> None:
    resp = client.post(
        "/api/v1/categories",
        json={"name": "Finance"},
        headers=organizer_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["description"] is None
