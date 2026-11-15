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


def test_agenda_filters_by_due_date_across_contacts(client, contact):
    other = client.post(
        "/contacts", json={"first_name": "Tom", "last_name": "Weiss", "email": "tom@example.com"}
    ).json()
    add_task(client, contact, title="Late", due_date=in_days(-1))
    add_task(client, other, title="Today", due_date=in_days(0))
    add_task(client, contact, title="In 6 days", due_date=in_days(6))
    add_task(client, other, title="In 7 days", due_date=in_days(7))
    add_task(client, contact, title="Someday")

    def titles(**params):
        return [t["title"] for t in client.get("/tasks", params=params).json()["items"]]

    assert titles() == ["Late", "Today", "In 6 days", "In 7 days", "Someday"]
    assert titles(due="overdue") == ["Late"]
    assert titles(due="today") == ["Today"]
    assert titles(due="week") == ["Today", "In 6 days"]
    assert titles(done="true") == []
    assert client.get("/tasks", params={"due": "tomorrow"}).status_code == 422


def test_complete_and_reopen_a_task(client, contact):
    task = add_task(client, contact, due_date=in_days(-1))

    done = client.post(f"/tasks/{task['id']}/complete").json()
    again = client.post(f"/tasks/{task['id']}/complete").json()
    reopened = client.post(f"/tasks/{task['id']}/reopen").json()

    assert done["status"] == "done"
    assert done["done_at"] is not None
    assert again["done_at"] == done["done_at"]
    assert reopened["status"] == "overdue"
    assert reopened["done_at"] is None
    assert client.post("/tasks/999/complete").status_code == 404


def test_edit_and_delete_a_task(client, contact):
    task = add_task(client, contact)

    edited = client.put(
        f"/tasks/{task['id']}", json={"title": "Send the revised proposal", "due_date": in_days(0)}
    ).json()

    assert edited["title"] == "Send the revised proposal"
    assert edited["status"] == "today"
    assert client.get(f"/tasks/{task['id']}").json() == edited
    assert (
        client.put(f"/tasks/{task['id']}", json={"title": "x", "deal_id": 999}).status_code == 422
    )
    assert client.delete(f"/tasks/{task['id']}").status_code == 204
    assert client.get(f"/tasks/{task['id']}").status_code == 404
