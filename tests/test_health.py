from app import __version__


def test_health_reports_version_and_database(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "database": "ok"}


def test_root_redirects_to_the_docs(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"
    assert "/" not in client.get("/openapi.json").json()["paths"]
