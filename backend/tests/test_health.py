"""Tests for backend health, readiness, middleware, and exception handling."""

from fastapi.testclient import TestClient


def test_health_endpoint_returns_safe_data(client: TestClient) -> None:
    """Verify GET /health returns 200 OK and only safe system metadata."""
    response = client.get("/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert "data" in payload

    data = payload["data"]
    assert data["service_name"] == "InterfaceForge Backend"
    assert data["status"] == "ok"
    assert data["environment"] == "development"
    assert data["version"] == "0.1.0"

    # Ensure no internal paths or sensitive details exposed
    raw_text = response.text.lower()
    assert "c:\\" not in raw_text
    assert "/home/" not in raw_text
    assert "secret" not in raw_text
    assert "password" not in raw_text


def test_ready_endpoint(client: TestClient) -> None:
    """Verify GET /ready returns 200 OK with readiness status."""
    response = client.get("/ready")
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "ready"
    assert payload["data"]["service"] == "InterfaceForge Backend"
    assert payload["data"]["checks"]["api"] == "healthy"


def test_request_id_middleware(client: TestClient) -> None:
    """Verify X-Request-ID header is present in responses and preserved if supplied."""
    # Test auto-generated request ID
    res1 = client.get("/health")
    assert res1.status_code == 200
    assert "x-request-id" in res1.headers
    req_id_1 = res1.headers["x-request-id"]
    assert len(req_id_1) > 0

    # Test preserved request ID
    custom_id = "test-request-id-12345"
    res2 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res2.status_code == 200
    assert res2.headers.get("x-request-id") == custom_id


def test_404_error_envelope(client: TestClient) -> None:
    """Verify 404 response follows standard error envelope structure."""
    response = client.get("/nonexistent-endpoint")
    assert response.status_code == 404

    payload = response.json()
    assert payload["success"] is False
    assert "error" in payload
    assert payload["error"]["id"] == "IF-HTTP-404"
    assert "recovery_steps" in payload["error"]
