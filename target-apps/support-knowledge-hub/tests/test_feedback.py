"""Feedback endpoint tests."""
import hashlib


def test_submit_feedback(client, seed_users, seed_article, db_session):
    """Employee submits feedback on a published article."""
    from app.models.search_log import SearchLog

    # Create a search log first
    user_id_hash = hashlib.sha256(seed_users["employee_id"].encode()).hexdigest()
    sl = SearchLog(
        id="e5000000-0000-0000-0000-000000000099",
        user_id_hash=user_id_hash,
        query_text="vpn reset",
        result_count=1,
    )
    db_session.add(sl)
    db_session.commit()

    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.post(
        "/api/v1/feedback",
        json={"search_log_id": sl.id, "article_id": seed_article, "signal": "helpful"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["signal"] == "helpful"


def test_duplicate_feedback_409(client, seed_users, seed_article, db_session):
    """Duplicate feedback returns 409."""
    from app.models.search_log import SearchLog

    user_id_hash = hashlib.sha256(seed_users["employee_id"].encode()).hexdigest()
    sl = SearchLog(
        id="e5000000-0000-0000-0000-000000000098",
        user_id_hash=user_id_hash,
        query_text="vpn",
        result_count=1,
    )
    db_session.add(sl)
    db_session.commit()

    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    body = {"search_log_id": sl.id, "article_id": seed_article, "signal": "helpful"}
    resp1 = client.post("/api/v1/feedback", json=body, headers=headers)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/feedback", json=body, headers=headers)
    assert resp2.status_code == 409
