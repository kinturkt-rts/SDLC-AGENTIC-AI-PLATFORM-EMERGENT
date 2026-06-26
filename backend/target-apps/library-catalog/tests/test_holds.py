import pytest
from fastapi.testclient import TestClient


def test_place_hold_success(client: TestClient, member_headers, sample_member, sample_book):
    """Test successfully placing a hold."""
    hold_data = {"book_id": sample_book.id}
    
    response = client.post("/holds/", json=hold_data, headers=member_headers)
    assert response.status_code == 201
    data = response.json()
    
    assert data["book_id"] == sample_book.id
    assert data["member_id"] == sample_member.id
    assert data["fulfilled_at"] is None
    assert data["cancelled_at"] is None
    assert "queue_position" in data


def test_place_hold_nonexistent_book_fails(client: TestClient, member_headers, sample_member):
    """Test placing hold on non-existent book fails."""
    hold_data = {"book_id": "nonexistent-book-id"}
    
    response = client.post("/holds/", json=hold_data, headers=member_headers)
    assert response.status_code == 404


def test_place_hold_without_auth_fails(client: TestClient, sample_book):
    """Test placing hold without auth fails."""
    hold_data = {"book_id": sample_book.id}
    
    response = client.post("/holds/", json=hold_data)
    assert response.status_code == 401


def test_get_my_holds_empty(client: TestClient, member_headers, sample_member):
    """Test getting holds when member has none."""
    response = client.get("/holds/mine", headers=member_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_my_holds_with_active_hold(client: TestClient, member_headers, sample_member, sample_book):
    """Test getting holds when member has active hold."""
    # Create a hold first
    hold_data = {"book_id": sample_book.id}
    client.post("/holds/", json=hold_data, headers=member_headers)
    
    response = client.get("/holds/mine", headers=member_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["book_id"] == sample_book.id
    assert data[0]["fulfilled_at"] is None


def test_cancel_hold_success(client: TestClient, member_headers, sample_member, sample_book):
    """Test successfully cancelling a hold."""
    # Create a hold first
    hold_data = {"book_id": sample_book.id}
    hold_response = client.post("/holds/", json=hold_data, headers=member_headers)
    hold_id = hold_response.json()["id"]
    
    # Cancel the hold
    response = client.delete(f"/holds/{hold_id}", headers=member_headers)
    assert response.status_code == 204


def test_cancel_nonexistent_hold_fails(client: TestClient, member_headers, sample_member):
    """Test cancelling non-existent hold fails."""
    response = client.delete("/holds/nonexistent-hold-id", headers=member_headers)
    assert response.status_code == 404


def test_place_duplicate_hold_fails(client: TestClient, member_headers, sample_member, sample_book):
    """Test placing duplicate hold on same book fails."""
    hold_data = {"book_id": sample_book.id}
    
    # Place first hold
    response1 = client.post("/holds/", json=hold_data, headers=member_headers)
    assert response1.status_code == 201
    
    # Try to place second hold on same book
    response2 = client.post("/holds/", json=hold_data, headers=member_headers)
    assert response2.status_code == 409
    assert "already has an active hold" in response2.json()["detail"]