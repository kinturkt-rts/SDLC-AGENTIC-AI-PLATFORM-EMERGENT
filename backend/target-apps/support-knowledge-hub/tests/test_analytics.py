"""Analytics endpoint tests."""


def test_get_gaps_admin(client, seed_users, db_session):
    from app.models.search_log import SearchLog

    # Seed some search logs with weak results
    sl = SearchLog(
        id="e5000000-0000-0000-0000-000000000050",
        user_id_hash="hash_test",
        query_text="contractor onboarding",
        result_count=0,
    )
    db_session.add(sl)
    db_session.commit()

    headers = {"Authorization": f"Bearer {seed_users['admin_token']}"}
    resp = client.get("/api/v1/analytics/gaps", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["query_text"] == "contractor onboarding"
    assert data[0]["weak_result_count"] >= 1


def test_get_gaps_forbidden_for_employee(client, seed_users):
    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.get("/api/v1/analytics/gaps", headers=headers)
    assert resp.status_code == 403


def test_get_gaps_leadership(client, seed_users, db_session):
    from app.models.search_log import SearchLog

    sl = SearchLog(
        id="e5000000-0000-0000-0000-000000000051",
        user_id_hash="hash_test2",
        query_text="parking pass",
        result_count=0,
    )
    db_session.add(sl)
    db_session.commit()

    headers = {"Authorization": f"Bearer {seed_users['leadership_token']}"}
    resp = client.get("/api/v1/analytics/gaps", headers=headers)
    assert resp.status_code == 200
