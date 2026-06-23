def test_list_collections(client, admin_user, sample_collection, auth_headers_admin):
    """Test listing collections for authenticated user"""
    response = client.get("/collections", headers=auth_headers_admin)
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) >= 1
    collection = data[0]
    assert collection["name"] == sample_collection.name
    assert collection["user_role"] == "contributor"  # Owner has contributor role
    assert "document_count" in collection


def test_create_collection_as_admin(client, auth_headers_admin):
    """Test creating collection as admin user"""
    response = client.post("/collections", 
        headers=auth_headers_admin,
        json={
            "name": "New Policy Collection",
            "description": "Test collection for policies"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["name"] == "New Policy Collection"
    assert data["description"] == "Test collection for policies"
    assert not data["archived"]


def test_create_collection_as_viewer_forbidden(client, auth_headers_viewer):
    """Test creating collection as viewer returns 403"""
    response = client.post("/collections",
        headers=auth_headers_viewer,
        json={
            "name": "Unauthorized Collection",
            "description": "This should fail"
        }
    )
    
    assert response.status_code == 403
    assert "Insufficient privileges" in response.json()["detail"]


def test_create_duplicate_collection_name(client, sample_collection, auth_headers_admin):
    """Test creating collection with duplicate name returns 400"""
    response = client.post("/collections",
        headers=auth_headers_admin,
        json={
            "name": sample_collection.name,  # Duplicate name
            "description": "This should fail"
        }
    )
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_list_collections_unauthorized(client):
    """Test listing collections without auth returns 401"""
    response = client.get("/collections")
    
    assert response.status_code == 401
