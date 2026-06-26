def test_chat_with_collection(client, sample_collection, sample_chunk, collection_membership, auth_headers_viewer, mock_bedrock):
    """Test asking a question in a collection"""
    response = client.post(
        f"/collections/{sample_collection.id}/chat",
        headers=auth_headers_viewer,
        json={"message": "What are the company policies?"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "answer" in data
    assert "confidence" in data
    assert "session_id" in data
    assert "citations" in data
    assert isinstance(data["refused"], bool)
    
    # Mock should return test answer
    assert "Test answer" in data["answer"]


def test_chat_no_collection_access(client, sample_collection, auth_headers_viewer, mock_bedrock):
    """Test chatting with collection without access returns 403"""
    response = client.post(
        f"/collections/{sample_collection.id}/chat",
        headers=auth_headers_viewer,
        json={"message": "What are the policies?"}
    )
    
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_chat_continue_session(client, sample_collection, sample_chunk, collection_membership, auth_headers_viewer, mock_bedrock, db):
    """Test continuing an existing chat session"""
    # First chat to create session
    response1 = client.post(
        f"/collections/{sample_collection.id}/chat",
        headers=auth_headers_viewer,
        json={"message": "First question"}
    )
    
    assert response1.status_code == 200
    session_id = response1.json()["session_id"]
    
    # Continue with same session
    response2 = client.post(
        f"/collections/{sample_collection.id}/chat",
        headers=auth_headers_viewer,
        json={
            "message": "Follow-up question",
            "session_id": session_id
        }
    )
    
    assert response2.status_code == 200
    assert response2.json()["session_id"] == session_id


def test_get_chat_history(client, sample_collection, collection_membership, auth_headers_viewer, mock_bedrock):
    """Test getting chat history for a session"""
    # Create a chat session first
    chat_response = client.post(
        f"/collections/{sample_collection.id}/chat",
        headers=auth_headers_viewer,
        json={"message": "Test question"}
    )
    
    assert chat_response.status_code == 200
    session_id = chat_response.json()["session_id"]
    
    # Get chat history
    response = client.get(
        f"/collections/{sample_collection.id}/chat/{session_id}",
        headers=auth_headers_viewer
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) >= 2  # User message + assistant response
    
    # Check user message
    user_msg = next((msg for msg in data if msg["is_user"]), None)
    assert user_msg is not None
    assert user_msg["content"] == "Test question"
    
    # Check assistant message
    assistant_msg = next((msg for msg in data if not msg["is_user"]), None)
    assert assistant_msg is not None
    assert "Test answer" in assistant_msg["content"]


def test_get_chat_history_invalid_session(client, sample_collection, collection_membership, auth_headers_viewer):
    """Test getting history for non-existent session returns 404"""
    response = client.get(
        f"/collections/{sample_collection.id}/chat/999",
        headers=auth_headers_viewer
    )
    
    assert response.status_code == 404
    assert "Chat session not found" in response.json()["detail"]


def test_chat_unauthorized(client, sample_collection):
    """Test chatting without authentication returns 401"""
    response = client.post(
        f"/collections/{sample_collection.id}/chat",
        json={"message": "Test question"}
    )
    
    assert response.status_code == 401
