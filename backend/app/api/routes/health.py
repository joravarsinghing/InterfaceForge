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


async def _check_gemini() -> ServiceStatusRow:
    model = settings.gemini_vision_model
    if not settings.gemini_api_key:
        return ServiceStatusRow(
            id="gemini_vision",
            label="Gemini Vision",
            status="Not configured",
            message="Gemini API key is not configured.",
            model=model,
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={settings.gemini_api_key}"
    try:
        payload = await asyncio.to_thread(_http_json, url, None, 2.0)
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = {
            str(item.get("name", "")).split("/")[-1]
            for item in models
            if isinstance(item, dict)
        }
        if names and model not in names:
            return ServiceStatusRow(
                id="gemini_vision",
                label="Gemini Vision",
                status="Unavailable",
                message="Configured Gemini model was not found in model listing.",
                model=model,
            )
        return ServiceStatusRow(
            id="gemini_vision",
            label="Gemini Vision",
            status="Available",
            message="Authenticated model listing succeeded.",
            model=model,
        )
    except Exception as exc:
        return ServiceStatusRow(
            id="gemini_vision",
            label="Gemini Vision",
            status="Unavailable",
            message=_safe_unavailable_message("Gemini Vision", exc),
            model=model,
        )


async def _check_openrouter() -> ServiceStatusRow:
    primary_model = settings.openrouter_vision_model
    fallback_model = settings.openrouter_vision_fallback_model
    if not settings.openrouter_api_key:
        return ServiceStatusRow(
            id="openrouter_vision",
            label="OpenRouter Vision fallback",
            status="Not configured",
            message="OpenRouter API key is not configured.",
            model=f"{primary_model} / {fallback_model}",
        )

    url = f"{settings.openrouter_api_base_url.rstrip('/')}/models"
    headers = {"Authorization": "Bearer " + settings.openrouter_api_key}
    try:
        payload = await asyncio.to_thread(_http_json, url, headers, 2.0)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        ids = {str(item.get("id", "")) for item in rows if isinstance(item, dict)}
        configured = [m for m in (primary_model, fallback_model) if m]
        if ids and configured and not any(model in ids for model in configured):
            return ServiceStatusRow(
                id="openrouter_vision",
                label="OpenRouter Vision fallback",
                status="Unavailable",
                message="Configured OpenRouter vision model was not found in model listing.",
                model=f"{primary_model} / {fallback_model}",
            )
        return ServiceStatusRow(
            id="openrouter_vision",
            label="OpenRouter Vision fallback",
            status="Available",
            message="Authenticated model listing succeeded.",
            model=f"{primary_model} / {fallback_model}",
        )
    except Exception as exc:
        return ServiceStatusRow(
            id="openrouter_vision",
            label="OpenRouter Vision fallback",
            status="Unavailable",
            message=_safe_unavailable_message("OpenRouter", exc),
            model=f"{primary_model} / {fallback_model}",
        )


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
        _check_gemini(),
        _check_openrouter(),
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
