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
