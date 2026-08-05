"""Tests for backend health, readiness, middleware, and exception handling."""

import urllib.error

import pytest
from fastapi.testclient import TestClient

from app.api.routes import health as health_route
from app.core.config import settings


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
    assert set(payload["data"]["checks"]) == {"backend", "zoo_engine", "persistence"}
    assert payload["data"]["checks"]["backend"] == "Available"


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


def test_health_reports_independent_runtime_dependency_rows(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "zoo_api_token", "")
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()["data"]
    rows = {row["id"]: row for row in data["services"]}

    assert set(rows) == {"backend", "zoo_engine", "persistence"}
    assert rows["backend"]["status"] == "Available"
    assert rows["zoo_engine"]["status"] == "Not configured"
    assert rows["persistence"]["status"] == "Available"

    raw_text = response.text.lower()
    assert "api-test-token" not in raw_text
    assert "secret" not in raw_text
    assert "password" not in raw_text


def test_health_reports_available_zoo_without_secrets(
    client: TestClient, monkeypatch
) -> None:

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self, _size: int) -> bytes:
            import json

            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        url = request.full_url
        return FakeResponse({"id": "user"})
    monkeypatch.setattr(settings, "zoo_api_token", "zoo-secret-value")
    monkeypatch.setattr(health_route.urllib.request, "urlopen", fake_urlopen)

    response = client.get("/health")
    rows = {row["id"]: row for row in response.json()["data"]["services"]}
    assert set(rows) == {"backend", "zoo_engine", "persistence"}
    assert rows["zoo_engine"]["status"] == "Available"
    assert "gemini-secret-value" not in response.text
    assert "openrouter-secret-value" not in response.text
    assert "zoo-secret-value" not in response.text


def test_health_reports_timeout_as_unavailable(client: TestClient, monkeypatch) -> None:

    def fake_urlopen(_request, timeout=0):
        raise TimeoutError("timed out with hidden secret")
    monkeypatch.setattr(settings, "zoo_api_token", "zoo-secret-value")
    monkeypatch.setattr(health_route.urllib.request, "urlopen", fake_urlopen)

    response = client.get("/health")
    rows = {row["id"]: row for row in response.json()["data"]["services"]}
    assert rows["zoo_engine"]["status"] == "Unavailable"
    assert "timed out" in rows["zoo_engine"]["message"]
    assert "secret" not in response.text.lower()


def test_health_reports_persistence_not_configured(client: TestClient, monkeypatch) -> None:

    monkeypatch.setattr(settings, "db_path", "")
    response = client.get("/health")
    rows = {row["id"]: row for row in response.json()["data"]["services"]}

    assert rows["persistence"]["status"] == "Not configured"

class _ZooFakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, _size: int) -> bytes:
        return self.payload


def _zoo_row(response) -> dict:
    rows = response.json()["data"]["services"]
    return {row["id"]: row for row in rows}["zoo_engine"]


def _disable_non_zoo_provider_checks(monkeypatch) -> None:
    return None

def test_zoo_health_uses_user_endpoint_and_bearer_auth_without_account_data(
    client: TestClient, monkeypatch
) -> None:
    _disable_non_zoo_provider_checks(monkeypatch)
    monkeypatch.setattr(settings, "zoo_api_token", "  zoo-secret-value  ")
    monkeypatch.setattr(settings, "zoo_api_base_url", "https://wrong.example/v0")
    seen: dict[str, str | float | None] = {}

    def fake_urlopen(request, timeout=0):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["user_agent"] = request.get_header("User-agent")
        seen["accept"] = request.get_header("Accept")
        seen["timeout"] = timeout
        return _ZooFakeResponse(
            b'{"email":"owner@example.com","discord":"hidden",'
            b'"github":"secret-gh","username":"private-user"}'
        )

    monkeypatch.setattr(health_route.urllib.request, "urlopen", fake_urlopen)

    response = client.get("/health")
    row = _zoo_row(response)

    assert row["status"] == "Available"
    assert seen == {
        "url": "https://api.zoo.dev/user",
        "authorization": "Bearer zoo-secret-value",
        "user_agent": "InterfaceForge/0.1 health-check",
        "accept": "application/json",
        "timeout": 2.0,
    }
    body = response.text.lower()
    assert "zoo-secret-value" not in body
    assert "bearer" not in body
    assert "owner@example.com" not in body
    assert "discord" not in body
    assert "secret-gh" not in body
    assert "private-user" not in body


def test_zoo_health_missing_token_is_not_configured_without_probe(
    client: TestClient, monkeypatch
) -> None:
    _disable_non_zoo_provider_checks(monkeypatch)
    monkeypatch.setattr(settings, "zoo_api_token", "")

    def fake_urlopen(_request, timeout=0):
        raise AssertionError("Zoo health should not call Zoo without a token")

    monkeypatch.setattr(health_route.urllib.request, "urlopen", fake_urlopen)

    response = client.get("/health")

    assert _zoo_row(response)["status"] == "Not configured"


@pytest.mark.parametrize("status_code", [401, 403])
def test_zoo_health_auth_failures_are_sanitized_unavailable(
    client: TestClient, monkeypatch, status_code: int
) -> None:
    _disable_non_zoo_provider_checks(monkeypatch)
    monkeypatch.setattr(settings, "zoo_api_token", "zoo-secret-value")

    def fake_urlopen(request, timeout=0):
        raise urllib.error.HTTPError(
            request.full_url,
            status_code,
            "secret account body should not leak",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(health_route.urllib.request, "urlopen", fake_urlopen)

    response = client.get("/health")
    row = _zoo_row(response)

    assert row["status"] == "Unavailable"
    assert row["message"] == f"Zoo Authentication returned HTTP {status_code}."
    body = response.text.lower()
    assert "zoo-secret-value" not in body
    assert "secret account body" not in body


def test_zoo_health_timeout_is_sanitized_unavailable(client: TestClient, monkeypatch) -> None:
    _disable_non_zoo_provider_checks(monkeypatch)
    monkeypatch.setattr(settings, "zoo_api_token", "zoo-secret-value")

    def fake_urlopen(_request, timeout=0):
        raise TimeoutError("timed out with account owner@example.com and token")

    monkeypatch.setattr(health_route.urllib.request, "urlopen", fake_urlopen)

    response = client.get("/health")
    row = _zoo_row(response)

    assert row["status"] == "Unavailable"
    assert row["message"] == "Zoo Authentication check timed out."
    body = response.text.lower()
    assert "zoo-secret-value" not in body
    assert "owner@example.com" not in body
