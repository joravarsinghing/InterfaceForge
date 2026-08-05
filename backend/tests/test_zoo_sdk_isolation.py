from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.generation import GenerationJob, JobStatus
from app.services import engine_provider
from app.services.engine_provider import ZooEngineProvider
from app.services.export_provider import inspect_stl_bounded
from app.services import export_provider
from tests.test_zoo_native_kcl_export import create_valid_binary_stl_box


def fake_kcl(execute):
    return SimpleNamespace(
        FileExportFormat=SimpleNamespace(Stl="stl"),
        execute_code_and_export=execute,
    )


def make_job():
    return GenerationJob(job_id="job_direct", project_id="project_direct", model_revision=1)


@pytest.mark.asyncio
async def test_live_zoo_executes_directly_and_persists_executing_checkpoint(monkeypatch):
    checkpoints = []

    async def execute(_code, _format):
        assert checkpoints[-1] == ("zoo_sdk_execute_export_started", 60)
        return [SimpleNamespace(contents=create_valid_binary_stl_box())]

    monkeypatch.setitem(__import__("sys").modules, "kcl", fake_kcl(execute))
    monkeypatch.setattr(engine_provider.settings, "zoo_api_token", "token")
    monkeypatch.setattr(engine_provider.settings, "max_live_stl_bytes", 10 * 1024 * 1024)
    job = make_job()
    job.set_operation_callback(lambda op: checkpoints.append((op, job.progress_percent)))

    result = await ZooEngineProvider().execute_generation(job, "cube(20)")

    assert result.status == JobStatus.SUCCEEDED
    assert ("zoo_sdk_execute_export_started", 60) in checkpoints
    assert "zoo_sdk_execute_export_completed" in [item[0] for item in checkpoints]
    assert "zoo_response_received" in [item[0] for item in checkpoints]


@pytest.mark.asyncio
async def test_live_zoo_sdk_exception_fails_without_process_isolation(monkeypatch):
    async def execute(_code, _format):
        raise RuntimeError("native failure")

    monkeypatch.setitem(__import__("sys").modules, "kcl", fake_kcl(execute))
    monkeypatch.setattr(engine_provider.settings, "zoo_api_token", "token")
    result = await ZooEngineProvider().execute_generation(make_job(), "cube(20)")
    assert result.status == JobStatus.FAILED
    assert result.error_id == "IF-ENG-001"


@pytest.mark.asyncio
async def test_live_zoo_sdk_timeout_fails(monkeypatch):
    async def execute(_code, _format):
        await __import__("asyncio").sleep(0.05)

    monkeypatch.setitem(__import__("sys").modules, "kcl", fake_kcl(execute))
    monkeypatch.setattr(engine_provider.settings, "zoo_api_token", "token")
    monkeypatch.setattr(engine_provider.settings, "generation_timeout_seconds", 0.001)
    result = await ZooEngineProvider().execute_generation(make_job(), "cube(20)")
    assert result.status == JobStatus.FAILED
    assert result.error_id == "IF-ZOO-SDK-TIMEOUT"


def test_engine_provider_has_no_multiprocessing_worker():
    source = open(engine_provider.__file__, encoding="utf-8").read()
    assert "multiprocessing" not in source
    assert "_zoo_sdk_worker" not in source
    assert "_execute_zoo_sdk_isolated" not in source


def test_bounded_binary_stl_inspection_rejects_truncated_and_zero_facet():
    valid = create_valid_binary_stl_box()
    assert inspect_stl_bounded(valid[:-1])["is_valid"] is False
    zero = valid[:80] + (0).to_bytes(4, "little")
    assert inspect_stl_bounded(zero)["is_valid"] is False


def test_bounded_binary_stl_rejects_nonfinite_and_zero_volume():
    valid = bytearray(create_valid_binary_stl_box())
    import struct
    struct.pack_into("<f", valid, 84 + 12, float("nan"))
    assert inspect_stl_bounded(bytes(valid))["is_valid"] is False
    flat = bytearray(create_valid_binary_stl_box())
    for offset in range(84, len(flat), 50):
        for vertex in (12, 24, 36):
            struct.pack_into("<f", flat, offset + vertex + 8, 0.0)
    assert inspect_stl_bounded(bytes(flat))["is_valid"] is False


def test_bounded_binary_stl_respects_facet_limit(monkeypatch):
    monkeypatch.setattr(export_provider.settings, "max_live_stl_facets", 1)
    result = inspect_stl_bounded(create_valid_binary_stl_box())
    assert result["is_valid"] is False
    assert "facet count" in result["error"]


def test_bounded_binary_inspection_allocations_do_not_scale_with_vertex_storage():
    import tracemalloc
    import struct

    facets = 10_000
    payload = bytearray(b"bounded".ljust(80, b"\0")) + bytearray(struct.pack("<I", facets))
    triangle = struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0)
    payload.extend(triangle * facets)
    tracemalloc.start()
    result = inspect_stl_bounded(bytes(payload))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert result["facet_count"] == facets
    assert peak < 2 * 1024 * 1024


@pytest.mark.asyncio
async def test_oversized_live_payload_fails_gracefully(monkeypatch):
    async def execute(_code, _format):
        return [SimpleNamespace(contents=create_valid_binary_stl_box())]

    monkeypatch.setitem(__import__("sys").modules, "kcl", fake_kcl(execute))
    monkeypatch.setattr(engine_provider.settings, "zoo_api_token", "token")
    monkeypatch.setattr(engine_provider.settings, "max_live_stl_bytes", 1)
    result = await ZooEngineProvider().execute_generation(make_job(), "cube(20)")
    assert result.status == JobStatus.FAILED
    assert result.error_id == "IF-ZOO-STL-LIMIT"
