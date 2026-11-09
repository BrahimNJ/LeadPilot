from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_each_response_carries_a_request_id(client):
    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]

    assert len(first) == 32
    assert first != second


def test_a_safe_incoming_request_id_is_kept(client):
    response = client.get("/health", headers={"X-Request-ID": "lb-trace.42"})

    assert response.headers["X-Request-ID"] == "lb-trace.42"


def test_an_unsafe_incoming_request_id_is_replaced(client):
    response = client.get("/health", headers={"X-Request-ID": "x" * 65})

    assert response.headers["X-Request-ID"] != "x" * 65
    assert len(response.headers["X-Request-ID"]) == 32


def test_cors_is_off_by_default(client):
    response = client.get("/health", headers={"Origin": "https://evil.example.com"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_configured_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
    get_settings.cache_clear()
    try:
        app = create_app()
    finally:
        get_settings.cache_clear()

    preflight = TestClient(app).options(
        "/contacts",
        headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST"},
    )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://app.example.com"


def test_responses_carry_security_headers(client):
    headers = client.get("/health").headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "max-age=" in headers["Strict-Transport-Security"]
    assert headers["Content-Security-Policy"].startswith("default-src 'none'")


def test_interactive_docs_keep_working_without_the_csp(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
