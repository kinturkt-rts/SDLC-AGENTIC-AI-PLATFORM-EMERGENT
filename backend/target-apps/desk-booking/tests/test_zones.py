"""Zone endpoint tests."""


def test_list_zones(client, sample_zone):
    """GET /zones returns all zones."""
    response = client.get("/zones/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == sample_zone.id
    assert data[0]["name"] == "north"


def test_list_zones_empty(client):
    """GET /zones when no zones exist."""
    response = client.get("/zones/")
    assert response.status_code == 200
    assert response.json() == []
