from app.demo import ACTIVITIES, COMPANIES, CONTACTS, DEALS, seed_demo


def test_demo_data_is_served_by_the_api(client, session):
    assert seed_demo(session) is True

    assert client.get("/companies").json()["total"] == len(COMPANIES)
    assert client.get("/contacts").json()["total"] == len(CONTACTS)
    assert client.get("/deals").json()["total"] == len(DEALS)
    pipeline = {s["stage"]: s["deals"] for s in client.get("/deals/pipeline").json()}
    assert pipeline["won"] == 1
    assert pipeline["lost"] == 1


def test_demo_contacts_have_a_consistent_timeline(client, session):
    seed_demo(session)
    sarah = client.get("/contacts", params={"q": "klein"}).json()["items"][0]

    timeline = client.get(f"/contacts/{sarah['id']}/activities").json()

    assert timeline["total"] == sum(1 for a in ACTIVITIES if a[0] == 0)
    assert timeline["items"][0]["subject"] == "Demo with the tech team"
    assert sarah["last_contacted_at"] is not None


def test_demo_seed_never_touches_existing_data(client, session):
    client.post("/companies", json={"name": "Mine"})

    assert seed_demo(session) is False
    assert client.get("/companies").json()["total"] == 1
