"""QA edge-case tests — inventory-app.

Covers PRD acceptance criteria and design §4/§5 gaps not addressed by the
developer baseline.  Each test follows the AAA (Arrange / Act / Assert)
pattern with exactly one behaviour per test.

Gap areas addressed:
  - Health: exact service name value (FR-1)
  - Auth: input validation edge cases (FR-2)
  - Categories: 422 validation, 404/409 PATCH paths, pagination shape, anon 401 (FR-3/4)
  - Products: missing 404 paths, staff PATCH 403, category/sku filter, unit_price ≤ 0
    validation, `qty_on_hand` truly absent from PATCH schema (FR-5/6)
  - Adjust-stock: invalid reason enum 422, note max-length 422, movements 404 (FR-7/8)
  - Delete product: unknown id 404 (FR-9)
"""

from __future__ import annotations

import uuid

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealthEdgeCases:
    """FR-1 exact body contract."""

    def test_health_service_name_exact(self, client):
        """Service name must be exactly 'inventory-desk' per FR-1 and design §4."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["service"] == "inventory-desk"

    def test_health_status_exact_ok(self, client):
        """Status field must be exactly the string 'ok' (not 'OK' or True)."""
        r = client.get("/health")
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth — input validation edge cases (FR-2)
# ---------------------------------------------------------------------------

class TestAuthValidation:
    """Input validation / 422 cases for POST /auth/login."""

    def test_login_missing_username_422(self, client):
        """Login body without username field must return 422."""
        r = client.post("/auth/login", json={"password": "Admin123!"})
        assert r.status_code == 422

    def test_login_missing_password_422(self, client):
        """Login body without password field must return 422."""
        r = client.post("/auth/login", json={"username": "admin"})
        assert r.status_code == 422

    def test_login_empty_body_422(self, client):
        """Empty JSON body must return 422."""
        r = client.post("/auth/login", json={})
        assert r.status_code == 422

    def test_login_empty_username_422(self, client, seeded):
        """Empty-string username violates min_length=1 → 422 (LoginRequest schema).

        This is a Pydantic validation error, not an auth failure.  401 is only
        returned when the credentials are structurally valid but wrong.
        """
        r = client.post("/auth/login", json={"username": "", "password": "Admin123!"})
        assert r.status_code == 422

    def test_login_empty_password_422(self, client, seeded):
        """Empty-string password violates min_length=1 → 422 (LoginRequest schema)."""
        r = client.post("/auth/login", json={"username": "admin", "password": ""})
        assert r.status_code == 422

    def test_login_response_has_all_fields(self, client, seeded):
        """Successful login response must contain all four documented fields (FR-2)."""
        r = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) >= {"access_token", "token_type", "role", "expires_in"}


# ---------------------------------------------------------------------------
# Categories — input validation (FR-4)
# ---------------------------------------------------------------------------

class TestCategoryValidation:
    """422 validation edge cases for category endpoints."""

    def test_create_category_empty_name_422(self, client, auth_headers):
        """name='' violates min_length=1 → 422."""
        r = client.post(
            "/categories",
            headers=auth_headers("admin"),
            json={"name": ""},
        )
        assert r.status_code == 422

    def test_create_category_name_too_long_422(self, client, auth_headers):
        """name > 80 chars violates max_length → 422."""
        r = client.post(
            "/categories",
            headers=auth_headers("admin"),
            json={"name": "A" * 81},
        )
        assert r.status_code == 422

    def test_create_category_explicit_slug_used(self, client, auth_headers):
        """When slug is supplied explicitly it must be used verbatim (lowered/stripped)."""
        r = client.post(
            "/categories",
            headers=auth_headers("admin"),
            json={"name": "Outdoor Tools", "slug": "outdoor-tools"},
        )
        assert r.status_code == 201
        assert r.json()["slug"] == "outdoor-tools"


# ---------------------------------------------------------------------------
# Categories — 403 / 404 / 409 paths (FR-3, FR-4)
# ---------------------------------------------------------------------------

class TestCategoryAccessAndErrors:
    """Role / resource error paths for category endpoints."""

    def test_anon_get_categories_list_401(self, client, seeded):
        """No token on GET /categories must return 401 (FR-3)."""
        r = client.get("/categories")
        assert r.status_code == 401

    def test_anon_get_category_detail_401(self, client, seeded):
        """No token on GET /categories/{id} must return 401 (FR-3)."""
        r = client.get(f"/categories/{seeded['category_id']}")
        assert r.status_code == 401

    def test_patch_unknown_category_404(self, client, auth_headers):
        """PATCH a non-existent category UUID must return 404 (FR-4)."""
        r = client.patch(
            "/categories/00000000-0000-0000-0000-000000000001",
            headers=auth_headers("admin"),
            json={"name": "Ghost"},
        )
        assert r.status_code == 404

    def test_patch_category_slug_collision_409(self, client, auth_headers):
        """PATCH a category slug to one already used by another category → 409."""
        headers = auth_headers("admin")
        # Create two categories.
        r1 = client.post("/categories", headers=headers, json={"name": "Slug Alpha"})
        assert r1.status_code == 201
        r2 = client.post("/categories", headers=headers, json={"name": "Slug Beta"})
        assert r2.status_code == 201
        cat2_id = r2.json()["id"]
        # Try to rename cat2's slug to cat1's slug.
        r_patch = client.patch(
            f"/categories/{cat2_id}",
            headers=headers,
            json={"slug": "slug-alpha"},
        )
        assert r_patch.status_code == 409

    def test_staff_cannot_patch_category_403(self, client, auth_headers, seeded):
        """Staff PATCH on any category must return 403 (FR-3)."""
        r = client.patch(
            f"/categories/{seeded['category_id']}",
            headers=auth_headers("staff"),
            json={"name": "Attempted rename"},
        )
        assert r.status_code == 403

    def test_list_categories_pagination_shape(self, client, auth_headers):
        """GET /categories pagination envelope fields must be correct types (FR-6)."""
        r = client.get("/categories?limit=5&offset=0", headers=auth_headers("admin"))
        assert r.status_code == 200
        body = r.json()
        assert body["limit"] == 5
        assert body["offset"] == 0
        assert isinstance(body["items"], list)
        assert isinstance(body["total"], int)


# ---------------------------------------------------------------------------
# Products — missing 404 paths, staff PATCH 403, filters (FR-5/6/9)
# ---------------------------------------------------------------------------

class TestProductEdgeCases:
    """Edge cases for product CRUD not covered by developer baseline."""

    def test_get_unknown_product_404(self, client, auth_headers):
        """GET /products/{unknown} must return 404 (FR-5)."""
        r = client.get(
            "/products/00000000-0000-0000-0000-000000000002",
            headers=auth_headers("admin"),
        )
        assert r.status_code == 404

    def test_patch_unknown_product_404(self, client, auth_headers):
        """PATCH /products/{unknown} must return 404 (FR-5)."""
        r = client.patch(
            "/products/00000000-0000-0000-0000-000000000003",
            headers=auth_headers("admin"),
            json={"name": "Phantom"},
        )
        assert r.status_code == 404

    def test_staff_cannot_patch_product_403(self, client, auth_headers, seeded):
        """Staff PATCH on a product must return 403 (FR-3/FR-5)."""
        r = client.patch(
            f"/products/{seeded['product_id']}",
            headers=auth_headers("staff"),
            json={"name": "Staff rename attempt"},
        )
        assert r.status_code == 403

    def test_delete_unknown_product_404(self, client, auth_headers):
        """DELETE /products/{unknown} must return 404 (FR-9)."""
        r = client.delete(
            "/products/00000000-0000-0000-0000-000000000004",
            headers=auth_headers("admin"),
        )
        assert r.status_code == 404

    def test_create_product_negative_price_422(self, client, auth_headers, seeded):
        """unit_price < 0 must be rejected with 422 (schema ge=0)."""
        r = client.post(
            "/products",
            headers=auth_headers("admin"),
            json={
                "category_id": str(seeded["category_id"]),
                "sku": "NEG-PRICE",
                "name": "Negative Price Item",
                "unit_price": "-1.00",
            },
        )
        assert r.status_code == 422

    def test_create_product_zero_price_allowed(self, client, auth_headers, seeded):
        """unit_price == 0 is valid per PRD open question 3 (ge=0, not gt=0)."""
        r = client.post(
            "/products",
            headers=auth_headers("admin"),
            json={
                "category_id": str(seeded["category_id"]),
                "sku": "FREE-001",
                "name": "Free Sample",
                "unit_price": "0.00",
            },
        )
        assert r.status_code == 201
        assert r.json()["unit_price"] == "0.00"

    def test_create_product_empty_sku_422(self, client, auth_headers, seeded):
        """sku='' violates min_length=1 → 422."""
        r = client.post(
            "/products",
            headers=auth_headers("admin"),
            json={
                "category_id": str(seeded["category_id"]),
                "sku": "",
                "name": "Empty SKU",
                "unit_price": "1.00",
            },
        )
        assert r.status_code == 422

    def test_list_products_category_filter(self, client, auth_headers, seeded):
        """GET /products?category_id=<id> returns only products in that category (FR-6)."""
        r = client.get(
            f"/products?category_id={seeded['category_id']}",
            headers=auth_headers("admin"),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        for item in body["items"]:
            assert item["category_id"] == str(seeded["category_id"])

    def test_list_products_sku_filter(self, client, auth_headers, seeded):
        """GET /products?sku=ELEC-001 returns the single matching product (FR-6)."""
        r = client.get("/products?sku=ELEC-001", headers=auth_headers("staff"))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["sku"] == "ELEC-001"

    def test_list_products_sku_filter_no_match(self, client, auth_headers):
        """GET /products?sku=<nonexistent> returns empty items with total=0."""
        r = client.get("/products?sku=NO-SUCH-SKU-XXXX", headers=auth_headers("staff"))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_anon_cannot_list_products_401(self, client, seeded):
        """No token on GET /products must return 401 (FR-3)."""
        r = client.get("/products")
        assert r.status_code == 401

    def test_product_created_qty_on_hand_always_zero(self, client, auth_headers, seeded):
        """New product qty_on_hand=0 even when caller sends qty_on_hand in the body (FR-5)."""
        r = client.post(
            "/products",
            headers=auth_headers("admin"),
            json={
                "category_id": str(seeded["category_id"]),
                "sku": "FORCED-QTY",
                "name": "Force Qty Item",
                "unit_price": "5.00",
                # qty_on_hand is not a valid ProductCreate field; send it anyway to
                # confirm it is ignored by Pydantic and the handler.
                "qty_on_hand": 99,
            },
        )
        assert r.status_code == 201
        assert r.json()["qty_on_hand"] == 0


# ---------------------------------------------------------------------------
# Adjust-stock — validation edge cases (FR-7)
# ---------------------------------------------------------------------------

class TestAdjustStockValidation:
    """422 paths not covered by developer baseline."""

    def test_adjust_stock_invalid_reason_422(self, client, auth_headers, seeded):
        """Reason value not in enum ('drop') must return 422 (FR-7)."""
        r = client.post(
            f"/products/{seeded['product_id']}/adjust-stock",
            headers=auth_headers("staff"),
            json={"delta": 1, "reason": "drop"},
        )
        assert r.status_code == 422

    def test_adjust_stock_note_too_long_422(self, client, auth_headers, seeded):
        """note > 500 chars must return 422 (PRD §7 note max 500 chars)."""
        r = client.post(
            f"/products/{seeded['product_id']}/adjust-stock",
            headers=auth_headers("staff"),
            json={"delta": 1, "reason": "restock", "note": "x" * 501},
        )
        assert r.status_code == 422

    def test_adjust_stock_note_exactly_500_chars_allowed(self, client, auth_headers, seeded):
        """note exactly 500 chars must be accepted (boundary check)."""
        r = client.post(
            f"/products/{seeded['product_id']}/adjust-stock",
            headers=auth_headers("staff"),
            json={"delta": 1, "reason": "restock", "note": "x" * 500},
        )
        assert r.status_code == 200

    def test_adjust_stock_missing_reason_422(self, client, auth_headers, seeded):
        """Body without required `reason` field must return 422."""
        r = client.post(
            f"/products/{seeded['product_id']}/adjust-stock",
            headers=auth_headers("staff"),
            json={"delta": 1},
        )
        assert r.status_code == 422

    def test_adjust_stock_missing_delta_422(self, client, auth_headers, seeded):
        """Body without required `delta` field must return 422."""
        r = client.post(
            f"/products/{seeded['product_id']}/adjust-stock",
            headers=auth_headers("staff"),
            json={"reason": "sale"},
        )
        assert r.status_code == 422

    def test_adjust_stock_all_valid_reasons(self, client, auth_headers, seeded):
        """All three valid reason values ('sale', 'restock', 'adjustment') must be accepted."""
        pid = seeded["product_id"]
        headers = auth_headers("admin")

        # Start at qty=3; add 10 so we have enough for 'sale'
        r = client.post(
            f"/products/{pid}/adjust-stock",
            headers=headers,
            json={"delta": 10, "reason": "restock"},
        )
        assert r.status_code == 200, f"restock failed: {r.text}"

        r = client.post(
            f"/products/{pid}/adjust-stock",
            headers=headers,
            json={"delta": -2, "reason": "sale"},
        )
        assert r.status_code == 200, f"sale failed: {r.text}"

        r = client.post(
            f"/products/{pid}/adjust-stock",
            headers=headers,
            json={"delta": -1, "reason": "adjustment"},
        )
        assert r.status_code == 200, f"adjustment failed: {r.text}"


# ---------------------------------------------------------------------------
# Movement history — 404 and pagination offset (FR-8)
# ---------------------------------------------------------------------------

class TestMovementHistoryEdgeCases:
    """Edge cases for GET /products/{id}/movements."""

    def test_movements_unknown_product_404(self, client, auth_headers):
        """GET movements for unknown product must return 404 (FR-8)."""
        r = client.get(
            "/products/00000000-0000-0000-0000-000000000005/movements",
            headers=auth_headers("admin"),
        )
        assert r.status_code == 404

    def test_movements_anon_401(self, client, seeded):
        """No token on movements endpoint must return 401 (FR-3)."""
        r = client.get(f"/products/{seeded['product_id']}/movements")
        assert r.status_code == 401

    def test_movements_empty_for_new_product(self, client, auth_headers, seeded):
        """Fresh product has zero movements; endpoint returns empty paginated response."""
        r_create = client.post(
            "/products",
            headers=auth_headers("admin"),
            json={
                "category_id": str(seeded["category_id"]),
                "sku": "MOV-TEST-001",
                "name": "Movement Test Product",
                "unit_price": "1.00",
            },
        )
        assert r_create.status_code == 201
        pid = r_create.json()["id"]

        r = client.get(f"/products/{pid}/movements", headers=auth_headers("staff"))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_movements_pagination_offset(self, client, auth_headers, seeded):
        """offset=1 on 2 movements must return 1 item with total=2."""
        pid = seeded["product_id"]
        headers = auth_headers("admin")

        # Create exactly 2 movements.
        client.post(f"/products/{pid}/adjust-stock", headers=headers,
                    json={"delta": 1, "reason": "restock"})
        client.post(f"/products/{pid}/adjust-stock", headers=headers,
                    json={"delta": 1, "reason": "restock"})

        r = client.get(f"/products/{pid}/movements?limit=10&offset=1", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert len(body["items"]) == 1


# ---------------------------------------------------------------------------
# NFR-3 — role boundaries not yet asserted for movements
# ---------------------------------------------------------------------------

class TestRoleBoundaryMovements:
    """Staff has read/write access to stock operations but not catalog (FR-3)."""

    def test_staff_can_read_movements(self, client, auth_headers, seeded):
        """Staff may call GET /products/{id}/movements (FR-8)."""
        r = client.get(
            f"/products/{seeded['product_id']}/movements",
            headers=auth_headers("staff"),
        )
        assert r.status_code == 200

    def test_staff_can_adjust_stock_adjustment_reason(self, client, auth_headers, seeded):
        """Staff may use reason='adjustment' (all three reasons allowed per FR-7)."""
        r = client.post(
            f"/products/{seeded['product_id']}/adjust-stock",
            headers=auth_headers("staff"),
            json={"delta": 1, "reason": "adjustment"},
        )
        assert r.status_code == 200
