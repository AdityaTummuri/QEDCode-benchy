from pathlib import Path

from benchy.evaluators.pytest_eval import Evaluator, is_protected
from benchy.runner.scripted import fixed_files
from benchy.suite import prepare_workspace


def _workspace(task, tmp_path):
    ws = tmp_path / "w"
    prepare_workspace(task, ws)
    return ws


def test_protected_paths():
    for p in [
        "tests/test_x.py",
        "tests/helpers.py",
        "conftest.py",
        "src/pkg/conftest.py",
        "pyproject.toml",
        "test_top.py",
        "pkg/foo_test.py",
        "hidden/test_hidden.py",
    ]:
        assert is_protected(Path(p)), p
    assert not is_protected(Path("src/pkg/mod.py"))


def test_untouched_code_is_not_resolved(chunk_task, tmp_path):
    ev = Evaluator(chunk_task).evaluate(_workspace(chunk_task, tmp_path))
    assert not ev.resolved and not ev.regression and ev.hidden_passed < ev.hidden_total


def test_reference_fix_is_resolved(chunk_task, tmp_path):
    ws = _workspace(chunk_task, tmp_path)
    for path, (_before, after) in fixed_files(chunk_task).items():
        (ws / path).write_text(after)
    ev = Evaluator(chunk_task).evaluate(ws)
    assert ev.resolved and ev.hidden_passed == ev.hidden_total == 3
    assert ev.changed_files == ["src/listkit/chunks.py"]


def test_regression_is_detected_and_blocks_resolution(chunk_task, tmp_path):
    ws = _workspace(chunk_task, tmp_path)
    # Keeps the tail (hidden tests pass) but stops validating size (a visible test breaks).
    (ws / "src/listkit/chunks.py").write_text(
        "def chunk(items, size):\n    items = list(items)\n"
        "    return [items[i : i + size] for i in range(0, len(items), max(size, 1))]\n"
    )
    ev = Evaluator(chunk_task).evaluate(ws)
    assert ev.hidden_passed == ev.hidden_total
    assert ev.regression and not ev.resolved
    assert any("size_must_be_positive" in t for t in ev.regressed_tests)


def test_test_tampering_is_discarded(chunk_task, tmp_path):
    ws = _workspace(chunk_task, tmp_path)
    (ws / "conftest.py").write_text(
        "import pytest\n\n@pytest.fixture(autouse=True)\ndef x():\n    pass\n"
    )
    (ws / "tests/test_chunks.py").write_text("def test_nothing():\n    assert True\n")
    ev = Evaluator(chunk_task).evaluate(ws)
    assert set(ev.discarded_files) == {"conftest.py", "tests/test_chunks.py"}
    assert ev.changed_files == [] and not ev.resolved


def test_syntax_error_is_unresolved_not_a_crash(chunk_task, tmp_path):
    ws = _workspace(chunk_task, tmp_path)
    (ws / "src/listkit/chunks.py").write_text("def chunk(:\n")
    ev = Evaluator(chunk_task).evaluate(ws)
    assert not ev.resolved and ev.regression and ev.hidden_passed == 0 and ev.hidden_total == 3
