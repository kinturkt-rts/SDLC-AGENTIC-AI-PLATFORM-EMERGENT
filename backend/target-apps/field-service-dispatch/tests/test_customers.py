"""Customer endpoint tests."""


def test_create_customer(client, dispatcher_headers):
    resp = client.post("/api/v1/customers", json={
        "full_name": "Test Customer",
        "phone": "555-1234",
        "email": "test@example.com",
        "street": "123 Main St",
        "city": "Columbus",
        "state": "OH",
        "zip": "43210"
    }, headers=dispatcher_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Test Customer"
    assert data["id"]


def test_list_customers(client, dispatcher_headers, seed_data):
    resp = client.get("/api/v1/customers", headers=dispatcher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_update_customer(client, dispatcher_headers, seed_data):
    cust_id = seed_data["customer_id"]
    resp = client.put(f"/api/v1/customers/{cust_id}", json={
        "phone": "555-9999"
    }, headers=dispatcher_headers)
    assert resp.status_code == 200
    assert resp.json()["phone"] == "555-9999"


def test_delete_customer(client, dispatcher_headers, seed_data):
    cust_id = seed_data["customer_id"]
    resp = client.delete(f"/api/v1/customers/{cust_id}", headers=dispatcher_headers)
    assert resp.status_code == 204


def test_no_auth_returns_401(client):
    resp = client.get("/api/v1/customers")
    assert resp.status_code == 401


def test_owner_can_list(client, owner_headers):
    resp = client.get("/api/v1/customers", headers=owner_headers)
    assert resp.status_code == 200


def test_owner_cannot_create(client, owner_headers):
    resp = client.post("/api/v1/customers", json={
        "full_name": "Blocked",
        "phone": "555-0000",
        "street": "1 Main",
        "city": "X",
        "state": "OH",
        "zip": "43000"
    }, headers=owner_headers)
    assert resp.status_code == 403
