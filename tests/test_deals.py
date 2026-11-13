import csv
import io

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


def test_deleted_deal_leaves_the_pipeline(client, contact):
    deal = make_deal(client, contact, amount=7000)

    assert client.delete(f"/deals/{deal['id']}").status_code == 204

    assert client.get(f"/deals/{deal['id']}").status_code == 404
    lead = next(s for s in client.get("/deals/pipeline").json() if s["stage"] == "lead")
    assert lead == {"stage": "lead", "deals": 0, "amount": 0}
    assert client.delete(f"/deals/{deal['id']}").status_code == 404


def test_overdue_lists_open_deals_past_their_close_date(client, contact):
    late = make_deal(client, contact, title="Late", expected_close="2020-01-31")
    make_deal(client, contact, title="Future", expected_close="2999-12-31")
    make_deal(client, contact, title="No date")
    lost = make_deal(client, contact, title="Lost late", expected_close="2020-01-31")
    client.post(f"/deals/{lost['id']}/stage", json={"stage": "lost"})

    page = client.get("/deals", params={"overdue": "true"}).json()

    assert [d["id"] for d in page["items"]] == [late["id"]]
    assert client.get("/deals").json()["total"] == 4


def test_export_deals_as_csv_with_filters(client, contact):
    make_deal(client, contact, title="=cmd|' /C calc'!A0", amount=500)
    late = make_deal(client, contact, title="Late", expected_close="2020-01-31")

    everything = client.get("/deals/export")
    overdue = client.get("/deals/export", params={"overdue": "true"})

    assert everything.status_code == 200
    assert everything.headers["content-type"].startswith("text/csv")
    assert "leadpilot-deals.csv" in everything.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(everything.text)))
    assert [r["title"] for r in rows] == ["Late", "'=cmd|' /C calc'!A0"]
    assert rows[0]["contact"] == "Nora Benali"
    assert rows[0]["expected_close"] == "2020-01-31"
    assert rows[1]["expected_close"] == ""
    late_rows = list(csv.DictReader(io.StringIO(overdue.text)))
    assert [int(r["id"]) for r in late_rows] == [late["id"]]
