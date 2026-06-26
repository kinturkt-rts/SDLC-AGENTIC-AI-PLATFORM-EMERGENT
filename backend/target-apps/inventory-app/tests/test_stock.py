"""Adjust-stock and movement-history tests (FR-7, FR-8, NFR-6)."""

from __future__ import annotations

import time


def test_staff_can_adjust_stock_positive(client, auth_headers, seeded):
    """Staff records a restock; qty + movement persisted; performed_by=staff."""
    pid = seeded["product_id"]
    r = client.post(
        f"/products/{pid}/adjust-stock",
        headers=auth_headers("staff"),
        json={"delta": 2, "reason": "restock", "note": "weekly delivery"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["qty_on_hand"] == 5  # 3 + 2
    assert body["movement"]["delta"] == 2
    assert body["movement"]["reason"] == "restock"
    assert body["movement"]["performed_by"] == str(seeded["staff_id"])


def test_negative_qty_blocked_with_422_and_no_movement(client, auth_headers, seeded):
    """qty_on_hand must not go negative; 422 returned and no movement persisted (FR-7, NFR-6)."""
    pid = seeded["product_id"]
    headers = auth_headers("staff")

    r = client.post(
        f"/products/{pid}/adjust-stock",
        headers=headers,
        json={"delta": -5, "reason": "sale"},
    )
    assert r.status_code == 422

    # Product unchanged.
    r_get = client.get(f"/products/{pid}", headers=headers)
    assert r_get.json()["qty_on_hand"] == 3

    # No movement row written.
    r_hist = client.get(f"/products/{pid}/movements", headers=headers)
    assert r_hist.status_code == 200
    assert r_hist.json()["total"] == 0


def test_zero_delta_returns_422(client, auth_headers, seeded):
    pid = seeded["product_id"]
    r = client.post(
        f"/products/{pid}/adjust-stock",
        headers=auth_headers("staff"),
        json={"delta": 0, "reason": "adjustment"},
    )
    assert r.status_code == 422


def test_adjust_stock_unknown_product_404(client, auth_headers):
    r = client.post(
        "/products/00000000-0000-0000-0000-000000000000/adjust-stock",
        headers=auth_headers("admin"),
        json={"delta": 1, "reason": "restock"},
    )
    assert r.status_code == 404


def test_adjust_stock_requires_auth(client, seeded):
    r = client.post(
        f"/products/{seeded['product_id']}/adjust-stock",
        json={"delta": 1, "reason": "restock"},
    )
    assert r.status_code == 401


def test_movement_history_newest_first_with_pagination(client, auth_headers, seeded):
    """Multiple movements come back in DESC created_at order (FR-8).

    Sleep briefly between calls so SQLite's second-precision `CURRENT_TIMESTAMP`
    produces strictly distinct timestamps, making ordering deterministic.
    """
    pid = seeded["product_id"]
    headers = auth_headers("staff")

    for delta, reason in [(2, "restock"), (1, "restock"), (-1, "sale")]:
        r = client.post(
            f"/products/{pid}/adjust-stock",
            headers=headers,
            json={"delta": delta, "reason": reason},
        )
        assert r.status_code == 200, r.text
        time.sleep(1.05)  # enforce distinct second-precision timestamps on SQLite

    r = client.get(f"/products/{pid}/movements?limit=2&offset=0", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    timestamps = [item["created_at"] for item in body["items"]]
    assert timestamps == sorted(timestamps, reverse=True)
    # Newest must be the last one we created (delta=-1, reason=sale).
    assert body["items"][0]["reason"] == "sale"
