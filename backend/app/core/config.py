"""Application configuration module using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings derived from environment variables or defaults."""

    app_name: str = "InterfaceForge Backend"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    host: str = "127.0.0.1"
    port: int = 8000
    db_path: str = "artifacts/interfaceforge.db"

    # Zoo Engine API Configuration per ADR-006 and ADR-009
    engine_provider: str = "mock"
    zoo_api_token: str = ""
    zoo_api_base_url: str = "https://api.zoo.dev"
    generation_timeout_seconds: float = 30.0

    # Vision Analysis Provider Configuration per ADR-003, ADR-009, and S7.1
    analysis_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_vision_model: str = "gemini-3.5-flash-lite"
    gemini_vision_fallback_model: str = "gemini-3.6-flash"
    gemini_vision_fallback_enabled: bool = True
    gemini_model: str = "gemini-3.5-flash-lite"
    analysis_timeout_seconds: float = 30.0

    # OpenRouter Vision fallback status configuration. Backend-only; never exposed raw.
    openrouter_api_key: str = ""
    openrouter_api_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_vision_model: str = "google/gemini-2.5-flash-image-preview"
    openrouter_vision_fallback_model: str = "openai/gpt-4o-mini"

    # File Format Export Provider Configuration per ADR-006 and S8
    export_provider: str = "mock"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_effective_engine_provider(self) -> str:
        """Validate engine provider settings safely.

        If 'zoo' is specified without a token, safely fall back to 'mock'.
        """
        provider = (self.engine_provider or "mock").lower()
        if provider == "zoo" and not self.zoo_api_token:
            return "mock"
        return provider

    def get_effective_analysis_provider(self) -> str:
        """Validate analysis provider settings safely.

        If 'gemini' is specified without an API key, safely fall back to 'mock'.
        """
        provider = (self.analysis_provider or "mock").lower()
        if provider == "gemini" and not self.gemini_api_key:
            return "mock"
        return provider

    def get_effective_export_provider(self) -> str:
        """Validate export provider settings safely.

        If 'zoo' is specified without a token, safely fall back to 'mock'.
        """
        provider = (self.export_provider or "mock").lower()
        if provider == "zoo" and not self.zoo_api_token:
            return "mock"
        return provider


settings = Settings()
