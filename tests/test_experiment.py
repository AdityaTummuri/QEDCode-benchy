import json

from benchy.cli import main
from benchy.runner.clients import make_model
from benchy.runner.experiment import ExperimentConfig, condition_order, run_experiment


def _run(core, model, tmp_path, ids=("b01", "b04"), reps=1):
    client, spec = make_model(model)
    cfg = ExperimentConfig(
        suite=core, tasks=core.select(list(ids)), model=spec, reps=reps, time_limit_s=120
    )
    return run_experiment(cfg, client, tmp_path)


def test_oracle_resolves_everything_in_both_conditions(core, tmp_path):
    state, run_dir = _run(core, "scripted:oracle", tmp_path)
    assert state.complete and len(state.attempts) == 4
    assert all(a["resolved"] and not a["regression"] for a in state.attempts)
    q = [a for a in state.attempts if a["condition"] == "qedcode"]
    assert all(a["qed_applied"] and a["qed_grade"] for a in q)
    # Both conditions started from the identical snapshot.
    for tid in ("b01_chunk_drops_tail", "b04_duration_minutes"):
        assert len({a["snapshot_commit"] for a in state.attempts if a["task_id"] == tid}) == 1
    for name in ("report.md", "results.json", "results.csv", "metadata.json", "logs"):
        assert (run_dir / name).exists()


def test_broken_model_resolves_nothing_and_report_is_labelled(core, tmp_path):
    state, run_dir = _run(core, "scripted:broken", tmp_path, ids=("b02",))
    assert not any(a["resolved"] for a in state.attempts)
    md = (run_dir / "report.md").read_text()
    assert "NOT A REAL MEASUREMENT" in md
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["is_real_measurement"] is False


def test_metadata_has_no_local_identity(core, tmp_path):
    import getpass
    import socket
    from pathlib import Path

    _state, run_dir = _run(core, "scripted:oracle", tmp_path, ids=("b03",))
    text = (run_dir / "results.json").read_text() + (run_dir / "metadata.json").read_text()
    assert str(Path.home()) not in text and str(tmp_path) not in text
    assert socket.gethostname() not in text
    assert f'"{getpass.getuser()}"' not in text


def test_condition_order_is_seeded_and_balanced(core):
    client, spec = make_model("scripted:oracle")
    cfg = ExperimentConfig(suite=core, tasks=core.tasks, model=spec, reps=4, seed=7)
    orders = [tuple(condition_order(cfg, t, r)) for t in core.tasks for r in range(1, 5)]
    assert orders == [tuple(condition_order(cfg, t, r)) for t in core.tasks for r in range(1, 5)]
    assert len(set(orders)) == 2  # both orders occur


def test_cli_run_and_report(tmp_path, capsys):
    out = str(tmp_path)
    assert main(["run", "--model", "scripted:oracle", "--tasks", "b05", "--out", out]) == 0
    assert main(["report", "--list", "--out", out]) == 0
    assert "[self-test]" in capsys.readouterr().out
    assert main(["report", "--out", out]) == 0
    assert "Benchy report" in capsys.readouterr().out
    assert main(["run", "--model", "nonsense", "--out", out]) == 2
    assert main(["run", "--model", "scripted:oracle", "--conditions", "x", "--out", out]) == 2
