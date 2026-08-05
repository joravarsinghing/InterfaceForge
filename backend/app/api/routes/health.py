"""Health and runtime dependency status endpoints."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import urllib.error
import urllib.request
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings

ServiceState = Literal["Available", "Not configured", "Unavailable", "Checking"]
ZOO_HEALTH_URL = "https://api.zoo.dev/user"


class ServiceStatusRow(BaseModel):
    """Safe per-service dependency status for the frontend."""

    id: str
    label: str
    status: ServiceState
    message: str
    model: Optional[str] = None


class HealthData(BaseModel):
    """Safe health response metadata."""

    service_name: str
    status: str
    environment: str
    version: str
    services: list[ServiceStatusRow] = Field(default_factory=list)


class ResponseEnvelope(BaseModel):
    """Standard success response envelope."""

    success: bool = True
    data: Dict[str, Any]


router = APIRouter(tags=["Health"])


def _safe_unavailable_message(service: str, exc: BaseException) -> str:
    """Return a short sanitized error classification without secret-bearing details."""
    if isinstance(exc, TimeoutError):
        return f"{service} check timed out."
    if isinstance(exc, urllib.error.HTTPError):
        return f"{service} returned HTTP {exc.code}."
    if isinstance(exc, urllib.error.URLError):
        return f"{service} could not be reached."
    return f"{service} check failed."


def _http_json(url: str, headers: Optional[dict[str, str]] = None, timeout: float = 2.0) -> Any:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(1024 * 1024)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


async def _check_zoo() -> ServiceStatusRow:
    token = (settings.zoo_api_token or "").strip()
    if not token:
        return ServiceStatusRow(
            id="zoo_engine",
            label="Zoo Authentication",
            status="Not configured",
            message="Zoo API token is not configured.",
        )

    headers = {
        "Authorization": "Bearer " + token,
        "User-Agent": "InterfaceForge/0.1 health-check",
        "Accept": "application/json",
    }
    try:
        payload = await asyncio.to_thread(_http_json, ZOO_HEALTH_URL, headers, 2.0)
        if payload is None:
            return ServiceStatusRow(
                id="zoo_engine",
                label="Zoo Authentication",
                status="Unavailable",
                message="Zoo Authentication returned an invalid health response.",
            )
        return ServiceStatusRow(
            id="zoo_engine",
            label="Zoo Authentication",
            status="Available",
            message="Authenticated Zoo API user probe succeeded.",
        )
    except Exception as exc:
        return ServiceStatusRow(
            id="zoo_engine",
            label="Zoo Authentication",
            status="Unavailable",
            message=_safe_unavailable_message("Zoo Authentication", exc),
        )


async def _check_persistence() -> ServiceStatusRow:
    if not settings.db_path:
        return ServiceStatusRow(
            id="persistence",
            label="Project persistence/storage",
            status="Not configured",
            message="Database path is not configured.",
        )
    try:
        def _probe() -> None:
            db_dir = os.path.dirname(os.path.abspath(settings.db_path))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            with sqlite3.connect(settings.db_path) as conn:
                conn.execute("SELECT 1")

        await asyncio.to_thread(_probe)
        return ServiceStatusRow(
            id="persistence",
            label="Project persistence/storage",
            status="Available",
            message="SQLite storage is reachable.",
        )
    except Exception:
        return ServiceStatusRow(
            id="persistence",
            label="Project persistence/storage",
            status="Unavailable",
            message="SQLite storage check failed.",
        )


async def collect_service_statuses() -> list[ServiceStatusRow]:
    """Collect independent runtime dependency statuses without exposing credentials."""
    backend = ServiceStatusRow(
        id="backend",
        label="InterfaceForge backend",
        status="Available",
        message="Backend API is responding.",
    )
    checks = await asyncio.gather(
        _check_zoo(),
        _check_persistence(),
    )
    return [backend, *checks]


@router.get("/health", response_model=ResponseEnvelope)
async def get_health() -> ResponseEnvelope:
    """Return safe application health metadata and independent dependency statuses."""
    services = await collect_service_statuses()
    health_info = HealthData(
        service_name=settings.app_name,
        status="ok",
        environment=settings.environment,
        version=settings.app_version,
        services=services,
    )
    return ResponseEnvelope(success=True, data=health_info.model_dump())


@router.get("/ready", response_model=ResponseEnvelope)
async def get_ready() -> ResponseEnvelope:
    """Return application readiness status."""
    services = await collect_service_statuses()
    ready_info = {
        "status": "ready",
        "service": settings.app_name,
        "checks": {row.id: row.status for row in services},
    }
    return ResponseEnvelope(success=True, data=ready_info)
