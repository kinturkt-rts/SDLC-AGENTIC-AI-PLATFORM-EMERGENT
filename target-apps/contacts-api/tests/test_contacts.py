"""Test contact endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_list_contacts_empty(client: TestClient):
    """Test listing contacts when none exist."""
    response = client.get("/contacts/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_get_contact_not_found(client: TestClient):
    """Test getting non-existent contact."""
    response = client.get("/contacts/99999999-9999-9999-9999-999999999999")
    assert response.status_code == 404
    assert "Contact not found" in response.json()["detail"]


def test_create_contact_success(client: TestClient, api_headers: dict, seeded_dept):
    """Test successful contact creation."""
    contact_data = {
        "department_id": seeded_dept.id,
        "full_name": "Jane Smith",
        "email": "jane.smith@company.com",
        "phone": "555-5678",
        "title": "Senior Engineer"
    }
    response = client.post("/contacts/", json=contact_data, headers=api_headers)
    assert response.status_code == 201
    
    contact = response.json()
    assert contact["full_name"] == "Jane Smith"
    assert contact["email"] == "jane.smith@company.com"
    assert contact["phone"] == "555-5678"
    assert contact["title"] == "Senior Engineer"
    assert contact["is_active"] is True
    assert contact["department"]["name"] == "Engineering"
    assert "id" in contact
    assert "created_at" in contact
    assert "updated_at" in contact


def test_create_contact_without_api_key(client: TestClient, seeded_dept):
    """Test contact creation fails without API key."""
    contact_data = {
        "department_id": seeded_dept.id,
        "full_name": "Jane Smith",
        "email": "jane.smith@company.com"
    }
    response = client.post("/contacts/", json=contact_data)
    assert response.status_code == 401
    assert "Invalid or missing API key" in response.json()["detail"]


def test_create_contact_invalid_department(client: TestClient, api_headers: dict):
    """Test contact creation with non-existent department."""
    contact_data = {
        "department_id": "99999999-9999-9999-9999-999999999999",
        "full_name": "Jane Smith",
        "email": "jane.smith@company.com"
    }
    response = client.post("/contacts/", json=contact_data, headers=api_headers)
    assert response.status_code == 404
    assert "Department not found" in response.json()["detail"]


def test_create_contact_duplicate_email(client: TestClient, api_headers: dict, seeded_contact):
    """Test contact creation with duplicate email."""
    contact_data = {
        "department_id": seeded_contact.department_id,
        "full_name": "Different Name",
        "email": seeded_contact.email  # duplicate email
    }
    response = client.post("/contacts/", json=contact_data, headers=api_headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_get_contact_success(client: TestClient, seeded_contact):
    """Test getting an existing contact."""
    response = client.get(f"/contacts/{seeded_contact.id}")
    assert response.status_code == 200
    
    contact = response.json()
    assert contact["id"] == seeded_contact.id
    assert contact["full_name"] == seeded_contact.full_name
    assert contact["email"] == seeded_contact.email
    assert contact["department"]["name"] == "Engineering"


def test_list_contacts_with_data(client: TestClient, seeded_contact):
    """Test listing contacts after creating some."""
    response = client.get("/contacts/")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 1
    assert data["items"][0]["full_name"] == "John Doe"


def test_list_contacts_with_search(client: TestClient, api_headers: dict, seeded_dept):
    """Test contact search functionality."""
    # Create multiple contacts
    contacts = [
        {"department_id": seeded_dept.id, "full_name": "John Smith", "email": "john.smith@company.com"},
        {"department_id": seeded_dept.id, "full_name": "Jane Doe", "email": "jane.doe@company.com"},
        {"department_id": seeded_dept.id, "full_name": "Bob Wilson", "email": "bob.wilson@company.com"}
    ]
    
    for contact_data in contacts:
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 201
    
    # Search by name
    response = client.get("/contacts/?q=john")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "john" in data["items"][0]["full_name"].lower()
    
    # Search by email
    response = client.get("/contacts/?q=doe")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "doe" in data["items"][0]["email"].lower()


def test_list_contacts_pagination(client: TestClient, api_headers: dict, seeded_dept):
    """Test contact pagination."""
    # Create multiple contacts
    for i in range(5):
        contact_data = {
            "department_id": seeded_dept.id,
            "full_name": f"Test User {i}",
            "email": f"test{i}@company.com"
        }
        response = client.post("/contacts/", json=contact_data, headers=api_headers)
        assert response.status_code == 201
    
    # Test pagination
    response = client.get("/contacts/?limit=3&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 5
    assert data["limit"] == 3
    assert data["offset"] == 0
    
    # Next page
    response = client.get("/contacts/?limit=3&offset=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5


def test_update_contact_success(client: TestClient, api_headers: dict, seeded_contact):
    """Test successful contact update."""
    update_data = {
        "full_name": "John Updated Doe",
        "title": "Lead Engineer"
    }
    response = client.patch(f"/contacts/{seeded_contact.id}", json=update_data, headers=api_headers)
    assert response.status_code == 200
    
    contact = response.json()
    assert contact["full_name"] == "John Updated Doe"
    assert contact["title"] == "Lead Engineer"
    assert contact["email"] == seeded_contact.email  # unchanged


def test_update_contact_not_found(client: TestClient, api_headers: dict):
    """Test updating non-existent contact."""
    update_data = {"full_name": "New Name"}
    response = client.patch("/contacts/99999999-9999-9999-9999-999999999999", 
                          json=update_data, headers=api_headers)
    assert response.status_code == 404
    assert "Contact not found" in response.json()["detail"]


def test_update_contact_without_api_key(client: TestClient, seeded_contact):
    """Test contact update fails without API key."""
    update_data = {"full_name": "New Name"}
    response = client.patch(f"/contacts/{seeded_contact.id}", json=update_data)
    assert response.status_code == 401


def test_delete_contact_success(client: TestClient, api_headers: dict, seeded_contact):
    """Test successful contact soft delete."""
    response = client.delete(f"/contacts/{seeded_contact.id}", headers=api_headers)
    assert response.status_code == 204
    
    # Verify contact is soft deleted
    response = client.get(f"/contacts/{seeded_contact.id}")
    assert response.status_code == 200
    contact = response.json()
    assert contact["is_active"] is False


def test_delete_contact_not_found(client: TestClient, api_headers: dict):
    """Test deleting non-existent contact."""
    response = client.delete("/contacts/99999999-9999-9999-9999-999999999999", headers=api_headers)
    assert response.status_code == 404
    assert "Contact not found" in response.json()["detail"]


def test_delete_contact_without_api_key(client: TestClient, seeded_contact):
    """Test contact delete fails without API key."""
    response = client.delete(f"/contacts/{seeded_contact.id}")
    assert response.status_code == 401