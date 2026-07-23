from config import health


def test_liveness_returns_service_status(client):
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "backend"}


def test_request_id_is_preserved_when_valid(client):
    response = client.get("/health/live", headers={"X-Request-ID": "test-request-123"})

    assert response.headers["X-Request-ID"] == "test-request-123"


def test_request_id_is_replaced_when_invalid(client):
    response = client.get("/health/live", headers={"X-Request-ID": "invalid request id"})

    assert response.headers["X-Request-ID"] != "invalid request id"
    assert response.headers["X-Request-ID"]


def test_readiness_returns_each_dependency(monkeypatch, client):
    monkeypatch.setattr(
        health,
        "DEPENDENCY_CHECKS",
        {
            "database": lambda: None,
            "redis": lambda: None,
            "object_storage": lambda: None,
        },
    )

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "backend",
        "checks": {
            "database": "ok",
            "redis": "ok",
            "object_storage": "ok",
        },
    }


def test_readiness_is_unavailable_when_dependency_fails(monkeypatch, client):
    def unavailable():
        raise ConnectionError("not reachable")

    monkeypatch.setattr(
        health,
        "DEPENDENCY_CHECKS",
        {
            "database": lambda: None,
            "redis": unavailable,
            "object_storage": lambda: None,
        },
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["checks"]["redis"] == "unavailable"
