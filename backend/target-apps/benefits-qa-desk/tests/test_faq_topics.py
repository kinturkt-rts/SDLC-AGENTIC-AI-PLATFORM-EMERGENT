"""FAQ topics endpoint tests."""


def test_create_faq_topic(client, contributor_headers, seed_users):
    resp = client.post(
        "/api/v1/faq-topics",
        json={"label": "Enrollment"},
        headers=contributor_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Enrollment"


def test_create_faq_topic_duplicate(client, contributor_headers, seed_users):
    client.post(
        "/api/v1/faq-topics",
        json={"label": "DupTopic"},
        headers=contributor_headers,
    )
    resp = client.post(
        "/api/v1/faq-topics",
        json={"label": "DupTopic"},
        headers=contributor_headers,
    )
    assert resp.status_code == 409


def test_list_faq_topics(client, employee_headers, contributor_headers, seed_users):
    client.post(
        "/api/v1/faq-topics",
        json={"label": "Vision"},
        headers=contributor_headers,
    )
    resp = client.get("/api/v1/faq-topics", headers=employee_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_create_faq_topic_employee_forbidden(client, employee_headers, seed_users):
    resp = client.post(
        "/api/v1/faq-topics",
        json={"label": "Blocked"},
        headers=employee_headers,
    )
    assert resp.status_code == 403
