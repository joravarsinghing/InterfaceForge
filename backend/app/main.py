"""FastAPI Application Entry Point and Factory."""

import faulthandler
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes.generation import router as generation_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestIDMiddleware
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.generation_job_service import GenerationJobService

faulthandler.enable(file=sys.stderr)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="InterfaceForge Modular Monolith Backend API",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 1. Add Request ID Middleware
    app.add_middleware(RequestIDMiddleware)

    # 2. Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
    )

    # 3. Register Exception Handlers
    register_exception_handlers(app)

    # 4. Include API Routes
    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(generation_router)

    # 5. Bootstrap Database
    SQLiteProjectRepository()
    GenerationJobService().recover_abandoned_jobs()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
