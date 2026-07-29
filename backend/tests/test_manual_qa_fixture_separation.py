"""Guard automated tests from mutable human-demo manual QA images."""

from pathlib import Path


def test_backend_tests_do_not_depend_on_manual_qa_images() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    tests_dir = repo_root / "backend" / "tests"
    offenders = []
    for path in tests_dir.glob("test_*.py"):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if "samples/manual_qa" in text or "manual_qa" in text:
            offenders.append(str(path.relative_to(repo_root)))

    assert offenders == []


def test_stable_s10_image_fixtures_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixtures = repo_root / "samples" / "test_fixtures"

    assert (fixtures / "s10_interface_a_original.jpg").is_file()
    assert (fixtures / "s10_interface_b_original.jpg").is_file()
