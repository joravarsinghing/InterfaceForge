"""Focused tests for project-scoped mock/live provider mode selection."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.models.schema import ProviderMode
from app.services.engine_provider import MockEngineProvider, ZooEngineProvider, get_engine_provider
from app.services.project_service import ProjectService


def test_created_project_has_readable_name_and_mock_mode(client: TestClient) -> None:
    response = client.post("/api/projects")
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["display_name"] == "Adapter 1"
    assert data["provider_mode"] == "mock"


def test_mock_mode_persists_without_schema_revision_change(client: TestClient) -> None:
    created = client.post("/api/projects").json()["data"]
    headers = {"X-Project-Token": created["project_token"]}

    response = client.patch(
        f"/api/projects/{created['project_id']}/provider-mode",
        json={"provider_mode": "mock"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["project"]["provider_mode"] == "mock"
    assert payload["project"]["current_schema_revision"] == 1
    assert payload["provider_status"]["effective_mode"] == "mock"

    reloaded = client.get(f"/api/projects/{created['project_id']}", headers=headers).json()["data"]
    assert reloaded["provider_mode"] == "mock"
    assert reloaded["display_name"] == "Adapter 1"


def test_live_mode_rejected_without_backend_credentials(client: TestClient) -> None:
    settings.zoo_api_token = ""
    created = client.post("/api/projects").json()["data"]
    headers = {"X-Project-Token": created["project_token"]}

    response = client.patch(
        f"/api/projects/{created['project_id']}/provider-mode",
        json={"provider_mode": "live"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["id"] == "IF-PROVIDER-409"
    reloaded = client.get(f"/api/projects/{created['project_id']}", headers=headers).json()["data"]
    assert reloaded["provider_mode"] == "mock"


def test_live_mode_uses_live_engine_provider_when_credentials_exist(temp_db) -> None:
    settings.zoo_api_token = "api-test-token"
    settings.engine_provider = "mock"
    service = ProjectService(repository=SQLiteProjectRepository(db_path=str(temp_db)))
    project = service.create_project()

    saved, mode_status = service.set_provider_mode(project.project_id, provider_mode=ProviderMode.LIVE)

    assert saved.provider_mode == "live"
    assert mode_status.effective_mode == "live"
    assert isinstance(get_engine_provider(saved.provider_mode.value), ZooEngineProvider)
    assert isinstance(get_engine_provider("mock"), MockEngineProvider)
    settings.zoo_api_token = ""

def test_pre_project_provider_mode_status_does_not_create_project(client: TestClient) -> None:
    settings.zoo_api_token = ""

    response = client.patch("/api/projects/provider-mode", json={"provider_mode": "mock"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["selected_mode"] == "mock"
    assert data["effective_mode"] == "mock"
    assert client.get("/api/projects/provider-mode").status_code == 200


def test_pre_project_live_mode_rejected_without_credentials(client: TestClient) -> None:
    settings.zoo_api_token = ""

    response = client.patch("/api/projects/provider-mode", json={"provider_mode": "live"})

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"]["id"] == "IF-PROVIDER-409"
    assert "credentials" in payload["error"]["message"]


def test_create_project_inherits_requested_live_mode_when_available(client: TestClient) -> None:
    settings.zoo_api_token = "api-test-token"

    response = client.post("/api/projects", json={"provider_mode": "live"})

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["provider_mode"] == "live"
    headers = {"X-Project-Token": data["project_token"]}
    mode = client.get(f"/api/projects/{data['project_id']}/provider-mode", headers=headers).json()["data"]
    assert mode["selected_mode"] == "live"
    assert mode["effective_mode"] == "live"
    settings.zoo_api_token = ""


def test_create_project_rejects_requested_live_mode_when_unavailable(client: TestClient) -> None:
    settings.zoo_api_token = ""

    response = client.post("/api/projects", json={"provider_mode": "live"})

    assert response.status_code == 409
    assert response.json()["error"]["id"] == "IF-PROVIDER-409"

