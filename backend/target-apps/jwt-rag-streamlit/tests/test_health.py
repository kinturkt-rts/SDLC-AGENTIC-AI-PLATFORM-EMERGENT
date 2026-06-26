def test_health_check(client):
    """Test health endpoint returns OK status"""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ok"
    assert "checks" in data
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"
