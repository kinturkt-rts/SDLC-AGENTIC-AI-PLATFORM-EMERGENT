"""Tests for customer endpoints."""
import pytest


@pytest.fixture()
def create_customer_payload():
    return {
        "full_name": "Test Customer",
        "phone": "555-000-1234",
        "email": "test@example.com",
        "service_addresses": [
            {
                "street": "100 Main St",
                "city": "Columbus",
                "state": "OH",
                "postal_code": "43215",
            }
        ],
    }


def test_create_customer_dispatcher(client, seed_users, create_customer_payload):
    resp = client.post(
        "/customers",
        json=create_customer_payload,
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Test Customer"
    assert len(data["service_addresses"]) == 1
    assert data["is_active"] is True


def test_create_customer_owner_forbidden(client, seed_users, create_customer_payload):
    resp = client.post(
        "/customers",
        json=create_customer_payload,
        headers=seed_users["owner_headers"],
    )
    assert resp.status_code == 403


def test_get_customer(client, seed_users, create_customer_payload):
    # Create first
    create_resp = client.post(
        "/customers",
        json=create_customer_payload,
        headers=seed_users["dispatcher_headers"],
    )
    customer_id = create_resp.json()["id"]

    # Get
    resp = client.get(
        f"/customers/{customer_id}",
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == customer_id


def test_patch_customer(client, seed_users, create_customer_payload):
    create_resp = client.post(
        "/customers",
        json=create_customer_payload,
        headers=seed_users["dispatcher_headers"],
    )
    customer_id = create_resp.json()["id"]

    resp = client.patch(
        f"/customers/{customer_id}",
        json={"phone": "555-999-0000"},
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "555-999-0000"


def test_get_customer_not_found(client, seed_users):
    resp = client.get(
        "/customers/00000000-0000-0000-0000-000000000000",
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 404
