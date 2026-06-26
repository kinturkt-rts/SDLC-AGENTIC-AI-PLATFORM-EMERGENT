import pytest
from fastapi.testclient import TestClient


def test_search_books_anonymous(client: TestClient, sample_book):
    """Test anonymous book search."""
    response = client.get("/books/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    
    book = data[0]
    assert "id" in book
    assert "title" in book
    assert "author" in book
    assert "available_copies" in book


def test_search_books_with_query(client: TestClient, sample_book):
    """Test book search with query parameter."""
    response = client.get("/books/", params={"query": "Test"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "Test" in data[0]["title"]


def test_create_book_librarian_only(client: TestClient, librarian_headers):
    """Test creating a book requires librarian auth."""
    book_data = {
        "isbn": "9781234567890",
        "title": "New Book",
        "author": "New Author",
        "total_copies": 1
    }
    
    response = client.post("/books/", json=book_data, headers=librarian_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Book"
    assert data["available_copies"] == 1


def test_create_book_without_auth_fails(client: TestClient):
    """Test creating a book without auth fails."""
    book_data = {
        "isbn": "9781234567891",
        "title": "Unauthorized Book",
        "author": "No Auth",
        "total_copies": 1
    }
    
    response = client.post("/books/", json=book_data)
    assert response.status_code == 401


def test_create_duplicate_isbn_fails(client: TestClient, librarian_headers, sample_book):
    """Test creating a book with duplicate ISBN fails."""
    book_data = {
        "isbn": sample_book.isbn,  # Same ISBN as sample_book
        "title": "Different Title",
        "author": "Different Author",
        "total_copies": 1
    }
    
    response = client.post("/books/", json=book_data, headers=librarian_headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_delete_book_with_no_loans(client: TestClient, librarian_headers):
    """Test deleting a book with no active loans."""
    # First create a book
    book_data = {
        "isbn": "9781234567892",
        "title": "To Delete",
        "author": "Delete Me",
        "total_copies": 1
    }
    create_response = client.post("/books/", json=book_data, headers=librarian_headers)
    book_id = create_response.json()["id"]
    
    # Then delete it
    response = client.delete(f"/books/{book_id}", headers=librarian_headers)
    assert response.status_code == 204


def test_delete_nonexistent_book_fails(client: TestClient, librarian_headers):
    """Test deleting a non-existent book fails."""
    response = client.delete("/books/nonexistent-id", headers=librarian_headers)
    assert response.status_code == 404