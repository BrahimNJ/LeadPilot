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
