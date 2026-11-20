import pytest

from benchy.suite import RESERVED, SuiteError, check_task, load_suite, prepare_workspace


def test_core_suite_metadata(core):
    assert core.name == "benchy-core" and core.version == "1.0.0"
    assert len(core.tasks) == 8
    assert len(core.fingerprint()) == 64


def test_fingerprint_is_stable(core):
    assert core.fingerprint() == load_suite("benchy-core").fingerprint()


def test_select_by_prefix_and_errors(core):
    assert [t.id for t in core.select(["b02", "b01"])] == [
        "b02_clamp_upper_bound",
        "b01_chunk_drops_tail",
    ]
    with pytest.raises(SuiteError):
        core.select(["b0"])  # ambiguous
    with pytest.raises(SuiteError):
        core.select(["zzz"])


def test_unknown_suite_is_a_clear_error():
    with pytest.raises(SuiteError, match="no suite called"):
        load_suite("does-not-exist")


def test_workspace_hides_answers_and_is_identical(chunk_task, tmp_path):
    a = prepare_workspace(chunk_task, tmp_path / "a")
    b = prepare_workspace(chunk_task, tmp_path / "b")
    assert a == b  # same commit sha: same snapshot for both conditions
    names = {p.name for p in (tmp_path / "a").rglob("*")}
    assert not names & RESERVED


@pytest.mark.parametrize("task_id", [f"b0{i}" for i in range(1, 9)])
def test_every_core_task_is_valid(core, task_id):
    result = check_task(core.select([task_id])[0])
    assert result.valid, result.problems
