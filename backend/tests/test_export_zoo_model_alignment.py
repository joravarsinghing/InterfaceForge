"""Regression test suite for Stage S8.2 — Zoo Model Export Alignment.

Verifies end-to-end lineage tracking, prohibition of local OBJ generation in production,
cache key invalidation, model reference enforcement, and hash verification per S8.2.
"""

import hashlib
import os

import pytest

from app.core.exceptions import StaleModelOperationError
from app.models.schema import (
    Connection,
    ConnectionMode,
    ModelRevision,
    ModelRevisionStatus,
    Project,
    WorkflowState,
)
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.export_provider import MockExportProvider, ZooExportProvider
from app.services.geometry_generator import (
    generate_adapter_obj,
    get_local_obj_call_count,
    reset_local_obj_call_count,
    set_prohibit_local_obj,
)
from app.services.kcl_compiler import compile_project_to_kcl
from app.services.project_service import ProjectService


@pytest.fixture
def approved_project() -> Project:
    """Fixture providing an approved project ready for generation/export."""
    p = Project(
        project_id="test_s82_proj_12345678",
        project_token="tok_test_s82",
        current_schema_revision=1,
        current_model_revision=1,
        state=WorkflowState.MODEL_CURRENT,
    )
    p.interface_a.approved = True
    p.interface_b.approved = True
    p.connection = Connection(mode=ConnectionMode.COAXIAL, length_mm=40.0)
    return p


@pytest.mark.asyncio
async def test_export_requires_zoo_model_reference(approved_project: Project):
    """Verify ZooExportProvider rejects exports missing a valid Zoo Engine model reference."""
    provider = ZooExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)

    # Missing zoo_model_id must fail with IF-EXPORT-003
    res = await provider.export_format(
        project_id=approved_project.project_id,
        model_revision=1,
        format_name="stl",
        kcl_code=kcl_res.kcl_code,
        project=approved_project,
        zoo_model_id=None,  # Missing!
        kcl_hash=kcl_res.kcl_hash,
    )

    assert not res.success
    assert res.error_id == "IF-EXPORT-003"
    assert "Zoo Engine model reference" in res.error_message


def test_local_obj_path_cannot_run_in_production_mode(approved_project: Project):
    """Verify local generate_adapter_obj raises RuntimeError when prohibition guard is active."""
    set_prohibit_local_obj(True)
    try:
        with pytest.raises(RuntimeError, match="PRODUCTION EXPORT VIOLATION"):
            generate_adapter_obj(approved_project)
    finally:
        set_prohibit_local_obj(False)


@pytest.mark.asyncio
async def test_missing_zoo_model_fails_clearly(approved_project: Project):
    """Verify missing Zoo model reference returns clear error ID and recovery steps."""
    provider = ZooExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)

    res = await provider.export_format(
        project_id=approved_project.project_id,
        model_revision=1,
        format_name="step",
        kcl_code=kcl_res.kcl_code,
        project=approved_project,
        zoo_model_id="",  # Empty!
    )

    assert not res.success
    assert res.error_id == "IF-EXPORT-003"
    assert len(res.recovery_steps) > 0


@pytest.mark.asyncio
async def test_stale_or_mismatched_model_revision_fails(approved_project: Project, tmp_path):
    """Verify attempting export for a stale model revision raises StaleModelOperationError."""
    db_path = str(tmp_path / "test_s82_stale.db")
    repo = SQLiteProjectRepository(db_path=db_path)
    service = ProjectService(repository=repo)

    approved_project.state = WorkflowState.MODEL_STALE
    approved_project.model_revisions = [
        ModelRevision(
            model_revision=1,
            schema_revision=1,
            status=ModelRevisionStatus.STALE,
            zoo_model_id="zoo_sess_old",
        )
    ]
    repo.save(approved_project)

    with pytest.raises(StaleModelOperationError):
        await service.generate_exports(
            project_id=approved_project.project_id,
            formats=["stl"],
            project_token=approved_project.project_token,
        )


@pytest.mark.asyncio
async def test_kcl_hash_mismatch_fails(approved_project: Project):
    """Verify providing a mismatched KCL hash fails export with IF-EXPORT-005."""
    provider = ZooExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)

    fake_kcl_hash = hashlib.sha256(b"differing_kcl_code").hexdigest()

    res = await provider.export_format(
        project_id=approved_project.project_id,
        model_revision=1,
        format_name="stl",
        kcl_code=kcl_res.kcl_code,
        project=approved_project,
        zoo_model_id="zoo_sess_12345",
        kcl_hash=fake_kcl_hash,  # Mismatched!
    )

    assert not res.success
    assert res.error_id == "IF-EXPORT-005"
    assert "KCL hash mismatch" in res.error_message


@pytest.mark.asyncio
async def test_legacy_local_artifacts_are_invalidated(approved_project: Project):
    """Verify old S8.1 artifacts named without zoo_ model identity are ignored as legacy."""
    os.makedirs("artifacts", exist_ok=True)
    legacy_file = f"artifacts/export_{approved_project.project_id}_rev1_legacy.stl"
    with open(legacy_file, "wb") as f:
        f.write(b"legacy_stl_bytes")

    provider = ZooExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)

    res = await provider.export_format(
        project_id=approved_project.project_id,
        model_revision=1,
        format_name="stl",
        kcl_code=kcl_res.kcl_code,
        project=approved_project,
        zoo_model_id="zoo_sess_99999",
        kcl_hash=kcl_res.kcl_hash,
    )

    # Legacy file is not matched by the new cache key (which requires zoo_sess_99999)
    if res.success:
        assert legacy_file not in res.artifact_ref

    if os.path.exists(legacy_file):
        os.remove(legacy_file)


@pytest.mark.asyncio
async def test_mock_mode_remains_available_for_offline_tests(approved_project: Project):
    """Verify MockExportProvider provides offline mock export functionality."""
    reset_local_obj_call_count()
    provider = MockExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)

    res = await provider.export_format(
        project_id=approved_project.project_id,
        model_revision=1,
        format_name="stl",
        kcl_code=kcl_res.kcl_code,
        project=approved_project,
    )

    assert res.success
    assert res.is_mock is True
    assert get_local_obj_call_count() > 0
