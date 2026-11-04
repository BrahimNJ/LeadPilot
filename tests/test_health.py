from app import __version__


def test_health_reports_version_and_database(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "database": "ok"}
