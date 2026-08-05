import asyncio
import os
import signal
import sys
import types
from unittest.mock import patch

import pytest

from app.models.generation import GenerationJob, JobStatus
from app.services.engine_provider import (
    _execute_zoo_sdk_isolated,
    _signal_name,
    _zoo_sdk_worker,
)
from app.services.generation_job_service import GenerationJobService


class _Connection:
    def __init__(self, value=None):
        self.value = value
        self.closed = False

    def send(self, value):
        self.value = value

    def poll(self, *_args):
        return self.value is not None

    def recv(self):
        value = self.value
        self.value = None
        return value

    def close(self):
        self.closed = True


class _Process:
    def __init__(self, response=None, exitcode=0, alive=False):
        self.response = response
        self.exitcode = exitcode
        self._alive = alive
        self.terminated = False
        self.joined = False

    def start(self):
        self._alive = self._alive

    def daemon(self, *_args):
        return None

    def is_alive(self):
        return self._alive

    def join(self, *_args):
        self.joined = True

    def terminate(self):
        self.terminated = True
        self._alive = False

    def kill(self):
        self.terminated = True
        self._alive = False


class _Context:
    def __init__(self, process):
        self.process = process

    def Pipe(self, duplex=False):
        assert duplex is False
        parent = _Connection(self.process.response)
        child = _Connection()
        return parent, child

    def Process(self, **kwargs):
        return self.process


@pytest.mark.asyncio
async def test_isolated_success_reads_child_response_before_join():
    process = _Process(response={"kind": "success", "stl_bytes": b"solid stl"})
    with patch("app.services.engine_provider.multiprocessing.get_context", return_value=_Context(process)):
        outcome, response = await _execute_zoo_sdk_isolated("cube(20)", 1.0)

    assert outcome == "response"
    assert response["stl_bytes"] == b"solid stl"
    assert process.joined is True
    assert process.terminated is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exitcode", "expected_signal"),
    [(1, None), (-signal.SIGSEGV, "SIGSEGV")],
)
async def test_isolated_abnormal_exit_is_classified(exitcode, expected_signal):
    process = _Process(exitcode=exitcode)
    with patch("app.services.engine_provider.multiprocessing.get_context", return_value=_Context(process)):
        outcome, details = await _execute_zoo_sdk_isolated("cube(20)", 1.0)

    assert outcome == "abnormal_exit"
    assert details["exit_code"] == exitcode
    assert details["signal"] == expected_signal


@pytest.mark.asyncio
async def test_isolated_timeout_terminates_and_joins_child():
    process = _Process(alive=True)
    with patch("app.services.engine_provider.multiprocessing.get_context", return_value=_Context(process)):
        outcome, details = await _execute_zoo_sdk_isolated("cube(20)", 0.01)

    assert outcome == "timeout"
    assert details["error_id"] == "IF-ZOO-WORKER-TIMEOUT"
    assert process.terminated is True


def test_zoo_worker_returns_stl_bytes_without_logging_source_or_token(monkeypatch):
    class ExportFormat:
        Stl = "stl"

    async def execute(_source, _format):
        return [types.SimpleNamespace(contents=[1, 2, 3])]

    fake_kcl = types.SimpleNamespace(
        FileExportFormat=ExportFormat,
        execute_code_and_export=execute,
    )
    monkeypatch.setitem(sys.modules, "kcl", fake_kcl)
    monkeypatch.setenv("ZOO_API_TOKEN", "secret-token")
    response = _Connection()

    _zoo_sdk_worker("secret-source", "Stl", response)

    assert response.value == {"kind": "success", "stl_bytes": b"\x01\x02\x03"}
    assert "secret-token" not in repr(response.value)
    assert "secret-source" not in repr(response.value)


def test_signal_name():
    assert _signal_name(-signal.SIGSEGV) == "SIGSEGV"
    assert _signal_name(1) is None
