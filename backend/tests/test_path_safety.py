"""Regression tests for resolved-path artifact containment."""

from pathlib import PurePosixPath, PureWindowsPath

import pytest

from app.core.exceptions import InvalidProjectTokenError
from app.core.path_safety import resolve_path_within
from app.models.schema import (
    ExportReferences,
    ModelRevision,
    ModelRevisionStatus,
    WorkflowState,
)
from app.services.project_service import ProjectService


def test_resolve_path_within_accepts_valid_child_path(tmp_path):
    base = tmp_path / "artifacts"
    child = base / "exports" / "adapter.kcl"

    resolved = resolve_path_within(base, child)

    assert resolved == child.resolve(strict=False)


def test_resolve_path_within_rejects_traversal_attempt(tmp_path):
    base = tmp_path / "artifacts"
    target = base / ".." / "outside.kcl"

    with pytest.raises(ValueError):
        resolve_path_within(base, target)


def test_resolve_path_within_rejects_sibling_directory_sharing_prefix(tmp_path):
    base = tmp_path / "artifacts"
    sibling = tmp_path / "artifacts_evil" / "adapter.kcl"

    with pytest.raises(ValueError):
        resolve_path_within(base, sibling)


def test_resolve_path_within_handles_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    resolved = resolve_path_within("artifacts", "artifacts/uploads/image.png")

    assert resolved == (tmp_path / "artifacts" / "uploads" / "image.png").resolve(strict=False)


def test_resolve_path_within_supports_nonexistent_target_paths(tmp_path):
    base = tmp_path / "artifacts"
    target = base / "missing" / "future-export.kcl"

    resolved = resolve_path_within(base, target)

    assert resolved == target.resolve(strict=False)


def test_pure_windows_prefix_sibling_is_not_a_relative_child():
    base = PureWindowsPath(r"C:\repo\artifacts")
    sibling = PureWindowsPath(r"C:\repo\artifacts_evil\adapter.kcl")

    assert not sibling.is_relative_to(base)


def test_pure_posix_prefix_sibling_is_not_a_relative_child():
    base = PurePosixPath("/repo/artifacts")
    sibling = PurePosixPath("/repo/artifacts_evil/adapter.kcl")

    assert not sibling.is_relative_to(base)
