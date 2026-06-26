import io


def test_list_documents(client, sample_collection, sample_document, collection_membership, auth_headers_viewer):
    """Test listing documents in a collection"""
    response = client.get(
        f"/collections/{sample_collection.id}/documents",
        headers=auth_headers_viewer
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) >= 1
    document = data[0]
    assert document["title"] == sample_document.title
    assert document["status"] == sample_document.status.value
    assert "chunk_count" in document


def test_list_documents_no_access(client, sample_collection, sample_document, auth_headers_viewer):
    """Test listing documents in collection without membership returns 403"""
    response = client.get(
        f"/collections/{sample_collection.id}/documents",
        headers=auth_headers_viewer
    )
    
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_upload_document_as_owner(client, sample_collection, auth_headers_admin):
    """Test uploading document as collection owner"""
    # Create a fake PDF file
    pdf_content = b"Fake PDF content for testing"
    files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {"title": "Test Upload Document"}
    
    response = client.post(
        f"/collections/{sample_collection.id}/documents",
        headers=auth_headers_admin,
        files=files,
        data=data
    )
    
    assert response.status_code == 201
    doc_data = response.json()
    
    assert doc_data["title"] == "Test Upload Document"
    assert doc_data["status"] == "pending"  # Should start as pending
    assert doc_data["collection_id"] == sample_collection.id


def test_upload_document_invalid_file_type(client, sample_collection, auth_headers_admin):
    """Test uploading non-PDF file returns 400"""
    files = {"file": ("test.txt", io.BytesIO(b"Not a PDF"), "text/plain")}
    data = {"title": "Invalid File"}
    
    response = client.post(
        f"/collections/{sample_collection.id}/documents",
        headers=auth_headers_admin,
        files=files,
        data=data
    )
    
    assert response.status_code == 400
    assert "Only PDF files" in response.json()["detail"]


def test_upload_document_as_viewer_forbidden(client, sample_collection, collection_membership, auth_headers_viewer):
    """Test uploading document as viewer returns 403"""
    files = {"file": ("test.pdf", io.BytesIO(b"PDF content"), "application/pdf")}
    data = {"title": "Forbidden Upload"}
    
    response = client.post(
        f"/collections/{sample_collection.id}/documents",
        headers=auth_headers_viewer,
        files=files,
        data=data
    )
    
    assert response.status_code == 403
    assert "Contributor access required" in response.json()["detail"]


def test_delete_document_as_owner(client, sample_collection, sample_document, auth_headers_admin):
    """Test deleting document as collection owner"""
    response = client.delete(
        f"/collections/{sample_collection.id}/documents/{sample_document.id}",
        headers=auth_headers_admin
    )
    
    assert response.status_code == 204


def test_delete_document_not_found(client, sample_collection, auth_headers_admin):
    """Test deleting non-existent document returns 404"""
    response = client.delete(
        f"/collections/{sample_collection.id}/documents/999",
        headers=auth_headers_admin
    )
    
    assert response.status_code == 404
    assert "Document not found" in response.json()["detail"]
