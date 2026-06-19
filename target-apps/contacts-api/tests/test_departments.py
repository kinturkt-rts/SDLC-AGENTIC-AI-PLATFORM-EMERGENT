"""Test department endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_list_departments_empty(client: TestClient):
    """Test listing departments when none exist."""
    response = client.get("/departments/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_department_success(client: TestClient, api_headers: dict):
    """Test successful department creation."""
    dept_data = {
        "name": "Engineering", 
        "code": "ENG"
    }
    response = client.post("/departments/", json=dept_data, headers=api_headers)
    assert response.status_code == 201
    
    dept = response.json()
    assert dept["name"] == "Engineering"
    assert dept["code"] == "ENG"
    assert "id" in dept
    assert "created_at" in dept


def test_create_department_without_api_key(client: TestClient):
    """Test department creation fails without API key."""
    dept_data = {
        "name": "Engineering", 
        "code": "ENG"
    }
    response = client.post("/departments/", json=dept_data)
    assert response.status_code == 401
    assert "Invalid or missing API key" in response.json()["detail"]


def test_create_department_invalid_code(client: TestClient, api_headers: dict):
    """Test department creation with invalid code format."""
    dept_data = {
        "name": "Engineering", 
        "code": "invalid"
    }
    response = client.post("/departments/", json=dept_data, headers=api_headers)
    assert response.status_code == 422


def test_create_department_duplicate_code(client: TestClient, api_headers: dict):
    """Test department creation with duplicate code."""
    dept_data = {
        "name": "Engineering", 
        "code": "ENG"
    }
    # First creation should succeed
    response = client.post("/departments/", json=dept_data, headers=api_headers)
    assert response.status_code == 201
    
    # Second creation should fail
    dept_data2 = {
        "name": "Different Engineering", 
        "code": "ENG"
    }
    response = client.post("/departments/", json=dept_data2, headers=api_headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_list_departments_with_data(client: TestClient, api_headers: dict):
    """Test listing departments after creating some."""
    # Create a few departments
    depts = [
        {"name": "Engineering", "code": "ENG"},
        {"name": "Sales", "code": "SALES"}
    ]
    
    for dept_data in depts:
        response = client.post("/departments/", json=dept_data, headers=api_headers)
        assert response.status_code == 201
    
    # List all departments
    response = client.get("/departments/")
    assert response.status_code == 200
    
    dept_list = response.json()
    assert len(dept_list) == 2
    codes = {dept["code"] for dept in dept_list}
    assert codes == {"ENG", "SALES"}


def test_update_department_success(client: TestClient, api_headers: dict):
    """Test successful department update."""
    # Create department
    dept_data = {"name": "Engineering", "code": "ENG"}
    response = client.post("/departments/", json=dept_data, headers=api_headers)
    assert response.status_code == 201
    dept_id = response.json()["id"]
    
    # Update department
    update_data = {"name": "Software Engineering"}
    response = client.patch(f"/departments/{dept_id}", json=update_data, headers=api_headers)
    assert response.status_code == 200
    
    updated_dept = response.json()
    assert updated_dept["name"] == "Software Engineering"
    assert updated_dept["code"] == "ENG"  # unchanged


def test_update_department_not_found(client: TestClient, api_headers: dict):
    """Test updating non-existent department."""
    update_data = {"name": "New Name"}
    response = client.patch("/departments/99999999-9999-9999-9999-999999999999", 
                          json=update_data, headers=api_headers)
    assert response.status_code == 404
    assert "Department not found" in response.json()["detail"]


def test_update_department_without_api_key(client: TestClient, api_headers: dict):
    """Test department update fails without API key."""
    # Create department first
    dept_data = {"name": "Engineering", "code": "ENG"}
    response = client.post("/departments/", json=dept_data, headers=api_headers)
    assert response.status_code == 201
    dept_id = response.json()["id"]
    
    # Try to update without API key
    update_data = {"name": "New Name"}
    response = client.patch(f"/departments/{dept_id}", json=update_data)
    assert response.status_code == 401