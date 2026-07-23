import json
from pathlib import Path

from django.conf import settings
from drf_spectacular.generators import SchemaGenerator


def test_contract_success_fixture_preserves_correlation_id(client):
    response = client.get(
        "/api/v1/contract/fixture",
        {"outcome": "success"},
        headers={"X-Request-ID": "tp102-success"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "tp102-success"
    assert response.json() == {
        "status": "ok",
        "message": "API contract is available.",
        "correlation_id": "tp102-success",
    }


def test_contract_error_fixture_uses_shared_envelope(client):
    response = client.get(
        "/api/v1/contract/fixture",
        {"outcome": "error"},
        headers={"X-Request-ID": "tp102-error"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "contract_fixture_error",
        "message": "Requested the error contract fixture.",
        "fields": {"outcome": ["Use success to receive a successful response."]},
        "correlation_id": "tp102-error",
    }


def test_method_not_allowed_uses_shared_envelope(client):
    response = client.post(
        "/api/v1/contract/fixture",
        headers={"X-Request-ID": "tp102-method"},
    )

    assert response.status_code == 405
    assert response.json() == {
        "code": "method_not_allowed",
        "message": "HTTP-метод не підтримується.",
        "fields": {},
        "correlation_id": "tp102-method",
    }


def test_validation_error_uses_422_envelope(client):
    response = client.get(
        "/api/v1/contract/fixture",
        {"outcome": "unknown"},
        headers={"X-Request-ID": "tp102-validation"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "Дані запиту не пройшли перевірку.",
        "fields": {"outcome": ["Allowed values: success, error."]},
        "correlation_id": "tp102-validation",
    }


def test_schema_endpoint_exposes_contract_and_error_component(client):
    response = client.get("/api/v1/schema", headers={"Accept": "application/json"})

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/api/v1/contract/fixture"]["get"]
    assert operation["operationId"] == "contract_fixture_retrieve"
    assert "ErrorEnvelope" in schema["components"]["schemas"]
    assert "422" in operation["responses"]


def test_openapi_schema_matches_checked_in_snapshot():
    generated = SchemaGenerator().get_schema(request=None, public=True)
    snapshot_path = Path(settings.BASE_DIR) / "openapi" / "schema.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert generated == snapshot
