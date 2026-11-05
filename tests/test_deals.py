import pytest


@pytest.fixture
def contact(client):
    response = client.post(
        "/contacts", json={"first_name": "Nora", "last_name": "Benali", "email": "nora@example.com"}
    )
    return response.json()


def make_deal(client, contact, **overrides):
    payload = {"title": "Kibo onboarding", "amount": 12000, "contact_id": contact["id"]}
    response = client.post("/deals", json=payload | overrides)
    assert response.status_code == 201, response.text
    return response.json()


def test_new_deal_starts_as_lead(client, contact):
    deal = make_deal(client, contact)

    assert deal["stage"] == "lead"
    assert deal["closed_at"] is None


def test_deal_needs_an_existing_contact(client):
    response = client.post("/deals", json={"title": "Ghost", "amount": 10, "contact_id": 42})

    assert response.status_code == 422


def test_deal_moves_forward_until_won(client, contact):
    deal = make_deal(client, contact)

    for stage in ("qualified", "proposal", "negotiation", "won"):
        response = client.post(f"/deals/{deal['id']}/stage", json={"stage": stage})
        assert response.status_code == 200, response.text

    assert response.json()["closed_at"] is not None


def test_moving_back_is_refused_with_a_reason(client, contact):
    deal = make_deal(client, contact)
    client.post(f"/deals/{deal['id']}/stage", json={"stage": "proposal"})

    response = client.post(f"/deals/{deal['id']}/stage", json={"stage": "qualified"})

    assert response.status_code == 422
    assert response.json()["detail"] == "cannot move a deal back from proposal to qualified"


def test_pipeline_summary_lists_every_stage(client, contact):
    make_deal(client, contact, amount=1000)
    make_deal(client, contact, amount=500)
    other = make_deal(client, contact, amount=3000)
    client.post(f"/deals/{other['id']}/stage", json={"stage": "lost"})

    summary = {row["stage"]: row for row in client.get("/deals/pipeline").json()}

    assert list(summary) == ["lead", "qualified", "proposal", "negotiation", "won", "lost"]
    assert summary["lead"] == {"stage": "lead", "deals": 2, "amount": 1500}
    assert summary["lost"]["amount"] == 3000
    assert summary["won"]["deals"] == 0


def test_list_deals_filters_by_stage(client, contact):
    make_deal(client, contact)
    lost = make_deal(client, contact)
    client.post(f"/deals/{lost['id']}/stage", json={"stage": "lost"})

    page = client.get("/deals", params={"stage": "lost"}).json()

    assert page["total"] == 1
    assert page["items"][0]["id"] == lost["id"]


def test_update_deal_details_keeps_its_stage(client, contact):
    deal = make_deal(client, contact)
    client.post(f"/deals/{deal['id']}/stage", json={"stage": "qualified"})

    response = client.put(
        f"/deals/{deal['id']}",
        json={
            "title": "Kibo onboarding, 2 sites",
            "amount": 18000,
            "contact_id": contact["id"],
            "expected_close": "2027-03-31",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["amount"] == 18000
    assert updated["expected_close"] == "2027-03-31"
    assert updated["stage"] == "qualified"


def test_update_deal_checks_the_contact(client, contact):
    deal = make_deal(client, contact)

    response = client.put(f"/deals/{deal['id']}", json={"title": "x", "amount": 1, "contact_id": 9})

    assert response.status_code == 422
    missing = client.put(
        "/deals/999", json={"title": "x", "amount": 1, "contact_id": contact["id"]}
    )
    assert missing.status_code == 404
