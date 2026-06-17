"""Tests for FAQ endpoints."""


def test_list_faqs_empty(client):
    response = client.get("/faqs")
    assert response.status_code == 200
    assert response.json() == []


def test_create_faq_unauthenticated(client):
    response = client.post(
        "/faqs",
        json={"category": "test", "question": "Q?", "answer": "A."},
    )
    assert response.status_code == 401


def test_create_faq_staff(client, staff_headers):
    response = client.post(
        "/faqs",
        json={"category": "office_hours", "question": "Are you open?", "answer": "Yes we are."},
        headers=staff_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["category"] == "office_hours"
    assert data["question"] == "Are you open?"
    assert data["is_active"] is True


def test_list_faqs_after_create(client, staff_headers):
    client.post(
        "/faqs",
        json={"category": "insurance", "question": "Do you take Aetna?", "answer": "Yes."},
        headers=staff_headers,
    )
    response = client.get("/faqs")
    assert response.status_code == 200
    faqs = response.json()
    assert len(faqs) >= 1


def test_list_faqs_filter_category(client, staff_headers):
    client.post(
        "/faqs",
        json={"category": "insurance", "question": "Q1?", "answer": "A1"},
        headers=staff_headers,
    )
    client.post(
        "/faqs",
        json={"category": "parking", "question": "Q2?", "answer": "A2"},
        headers=staff_headers,
    )
    response = client.get("/faqs?category=insurance")
    assert response.status_code == 200
    faqs = response.json()
    assert all(f["category"] == "insurance" for f in faqs)


def test_update_faq_unauthenticated(client, staff_headers):
    # Create first
    create_resp = client.post(
        "/faqs",
        json={"category": "test", "question": "Old Q?", "answer": "Old A."},
        headers=staff_headers,
    )
    faq_id = create_resp.json()["id"]
    # Try update without auth
    response = client.put(f"/faqs/{faq_id}", json={"question": "New Q?"})
    assert response.status_code == 401


def test_update_faq_staff(client, staff_headers):
    create_resp = client.post(
        "/faqs",
        json={"category": "test", "question": "Old Q?", "answer": "Old A."},
        headers=staff_headers,
    )
    faq_id = create_resp.json()["id"]
    response = client.put(
        f"/faqs/{faq_id}",
        json={"question": "New Q?", "is_active": False},
        headers=staff_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "New Q?"
    assert data["is_active"] is False


def test_update_faq_not_found(client, staff_headers):
    response = client.put(
        "/faqs/99999",
        json={"question": "New Q?"},
        headers=staff_headers,
    )
    assert response.status_code == 404
