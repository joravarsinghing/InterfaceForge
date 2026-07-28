"""Centralized exception handling and error envelope definitions."""

from typing import Any, List, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorDetails(BaseModel):
    """Standardized error details payload per ADR-013."""

    id: str
    message: str
    details: Optional[Any] = None
    recovery_steps: List[str] = []


class ErrorResponse(BaseModel):
    """Standardized error envelope response format."""

    success: bool = False
    error: ErrorDetails


class APIError(Exception):
    """Base API exception with structured error metadata."""

    def __init__(
        self,
        error_id: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Any] = None,
        recovery_steps: Optional[List[str]] = None,
    ) -> None:
        self.error_id = error_id
        self.message = message
        self.status_code = status_code
        self.details = details
        self.recovery_steps = recovery_steps or ["Check input parameters and try again."]
        super().__init__(message)


# Domain-specific stable errors per ADR-013 & S3 specification


class ProjectNotFoundError(APIError):
    """Raised when a requested project ID does not exist."""

    def __init__(self, project_id: str) -> None:
        super().__init__(
            error_id="IF-PROJ-404",
            message=f"Project '{project_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            recovery_steps=["Verify the project ID and try creating a new project if needed."],
        )


class InvalidProjectTokenError(APIError):
    """Raised when an invalid project access token is provided."""

    def __init__(self) -> None:
        super().__init__(
            error_id="IF-AUTH-401",
            message="Invalid or missing project token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            recovery_steps=["Provide a valid X-Project-Token header matching project credentials."],
        )


class InvalidStateTransitionError(APIError):
    """Raised when a requested workflow state transition is disallowed."""

    def __init__(self, current_state: str, target_state: str, reason: str = "") -> None:
        msg = f"Cannot transition from '{current_state}' to '{target_state}'."
        if reason:
            msg += f" {reason}"
        super().__init__(
            error_id="IF-STATE-400",
            message=msg,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=[
                "Ensure project workflow prerequisites are fulfilled before transitioning."
            ],
        )


class MissingPrerequisiteError(APIError):
    """Raised when an action is attempted before required prerequisites are complete."""

    def __init__(self, message: str, recovery_steps: Optional[List[str]] = None) -> None:
        super().__init__(
            error_id="IF-PREREQ-400",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=recovery_steps or ["Complete required prerequisite steps first."],
        )


class InvalidInterfaceApprovalError(APIError):
    """Raised when interface approval rules are violated."""

    def __init__(self, message: str, recovery_steps: Optional[List[str]] = None) -> None:
        super().__init__(
            error_id="IF-APPROVAL-400",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=recovery_steps
            or ["Review interface parameters and confirm scale before approval."],
        )


class InvalidConnectionConfigError(APIError):
    """Raised when connection parameters violate manufacturing or geometric validation rules."""

    def __init__(
        self,
        message: str,
        error_id: str = "IF-CONN-400",
        details: Optional[Any] = None,
        recovery_steps: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            error_id=error_id,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            recovery_steps=recovery_steps
            or ["Adjust connection or manufacturing parameters to satisfy geometric limits."],
        )


class StaleModelOperationError(APIError):
    """Raised when performing an operation (e.g., export) on a stale or missing model."""

    def __init__(
        self, message: str = "Cannot perform operation because current model is stale or missing."
    ) -> None:
        super().__init__(
            error_id="IF-STALE-400",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=["Re-generate the 3D model with updated parameters before exporting."],
        )


class ExportFailedError(APIError):
    """Raised when CAD format export generation fails."""

    def __init__(
        self,
        message: str,
        error_id: str = "IF-EXPORT-001",
        recovery_steps: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            error_id=error_id,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=recovery_steps
            or ["Retry export for the failed format or check geometry parameters."],
        )


class UnsupportedExportFormatError(APIError):
    """Raised when an unsupported export format is requested."""

    def __init__(self, fmt: str) -> None:
        super().__init__(
            error_id="IF-EXPORT-002",
            message=f"Unsupported export format '{fmt}'. Supported formats are: stl, step, kcl.",
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=["Select a supported export format (stl, step, kcl)."],
        )


class ExportArtifactNotFoundError(APIError):
    """Raised when a requested export artifact file is missing or corrupted."""

    def __init__(self, message: str = "Export artifact not found or corrupted.") -> None:
        super().__init__(
            error_id="IF-EXPORT-004",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            recovery_steps=["Re-trigger export generation for this format."],
        )


class SchemaVersionMismatchError(APIError):
    """Raised when an unsupported schema version is supplied."""

    def __init__(self, provided_version: str, expected_version: str = "0.1") -> None:
        msg = f"Unsupported schema version '{provided_version}'. Expected '{expected_version}'."
        super().__init__(
            error_id="IF-SCHEMA-400",
            message=msg,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=["Update API client to pass a supported schema version."],
        )


class InvalidFileUploadError(APIError):
    """Raised when an uploaded file fails validation checks (type, size, corruption)."""

    def __init__(self, message: str, recovery_steps: Optional[List[str]] = None) -> None:
        super().__init__(
            error_id="IF-FILE-400",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=recovery_steps
            or ["Upload a valid image file (PNG, JPEG, WEBP under 10MB)."],
        )


class AnalysisRejectedError(APIError):
    """Raised when analysis rejects an image due to poor quality or unresolvable contour."""

    def __init__(self, message: str, recovery_steps: Optional[List[str]] = None) -> None:

        super().__init__(
            error_id="IF-ANALYSIS-400",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=recovery_steps
            or ["Upload a clearer, well-lit image facing the interface directly."],
        )


class MalformedProviderResponseError(APIError):
    """Raised when analysis provider returns a malformed data structure."""

    def __init__(self, message: str = "Analysis provider returned malformed response.") -> None:
        super().__init__(
            error_id="IF-ANALYSIS-400",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            recovery_steps=["Try re-running analysis or switching analysis provider."],
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers on the FastAPI application."""

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        content = ErrorResponse(
            error=ErrorDetails(
                id=exc.error_id,
                message=exc.message,
                details=exc.details,
                recovery_steps=exc.recovery_steps,
            )
        ).model_dump()
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        error_id = f"IF-HTTP-{exc.status_code}"
        content = ErrorResponse(
            error=ErrorDetails(
                id=error_id,
                message=str(exc.detail),
                recovery_steps=["Verify request path and headers."],
            )
        ).model_dump()
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        content = ErrorResponse(
            error=ErrorDetails(
                id="IF-VAL-422",
                message="Request validation error",
                details=exc.errors(),
                recovery_steps=["Ensure all required fields match the expected format."],
            )
        ).model_dump()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        content = ErrorResponse(
            error=ErrorDetails(
                id="IF-SYS-500",
                message="An unexpected internal server error occurred.",
                recovery_steps=[
                    "Retry request after a short delay.",
                    "Contact system support if issue persists.",
                ],
            )
        ).model_dump()
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content)
