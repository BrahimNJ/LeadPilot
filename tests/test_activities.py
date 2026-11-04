import pytest


@pytest.fixture
def contact(client):
    response = client.post(
        "/contacts", json={"first_name": "Hugo", "last_name": "Leroy", "email": "hugo@nova.io"}
    )
    return response.json()


def log(client, contact, **fields):
    payload = {"kind": "call", "subject": "Discovery call"} | fields
    response = client.post(f"/contacts/{contact['id']}/activities", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_timeline_is_newest_first(client, contact):
    log(client, contact, subject="First call", occurred_at="2026-10-01T09:00:00Z")
    log(client, contact, kind="email", subject="Proposal sent", occurred_at="2026-10-08T14:30:00Z")
    log(
        client, contact, kind="note", subject="Budget confirmed", occurred_at="2026-10-05T10:00:00Z"
    )

    timeline = client.get(f"/contacts/{contact['id']}/activities").json()

    assert timeline["total"] == 3
    assert [a["subject"] for a in timeline["items"]] == [
        "Proposal sent",
        "Budget confirmed",
        "First call",
    ]


def test_last_contacted_follows_the_most_recent_activity(client, contact):
    log(client, contact, occurred_at="2026-10-08T14:30:00Z")
    log(client, contact, occurred_at="2026-09-01T08:00:00Z")  # logged late, happened earlier

    refreshed = client.get(f"/contacts/{contact['id']}").json()

    assert refreshed["last_contacted_at"].startswith("2026-10-08T14:30")


def test_activity_kind_and_timezone_are_validated(client, contact):
    url = f"/contacts/{contact['id']}/activities"

    unknown_kind = client.post(url, json={"kind": "fax", "subject": "Old school"})
    naive_date = client.post(
        url, json={"kind": "call", "subject": "When?", "occurred_at": "2026-10-01T09:00:00"}
    )

    assert unknown_kind.status_code == 422
    assert naive_date.status_code == 422


def test_unknown_contact_returns_404(client):
    assert client.get("/contacts/999/activities").status_code == 404
