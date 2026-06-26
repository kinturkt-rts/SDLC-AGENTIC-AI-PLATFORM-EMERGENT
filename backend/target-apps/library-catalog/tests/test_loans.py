import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta


def test_checkout_book_success(client: TestClient, member_headers, sample_member, sample_book):
    """Test successful book checkout."""
    loan_data = {"book_id": sample_book.id}
    
    response = client.post("/loans/", json=loan_data, headers=member_headers)
    assert response.status_code == 201
    data = response.json()
    
    assert data["book_id"] == sample_book.id
    assert data["member_id"] == sample_member.id
    assert data["returned_at"] is None
    assert "due_at" in data
    assert "is_overdue" in data


def test_checkout_nonexistent_book_fails(client: TestClient, member_headers, sample_member):
    """Test checking out non-existent book fails."""
    loan_data = {"book_id": "nonexistent-book-id"}
    
    response = client.post("/loans/", json=loan_data, headers=member_headers)
    assert response.status_code == 404


def test_checkout_without_auth_fails(client: TestClient, sample_book):
    """Test checking out book without auth fails."""
    loan_data = {"book_id": sample_book.id}
    
    response = client.post("/loans/", json=loan_data)
    assert response.status_code == 401


def test_get_my_loans_empty(client: TestClient, member_headers, sample_member):
    """Test getting loans when member has none."""
    response = client.get("/loans/mine", headers=member_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_my_loans_with_active_loan(client: TestClient, member_headers, sample_member, sample_book):
    """Test getting loans when member has active loan."""
    # Create a loan first
    loan_data = {"book_id": sample_book.id}
    client.post("/loans/", json=loan_data, headers=member_headers)
    
    response = client.get("/loans/mine", headers=member_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["book_id"] == sample_book.id
    assert data[0]["returned_at"] is None


def test_return_book_success(client: TestClient, member_headers, sample_member, sample_book):
    """Test successful book return."""
    # Create a loan first
    loan_data = {"book_id": sample_book.id}
    loan_response = client.post("/loans/", json=loan_data, headers=member_headers)
    loan_id = loan_response.json()["id"]
    
    # Return the book
    response = client.put(f"/loans/{loan_id}/return", headers=member_headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == loan_id
    assert data["returned_at"] is not None
    assert data["is_overdue"] is False


def test_return_nonexistent_loan_fails(client: TestClient, member_headers, sample_member):
    """Test returning non-existent loan fails."""
    response = client.put("/loans/nonexistent-loan-id/return", headers=member_headers)
    assert response.status_code == 404


def test_return_already_returned_book_fails(client: TestClient, member_headers, sample_member, sample_book):
    """Test returning already returned book fails."""
    # Create and return a loan
    loan_data = {"book_id": sample_book.id}
    loan_response = client.post("/loans/", json=loan_data, headers=member_headers)
    loan_id = loan_response.json()["id"]
    
    client.put(f"/loans/{loan_id}/return", headers=member_headers)
    
    # Try to return again
    response = client.put(f"/loans/{loan_id}/return", headers=member_headers)
    assert response.status_code == 409
    assert "already returned" in response.json()["detail"]