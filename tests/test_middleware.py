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


def test_oversized_body_is_refused(client_with):
    client = client_with(MAX_BODY_BYTES="50")

    response = client.post("/companies", json={"name": "x" * 100})

    assert response.status_code == 413
    assert "X-Request-ID" in response.headers
    assert client.post("/companies", json={"name": "Small"}).status_code == 201


def test_chunked_body_is_refused(client_with):
    client = client_with(MAX_BODY_BYTES="50")

    response = client.post(
        "/companies",
        content=iter([b'{"name":', b'"x"}']),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 411


def test_rate_limit_answers_429_with_a_wait_time(client_with):
    client = client_with(RATE_LIMIT_PER_MINUTE="2")

    statuses = [client.get("/companies").status_code for _ in range(3)]
    refused = client.get("/companies")

    assert statuses == [200, 200, 429]
    assert refused.status_code == 429
    assert 1 <= int(refused.headers["Retry-After"]) <= 60
    assert "X-Request-ID" in refused.headers


def test_health_is_not_rate_limited(client_with):
    client = client_with(RATE_LIMIT_PER_MINUTE="1")

    assert [client.get("/health").status_code for _ in range(3)] == [200, 200, 200]


def test_a_forged_forwarded_header_does_not_escape_the_limit(client_with):
    client = client_with(RATE_LIMIT_PER_MINUTE="1", TRUST_FORWARDED_FOR="true")

    first = client.get("/companies", headers={"X-Forwarded-For": "1.1.1.1, 203.0.113.9"})
    second = client.get("/companies", headers={"X-Forwarded-For": "2.2.2.2, 203.0.113.9"})
    other = client.get("/companies", headers={"X-Forwarded-For": "203.0.113.10"})

    assert (first.status_code, second.status_code, other.status_code) == (200, 429, 200)


def test_forwarded_header_is_ignored_unless_trusted(client_with):
    client = client_with(RATE_LIMIT_PER_MINUTE="1")

    assert client.get("/companies", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.get("/companies", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429
