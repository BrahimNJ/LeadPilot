from app.models import Contact


def make_company(client, **overrides):
    payload = {"name": "Acme", "domain": "acme.example.com", "industry": "Retail", "size": "51-200"}
    response = client.post("/companies", json=payload | overrides)
    assert response.status_code == 201, response.text
    return response.json()


def make_contact(client, **overrides):
    payload = {"first_name": "Camille", "last_name": "Martin", "email": "camille@example.com"}
    response = client.post("/contacts", json=payload | overrides)
    assert response.status_code == 201, response.text
    return response.json()


def test_company_crud(client):
    company = make_company(client)

    assert client.get(f"/companies/{company['id']}").json()["name"] == "Acme"

    updated = client.put(f"/companies/{company['id']}", json={"name": "Acme SAS"})
    assert updated.json()["name"] == "Acme SAS"

    assert client.delete(f"/companies/{company['id']}").status_code == 204
    assert client.get(f"/companies/{company['id']}").status_code == 404


def test_company_domain_is_unique(client):
    make_company(client)

    response = client.post("/companies", json={"name": "Copycat", "domain": "acme.example.com"})

    assert response.status_code == 409
    assert "acme.example.com" in response.json()["detail"]


def test_contact_linked_to_company(client):
    company = make_company(client)
    contact = make_contact(client, company_id=company["id"], role="Head of Sales")

    listed = client.get("/contacts", params={"company_id": company["id"]}).json()

    assert listed["total"] == 1
    assert listed["items"][0]["id"] == contact["id"]


def test_contact_with_unknown_company_is_rejected(client):
    response = client.post(
        "/contacts",
        json={"first_name": "A", "last_name": "B", "email": "a@example.org", "company_id": 999},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "company 999 not found"


def test_contact_email_is_unique_and_validated(client):
    make_contact(client)

    duplicate = client.post(
        "/contacts", json={"first_name": "C", "last_name": "M", "email": "camille@example.com"}
    )
    invalid = client.post(
        "/contacts", json={"first_name": "C", "last_name": "M", "email": "not-an-email"}
    )

    assert duplicate.status_code == 409
    assert invalid.status_code == 422


def test_contact_search_and_pagination(client):
    for i in range(5):
        make_contact(client, first_name=f"User{i}", last_name="Durand", email=f"u{i}@example.org")
    make_contact(client, first_name="Lea", last_name="Petit", email="lea@example.org")

    page = client.get("/contacts", params={"q": "durand", "limit": 2, "offset": 2}).json()

    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert client.get("/contacts", params={"q": "LEA"}).json()["total"] == 1


def test_deleting_a_company_keeps_its_contacts(client):
    company = make_company(client)
    contact = make_contact(client, company_id=company["id"])

    assert client.delete(f"/companies/{company['id']}").status_code == 204

    assert client.get(f"/contacts/{contact['id']}").json()["company_id"] is None


def test_deleting_a_contact_removes_its_deals_and_activities(client):
    contact = make_contact(client)
    deal = client.post(
        "/deals", json={"title": "Pilot", "amount": 5000, "contact_id": contact["id"]}
    ).json()
    client.post(f"/contacts/{contact['id']}/activities", json={"kind": "call", "subject": "Intro"})

    assert client.delete(f"/contacts/{contact['id']}").status_code == 204

    assert client.get(f"/deals/{deal['id']}").status_code == 404
    assert client.get("/deals").json()["total"] == 0


def test_company_search_matches_name_and_domain(client):
    make_company(client)
    make_company(client, name="Brightwave", domain="brightwave.example.org")
    make_company(client, name="Nordlicht", domain=None)

    assert client.get("/companies", params={"q": "BRIGHT"}).json()["total"] == 1
    assert client.get("/companies", params={"q": "example.org"}).json()["total"] == 1
    assert client.get("/companies", params={"q": "example"}).json()["total"] == 2
    assert client.get("/companies").json()["total"] == 3


def test_company_contacts_are_listed_by_name(client):
    company = make_company(client)
    make_contact(
        client,
        first_name="Zoe",
        last_name="Roux",
        email="zoe@example.com",
        company_id=company["id"],
    )
    make_contact(
        client,
        first_name="Hugo",
        last_name="Blanc",
        email="hugo@example.com",
        company_id=company["id"],
    )
    make_contact(client, first_name="Solo", last_name="Free", email="solo@example.com")

    page = client.get(f"/companies/{company['id']}/contacts").json()

    assert page["total"] == 2
    assert [c["last_name"] for c in page["items"]] == ["Blanc", "Roux"]
    assert client.get("/companies/999/contacts").status_code == 404


def test_contacts_filtered_by_minimum_score(client, session):
    hot = make_contact(client, email="hot@example.com")
    warm = make_contact(client, email="warm@example.com")
    make_contact(client, email="unscored@example.com")
    session.get(Contact, hot["id"]).score = 85
    session.get(Contact, warm["id"]).score = 50
    session.commit()

    page = client.get("/contacts", params={"min_score": 60}).json()

    assert [c["email"] for c in page["items"]] == ["hot@example.com"]
    assert client.get("/contacts", params={"min_score": 50}).json()["total"] == 2
    assert client.get("/contacts", params={"min_score": 101}).status_code == 422


def test_search_wildcards_are_plain_text(client):
    make_contact(client, first_name="Ana", last_name="Lopez", email="ana@example.com")
    make_company(client, name="Acme", domain=None)

    assert client.get("/contacts", params={"q": "%"}).json()["total"] == 0
    assert client.get("/contacts", params={"q": "a_a"}).json()["total"] == 0
    assert client.get("/companies", params={"q": "%"}).json()["total"] == 0
    assert client.get("/contacts", params={"q": "ana"}).json()["total"] == 1


def test_search_terms_are_limited_in_length(client):
    assert client.get("/contacts", params={"q": "x" * 100}).status_code == 200
    assert client.get("/contacts", params={"q": "x" * 101}).status_code == 422
    assert client.get("/companies", params={"q": "x" * 101}).status_code == 422
