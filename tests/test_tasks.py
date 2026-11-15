from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture
def contact(client):
    response = client.post(
        "/contacts", json={"first_name": "Lina", "last_name": "Haddad", "email": "lina@example.com"}
    )
    return response.json()


def in_days(n: int) -> str:
    # The API counts days in UTC, so the tests do too.
    return (datetime.now(UTC).date() + timedelta(days=n)).isoformat()


def add_task(client, contact, **fields):
    payload = {"title": "Send the proposal"} | fields
    response = client.post(f"/contacts/{contact['id']}/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_new_task_is_open_with_a_status(client, contact):
    dated = add_task(client, contact, due_date=in_days(3))
    undated = add_task(client, contact, title="Ask for an intro to the CFO")

    assert dated["status"] == "upcoming"
    assert dated["done_at"] is None
    assert dated["contact_id"] == contact["id"]
    assert undated["status"] == "someday"


def test_task_needs_a_title_and_an_existing_contact(client, contact):
    assert client.post(f"/contacts/{contact['id']}/tasks", json={"title": ""}).status_code == 422
    assert client.post("/contacts/999/tasks", json={"title": "x"}).status_code == 404


def test_task_deal_must_belong_to_the_same_contact(client, contact):
    other = client.post(
        "/contacts", json={"first_name": "Tom", "last_name": "Weiss", "email": "tom@example.com"}
    ).json()
    their_deal = client.post(
        "/deals", json={"title": "Theirs", "amount": 100, "contact_id": other["id"]}
    ).json()
    our_deal = client.post(
        "/deals", json={"title": "Ours", "amount": 100, "contact_id": contact["id"]}
    ).json()

    refused = client.post(
        f"/contacts/{contact['id']}/tasks", json={"title": "x", "deal_id": their_deal["id"]}
    )

    assert refused.status_code == 422
    assert add_task(client, contact, deal_id=our_deal["id"])["deal_id"] == our_deal["id"]


def test_contact_tasks_list_open_ones_first_soonest_first(client, contact, session):
    from app.models import Task

    later = add_task(client, contact, title="Later", due_date=in_days(5))
    someday = add_task(client, contact, title="Someday")
    soon = add_task(client, contact, title="Soon", due_date=in_days(1))
    done = add_task(client, contact, title="Done", due_date=in_days(-2))
    session.get(Task, done["id"]).done_at = datetime.now(UTC)
    session.commit()

    page = client.get(f"/contacts/{contact['id']}/tasks").json()
    open_only = client.get(f"/contacts/{contact['id']}/tasks", params={"done": "false"}).json()

    assert [t["title"] for t in page["items"]] == ["Soon", "Later", "Someday", "Done"]
    assert {t["id"] for t in open_only["items"]} == {later["id"], someday["id"], soon["id"]}
    assert client.get("/contacts/999/tasks").status_code == 404
