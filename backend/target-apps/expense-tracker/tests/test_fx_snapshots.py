"""FX Snapshot endpoint tests."""
from __future__ import annotations

from decimal import Decimal


class TestCreateFxSnapshot:
    def test_create_success(self, client, auth_as_admin):
        resp = client.post("/api/v1/fx-snapshots", json={
            "currency": "CAD",
            "date": "2024-07-01",
            "rate_to_usd": "0.7400",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["currency"] == "CAD"
        assert Decimal(str(data["rate_to_usd"])) == Decimal("0.7400")

    def test_create_upsert_existing(self, client, auth_as_admin, seed_fx):
        resp = client.post("/api/v1/fx-snapshots", json={
            "currency": "GBP",
            "date": "2024-06-01",
            "rate_to_usd": "1.3000",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert Decimal(str(data["rate_to_usd"])) == Decimal("1.3000")

    def test_create_forbidden_employee(self, client, auth_as_employee):
        resp = client.post("/api/v1/fx-snapshots", json={
            "currency": "USD",
            "date": "2024-07-01",
            "rate_to_usd": "1.0",
        })
        assert resp.status_code == 403
