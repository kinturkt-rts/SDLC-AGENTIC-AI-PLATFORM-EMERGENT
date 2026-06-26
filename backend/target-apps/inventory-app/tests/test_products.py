"""Product route tests (FR-5/6/9)."""

from __future__ import annotations


def test_admin_create_product(client, auth_headers, seeded):
    r = client.post(
        "/products",
        headers=auth_headers("admin"),
        json={
            "category_id": str(seeded["category_id"]),
            "sku": "ELEC-XYZ",
            "name": "USB Hub",
            "unit_price": "12.50",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["sku"] == "ELEC-XYZ"
    assert body["qty_on_hand"] == 0  # FR-5: always starts at zero


def test_create_product_duplicate_sku_409(client, auth_headers, seeded):
    headers = auth_headers("admin")
    payload = {
        "category_id": str(seeded["category_id"]),
        "sku": "DUP-001",
        "name": "Thing",
        "unit_price": "1.00",
    }
    assert client.post("/products", headers=headers, json=payload).status_code == 201
    r = client.post("/products", headers=headers, json=payload)
    assert r.status_code == 409


def test_create_product_unknown_category_404(client, auth_headers):
    r = client.post(
        "/products",
        headers=auth_headers("admin"),
        json={
            "category_id": "00000000-0000-0000-0000-000000000000",
            "sku": "GHOST-1",
            "name": "Phantom",
            "unit_price": "0.00",
        },
    )
    assert r.status_code == 404


def test_staff_cannot_create_product(client, auth_headers, seeded):
    r = client.post(
        "/products",
        headers=auth_headers("staff"),
        json={
            "category_id": str(seeded["category_id"]),
            "sku": "STAFF-NO",
            "name": "Forbidden",
            "unit_price": "0.00",
        },
    )
    assert r.status_code == 403


def test_patch_product_ignores_qty_on_hand(client, auth_headers, seeded):
    """qty_on_hand must NOT be settable via PATCH (FR-5)."""
    pid = seeded["product_id"]
    r = client.patch(
        f"/products/{pid}",
        headers=auth_headers("admin"),
        json={"name": "Renamed", "qty_on_hand": 999},  # extra field is ignored
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["qty_on_hand"] == 3  # unchanged from seed


def test_list_products_low_stock_filter(client, auth_headers, seeded):
    """low_stock=true returns only products with qty_on_hand <= 5 (FR-6)."""
    r = client.get(
        "/products?low_stock=true", headers=auth_headers("staff")
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all(item["qty_on_hand"] <= 5 for item in body["items"])


def test_list_products_pagination_envelope(client, auth_headers):
    r = client.get("/products?limit=10&offset=0", headers=auth_headers("admin"))
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"items", "total", "limit", "offset"}
    assert body["limit"] == 10
    assert body["offset"] == 0


def test_delete_product_with_stock_409(client, auth_headers, seeded):
    """Cannot delete a product with qty_on_hand > 0 (FR-9)."""
    r = client.delete(f"/products/{seeded['product_id']}", headers=auth_headers("admin"))
    assert r.status_code == 409


def test_delete_zero_stock_product_204(client, auth_headers, seeded):
    """After draining stock, admin can delete and product is 404 afterwards."""
    pid = seeded["product_id"]
    headers = auth_headers("admin")

    # Drain via adjust-stock (qty 3 -> 0)
    r = client.post(
        f"/products/{pid}/adjust-stock",
        headers=headers,
        json={"delta": -3, "reason": "sale", "note": "drain"},
    )
    assert r.status_code == 200, r.text

    r_del = client.delete(f"/products/{pid}", headers=headers)
    assert r_del.status_code == 204

    r_get = client.get(f"/products/{pid}", headers=headers)
    assert r_get.status_code == 404


def test_staff_cannot_delete_product(client, auth_headers, seeded):
    r = client.delete(f"/products/{seeded['product_id']}", headers=auth_headers("staff"))
    assert r.status_code == 403
