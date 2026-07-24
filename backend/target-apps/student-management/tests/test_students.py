"""Tests for /api/v1/students endpoints."""
from datetime import date

import pytest


class TestCreateStudent:
    """POST /api/v1/students"""

    def test_create_success(self, client, write_headers):
        payload = {
            "student_id": "STU-100",
            "full_name": "Test User",
            "email": "test@example.com",
            "course": "Physics",
            "enrollment_date": "2024-01-10",
        }
        resp = client.post("/api/v1/students", json=payload, headers=write_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["student_id"] == "STU-100"
        assert data["status"] == "active"
        assert data["is_active"] is True

    def test_create_duplicate_student_id(self, client, write_headers):
        payload = {
            "student_id": "STU-DUP",
            "full_name": "First",
            "email": "first@example.com",
            "course": "Math",
            "enrollment_date": "2024-01-01",
        }
        client.post("/api/v1/students", json=payload, headers=write_headers)
        payload2 = {
            "student_id": "STU-DUP",
            "full_name": "Second",
            "email": "second@example.com",
            "course": "Math",
            "enrollment_date": "2024-01-01",
        }
        resp = client.post("/api/v1/students", json=payload2, headers=write_headers)
        assert resp.status_code == 409

    def test_create_duplicate_email(self, client, write_headers):
        payload = {
            "student_id": "STU-A1",
            "full_name": "A",
            "email": "same@example.com",
            "course": "Math",
            "enrollment_date": "2024-01-01",
        }
        client.post("/api/v1/students", json=payload, headers=write_headers)
        payload2 = {
            "student_id": "STU-A2",
            "full_name": "B",
            "email": "same@example.com",
            "course": "Math",
            "enrollment_date": "2024-01-01",
        }
        resp = client.post("/api/v1/students", json=payload2, headers=write_headers)
        assert resp.status_code == 409

    def test_create_future_enrollment_date(self, client, write_headers):
        payload = {
            "student_id": "STU-FUT",
            "full_name": "Future",
            "email": "future@example.com",
            "course": "Art",
            "enrollment_date": "2099-12-31",
        }
        resp = client.post("/api/v1/students", json=payload, headers=write_headers)
        assert resp.status_code == 422

    def test_create_without_api_key(self, client):
        payload = {
            "student_id": "STU-NO",
            "full_name": "NoKey",
            "email": "nokey@example.com",
            "course": "CS",
            "enrollment_date": "2024-01-01",
        }
        resp = client.post("/api/v1/students", json=payload)
        assert resp.status_code == 401

    def test_create_with_read_key_rejected(self, client, read_headers):
        payload = {
            "student_id": "STU-RD",
            "full_name": "ReadOnly",
            "email": "ro@example.com",
            "course": "CS",
            "enrollment_date": "2024-01-01",
        }
        resp = client.post("/api/v1/students", json=payload, headers=read_headers)
        assert resp.status_code == 401


class TestListStudents:
    """GET /api/v1/students"""

    def test_list_empty(self, client, read_headers):
        resp = client.get("/api/v1/students", headers=read_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_students(self, client, write_headers, read_headers):
        for i in range(3):
            client.post("/api/v1/students", json={
                "student_id": f"STU-L{i}",
                "full_name": f"Student {i}",
                "email": f"s{i}@example.com",
                "course": "CS",
                "enrollment_date": "2024-01-01",
            }, headers=write_headers)
        resp = client.get("/api/v1/students", headers=read_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_filter_by_course(self, client, write_headers, read_headers):
        client.post("/api/v1/students", json={
            "student_id": "STU-CS1",
            "full_name": "CS Student",
            "email": "cs1@example.com",
            "course": "Computer Science",
            "enrollment_date": "2024-01-01",
        }, headers=write_headers)
        client.post("/api/v1/students", json={
            "student_id": "STU-DE1",
            "full_name": "DE Student",
            "email": "de1@example.com",
            "course": "Data Engineering",
            "enrollment_date": "2024-01-01",
        }, headers=write_headers)
        resp = client.get("/api/v1/students?course=Computer+Science", headers=read_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["course"] == "Computer Science"

    def test_filter_by_status(self, client, write_headers, read_headers):
        client.post("/api/v1/students", json={
            "student_id": "STU-ACT",
            "full_name": "Active",
            "email": "act@example.com",
            "course": "CS",
            "enrollment_date": "2024-01-01",
            "status": "active",
        }, headers=write_headers)
        client.post("/api/v1/students", json={
            "student_id": "STU-INACT",
            "full_name": "Inactive",
            "email": "inact@example.com",
            "course": "CS",
            "enrollment_date": "2024-01-01",
            "status": "inactive",
        }, headers=write_headers)
        resp = client.get("/api/v1/students?status=inactive", headers=read_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "inactive"

    def test_list_without_api_key(self, client):
        resp = client.get("/api/v1/students")
        assert resp.status_code == 401


class TestGetStudent:
    """GET /api/v1/students/{student_id}"""

    def test_get_existing(self, client, write_headers, read_headers):
        client.post("/api/v1/students", json={
            "student_id": "STU-GET",
            "full_name": "Get Me",
            "email": "getme@example.com",
            "course": "CS",
            "enrollment_date": "2024-01-01",
        }, headers=write_headers)
        resp = client.get("/api/v1/students/STU-GET", headers=read_headers)
        assert resp.status_code == 200
        assert resp.json()["student_id"] == "STU-GET"

    def test_get_not_found(self, client, read_headers):
        resp = client.get("/api/v1/students/NONEXISTENT", headers=read_headers)
        assert resp.status_code == 404


class TestUpdateStudent:
    """PUT /api/v1/students/{student_id}"""

    def test_update_success(self, client, write_headers, read_headers):
        client.post("/api/v1/students", json={
            "student_id": "STU-UPD",
            "full_name": "Old Name",
            "email": "upd@example.com",
            "course": "CS",
            "enrollment_date": "2024-01-01",
        }, headers=write_headers)
        resp = client.put("/api/v1/students/STU-UPD", json={
            "full_name": "New Name",
            "course": "Data Science",
        }, headers=write_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "New Name"
        assert data["course"] == "Data Science"

    def test_update_not_found(self, client, write_headers):
        resp = client.put("/api/v1/students/NOPE", json={
            "full_name": "X",
        }, headers=write_headers)
        assert resp.status_code == 404

    def test_update_future_enrollment(self, client, write_headers):
        client.post("/api/v1/students", json={
            "student_id": "STU-UFUT",
            "full_name": "Orig",
            "email": "ufut@example.com",
            "course": "CS",
            "enrollment_date": "2024-01-01",
        }, headers=write_headers)
        resp = client.put("/api/v1/students/STU-UFUT", json={
            "enrollment_date": "2099-12-31",
        }, headers=write_headers)
        assert resp.status_code == 422


class TestDeactivateStudent:
    """PATCH /api/v1/students/{student_id}/deactivate"""

    def test_deactivate_success(self, client, write_headers, read_headers):
        client.post("/api/v1/students", json={
            "student_id": "STU-DEACT",
            "full_name": "Active",
            "email": "deact@example.com",
            "course": "CS",
            "enrollment_date": "2024-01-01",
        }, headers=write_headers)
        resp = client.patch("/api/v1/students/STU-DEACT/deactivate", headers=write_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "inactive"
        assert data["is_active"] is False
        # Still retrievable
        resp2 = client.get("/api/v1/students/STU-DEACT", headers=read_headers)
        assert resp2.status_code == 200

    def test_deactivate_not_found(self, client, write_headers):
        resp = client.patch("/api/v1/students/NOPE/deactivate", headers=write_headers)
        assert resp.status_code == 404

    def test_deactivate_without_write_key(self, client, read_headers):
        resp = client.patch("/api/v1/students/STU-X/deactivate", headers=read_headers)
        assert resp.status_code == 401


class TestSeedEndpoint:
    """POST /api/v1/students/seed"""

    def test_seed_creates_records(self, client, write_headers, read_headers):
        resp = client.post("/api/v1/students/seed", headers=write_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["seeded"] == 3
        # Verify records exist
        resp2 = client.get("/api/v1/students", headers=read_headers)
        assert len(resp2.json()) == 3

    def test_seed_idempotent(self, client, write_headers):
        client.post("/api/v1/students/seed", headers=write_headers)
        resp = client.post("/api/v1/students/seed", headers=write_headers)
        assert resp.status_code == 200
        assert resp.json()["seeded"] == 0

    def test_seed_requires_write_key(self, client, read_headers):
        resp = client.post("/api/v1/students/seed", headers=read_headers)
        assert resp.status_code == 401
