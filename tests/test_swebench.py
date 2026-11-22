"""SWE-bench support, tested offline against a tiny local repository shaped like an instance.

The fake repository `fakeorg/calc` has a bug in `calc/ops.py`; the instance's test patch adds a
test for it, and its reference patch fixes it. Environments are not built here (that needs uv and
PyPI): the task's interpreter is this test run's own Python, which has pytest.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchy.runner import baseline_swe
from benchy.runner.clients import make_model
from benchy.runner.experiment import ExperimentConfig, run_experiment
from benchy.suite import SuiteError, check_task, load_suite, prepare_workspace
from benchy.swebench import cache, evaluate, fetch, specs, validity
from benchy.swebench.instances import SweInstance, patch_files

BUGGY = '''def add(a, b):
    return a + b


def clamp(value, low, high):
    """Limit value to the range [low, high]."""
    if value < low:
        return low
    if value > high:
        return low
    return value
'''
FIXED = BUGGY.replace(
    "    if value > high:\n        return low", "    if value > high:\n        return high"
)
OLD_TESTS = """from calc.ops import add, clamp


def test_add():
    assert add(2, 3) == 5


def test_clamp_inside():
    assert clamp(5, 0, 10) == 5
"""
NEW_TESTS = (
    OLD_TESTS
    + """

def test_clamp_above():
    assert clamp(50, 0, 10) == 10
"""
)
README = "calc: small arithmetic helpers.\n"
UNRELATED = "def greet(name):\n    return 'hello ' + name\n"


def _git(cwd: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(cwd),
        "PATH": __import__("os").environ["PATH"],
    }
    return subprocess.run(
        ["git", "-c", "init.defaultBranch=main", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _diff(path: str, before: str, after: str) -> str:
    import difflib

    lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return f"diff --git a/{path} b/{path}\n" + "".join(lines)


@pytest.fixture()
def fake(tmp_path, monkeypatch):
    """A cached bare repo + one instance + a one-instance `kind = "swebench"` suite."""
    monkeypatch.setenv("BENCHY_CACHE", str(tmp_path / "cache"))
    src = tmp_path / "upstream"
    (src / "calc").mkdir(parents=True)
    (src / "tests").mkdir()
    (src / "calc" / "__init__.py").write_text("")
    (src / "calc" / "ops.py").write_text(BUGGY)
    (src / "calc" / "greet.py").write_text(UNRELATED)
    (src / "tests" / "test_ops.py").write_text(OLD_TESTS)
    (src / "README.md").write_text(README)
    _git(src, "init", "-q")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "base")
    base = _git(src, "rev-parse", "HEAD")
    bare = cache.repo_dir("fakeorg/calc")
    bare.parent.mkdir(parents=True)
    _git(tmp_path, "clone", "-q", "--bare", str(src), str(bare))

    rec = {
        "instance_id": "fakeorg__calc-1",
        "repo": "fakeorg/calc",
        "version": "1.0",
        "base_commit": base,
        "environment_setup_commit": base,
        "problem_statement": "clamp() returns the low bound when the value is above the high bound",
        "patch": _diff("calc/ops.py", BUGGY, FIXED),
        "test_patch": _diff("tests/test_ops.py", OLD_TESTS, NEW_TESTS),
        "FAIL_TO_PASS": json.dumps(["tests/test_ops.py::test_clamp_above"]),
        "PASS_TO_PASS": json.dumps(["tests/test_ops.py::test_add", "test_clamp_inside"]),
        "difficulty": "<15 min fix",
    }
    spec = specs.EnvSpec(python="3.12", pip=("pytest",))
    monkeypatch.setattr("benchy.swebench.instances.spec_for", lambda repo, version: spec)
    monkeypatch.setattr(cache, "env_ready", lambda *a: True)
    monkeypatch.setattr(cache, "env_python", lambda path: Path(sys.executable))
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "suite.toml").write_text(
        '[suite]\nname = "fake-swe"\nversion = "0.1"\nkind = "swebench"\ntime_limit_s = 300\n'
    )
    (suite_dir / "instances.jsonl").write_text(json.dumps(rec) + "\n")
    suite = load_suite(suite_dir)
    return suite, suite.tasks[0], SweInstance.from_record(rec)


# --------------------------------------------------------------------------- specs and data


def test_specs_for_supported_repos():
    assert specs.spec_for("sympy/sympy", "1.1").python == "3.9"
    sphinx = specs.spec_for("sphinx-doc/sphinx", "3.5")
    assert sphinx.install == ".[test]" and any(e.path == "setup.py" for e in sphinx.edits)
    assert "docutils<0.22" in sphinx.pip
    assert specs.spec_for("pylint-dev/pylint", "3.0").pip[0] == "astroid==3.0.0a6"
    assert specs.spec_for("pylint-dev/pylint", "2.15").requirements == ("requirements_test.txt",)
    xarray = specs.spec_for("pydata/xarray", "2022.06")
    assert xarray.python == "3.10" and "pint" in xarray.optional
    assert "setuptools==68.0.0" in xarray.pip and "setuptools<70" not in xarray.pip
    # Environments without a setuptools pin get one that still ships pkg_resources.
    assert "setuptools<70" in specs.spec_for("sympy/sympy", "1.1").pip


@pytest.mark.parametrize(
    "repo,version",
    [("sphinx-doc/sphinx", "7.2"), ("pylint-dev/pylint", "2.8"), ("django/django", "4.0")],
)
def test_unsupported_repo_versions_say_why(repo, version):
    with pytest.raises(specs.Unsupported):
        specs.spec_for(repo, version)


def test_setup_edits_replace_the_first_match_per_line(tmp_path):
    (tmp_path / "setup.py").write_text("x = ['Jinja2>=2.3', 'Jinja2>=2.3']\ny = 'Jinja2>=2.3'\n")
    cache.apply_edits(tmp_path, (specs.SetupEdit("setup.py", "Jinja2>=2.3", "Jinja2<3.0"),))
    assert (tmp_path / "setup.py").read_text() == (
        "x = ['Jinja2<3.0', 'Jinja2>=2.3']\ny = 'Jinja2<3.0'\n"
    )


def test_instance_round_trip_and_patch_files(fake):
    _, _, inst = fake
    again = SweInstance.from_record(json.loads(json.dumps(inst.to_record())))
    assert again == inst
    assert patch_files(inst.patch) == ["calc/ops.py"]
    assert evaluate.test_files(inst) == ["tests/test_ops.py"]


def test_outcome_lookup_handles_swebench_id_styles():
    outcomes = {
        "tests/a.py::test_x": "passed",
        "sympy/core/tests/test_b.py::test_issue_1": "failed",
        "tests/c.py::test_p[float64-single index]": "passed",
        "tests/c.py::test_p[float64-multiple indices]": "passed",
        "tests/d.py::test_q[1]": "xfailed",
    }
    assert evaluate.outcome_of("tests/a.py::test_x", outcomes) == "passed"
    assert evaluate.outcome_of("test_issue_1", outcomes) == "failed"  # sympy: bare names
    assert (
        evaluate.outcome_of("tests/c.py::test_p[float64-single", outcomes) == "passed"
    )  # cut at space
    assert evaluate.outcome_of("test_q", outcomes) == "passed"  # xfail counts as a pass
    assert evaluate.outcome_of("tests/a.py::test_gone", outcomes) == "missing"


# --------------------------------------------------------------------------- the judge


def test_the_reference_fix_makes_the_instance_valid(fake):
    _, task, inst = fake
    result = evaluate.check_instance(inst, Path(sys.executable))
    assert result.valid, result.problems
    assert check_task(task).valid


def test_an_instance_whose_fix_does_not_work_is_invalid(fake, monkeypatch):
    _, _, inst = fake
    broken = SweInstance(
        **{**inst.__dict__, "patch": _diff("calc/greet.py", UNRELATED, UNRELATED + "\n")}
    )
    result = evaluate.check_instance(broken, Path(sys.executable))
    assert not result.valid
    assert any("still fail" in p for p in result.problems)


def test_workspaces_are_identical_for_both_conditions(fake, tmp_path):
    _, task, _ = fake
    first = prepare_workspace(task, tmp_path / "a")
    second = prepare_workspace(task, tmp_path / "b")
    assert first == second
    assert ".qed/" in (tmp_path / "a" / ".gitignore").read_text()
    assert (tmp_path / "a" / "calc" / "ops.py").read_text() == BUGGY


def test_the_judge_resolves_a_real_fix(fake, tmp_path):
    _, task, inst = fake
    ws = tmp_path / "ws"
    prepare_workspace(task, ws)
    (ws / "calc" / "ops.py").write_text(FIXED)
    ev = evaluate.SweEvaluator(inst, Path(sys.executable)).evaluate(ws, log_dir=tmp_path / "log")
    assert ev.resolved and not ev.regression
    assert (ev.hidden_passed, ev.hidden_total, ev.visible_passed, ev.visible_total) == (1, 1, 2, 2)
    assert ev.changed_files == ["calc/ops.py"]
    assert (tmp_path / "log" / "eval_outcomes.json").is_file()


def test_test_edits_are_discarded_and_cannot_fake_a_pass(fake, tmp_path):
    _, task, inst = fake
    ws = tmp_path / "ws"
    prepare_workspace(task, ws)
    (ws / "tests" / "test_ops.py").write_text("def test_clamp_above():\n    pass\n")
    (ws / "tests" / "conftest.py").write_text("")
    ev = evaluate.SweEvaluator(inst, Path(sys.executable)).evaluate(ws)
    assert not ev.resolved
    assert ev.discarded_files == ["tests/conftest.py", "tests/test_ops.py"]
    assert ev.changed_files == []


def test_breaking_a_passing_test_is_a_regression(fake, tmp_path):
    _, task, inst = fake
    ws = tmp_path / "ws"
    prepare_workspace(task, ws)
    (ws / "calc" / "ops.py").write_text(FIXED.replace("return a + b", "return a - b"))
    ev = evaluate.SweEvaluator(inst, Path(sys.executable)).evaluate(ws)
    assert ev.regression and not ev.resolved
    assert ev.regressed_tests == ["tests/test_ops.py::test_add"]


def test_a_change_that_breaks_imports_reports_why(fake, tmp_path):
    _, task, inst = fake
    ws = tmp_path / "ws"
    prepare_workspace(task, ws)
    (ws / "calc" / "ops.py").write_text("def add(:\n")
    ev = evaluate.SweEvaluator(inst, Path(sys.executable)).evaluate(ws)
    assert not ev.resolved and ev.hidden_passed == 0


# --------------------------------------------------------------------------- the baseline


def test_bm25_ranks_the_file_the_issue_talks_about_first(fake, tmp_path):
    _, task, inst = fake
    ws = tmp_path / "ws"
    prepare_workspace(task, ws)
    assert baseline_swe.source_files(ws) == [
        Path("calc/__init__.py"),
        Path("calc/greet.py"),
        Path("calc/ops.py"),
    ]
    ctx = baseline_swe.build_context(ws, inst.problem_statement)
    assert ctx.files[0] == "calc/ops.py"
    assert "[start of calc/ops.py]" in ctx.text and "1 def add(a, b):" in ctx.text
    oracle = baseline_swe.build_context(ws, inst.problem_statement, "oracle", inst.patch)
    assert oracle.files == ["calc/ops.py"]


def test_tokens_split_identifiers():
    assert {"getlocal_var", "get", "local", "var"} <= set(baseline_swe.tokens("getLocal_var"))


@pytest.mark.parametrize(
    "reply",
    [
        "<patch>\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n</patch>",
        "Here:\n```diff\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n```",
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n",
    ],
)
def test_extract_patch_formats(reply):
    assert baseline_swe.extract_patch(reply).startswith(("--- a/x.py", "diff --git"))


def test_extract_patch_without_a_diff():
    assert baseline_swe.extract_patch("I think the bug is in clamp.") == ""


class _Reply:
    def __init__(self, text):
        self.text = text

    def chat(self, messages, **kw):
        self.prompt = messages[0]["content"]
        return self.text


def test_baseline_applies_the_models_patch(fake, tmp_path):
    _, task, inst = fake
    ws = tmp_path / "ws"
    prepare_workspace(task, ws)
    client = _Reply(f"<patch>\n{inst.patch}</patch>")
    out, shown = baseline_swe.run_baseline_swe(client, inst.problem_statement, ws)
    assert out.status == "done" and out.files_written == ["calc/ops.py"]
    assert (ws / "calc" / "ops.py").read_text() == FIXED
    assert shown[0] == "calc/ops.py" and "<issue>" in client.prompt


def test_baseline_records_a_patch_that_does_not_apply(fake, tmp_path):
    _, task, inst = fake
    ws = tmp_path / "ws"
    prepare_workspace(task, ws)
    bad = "--- a/calc/ops.py\n+++ b/calc/ops.py\n@@ -1,1 +1,1 @@\n-nothing like this\n+x\n"
    out, _ = baseline_swe.run_baseline_swe(_Reply(f"<patch>\n{bad}</patch>"), "x", ws)
    assert out.status == "unparsable" and "does not apply" in out.message


def test_baseline_refuses_paths_outside_the_repo(fake, tmp_path):
    _, task, _ = fake
    ws = tmp_path / "ws"
    prepare_workspace(task, ws)
    evil = "--- a/../evil.py\n+++ b/../evil.py\n@@ -0,0 +1 @@\n+x\n"
    out, _ = baseline_swe.run_baseline_swe(_Reply(f"<patch>\n{evil}</patch>"), "x", ws)
    assert out.status == "no_change" and out.rejected_paths == ["../evil.py"]


# --------------------------------------------------------------------------- end to end


def _experiment(suite, model, tmp_path):
    client, spec = make_model(model)
    cfg = ExperimentConfig(
        suite=suite, tasks=suite.tasks, model=spec, time_limit_s=300, speed="fast"
    )
    return run_experiment(cfg, client, tmp_path / "reports")


def test_oracle_resolves_in_both_conditions_with_the_swebench_judge(fake, tmp_path):
    suite, _, _ = fake
    state, run_dir = _experiment(suite, "scripted:oracle", tmp_path)
    assert state.complete and len(state.attempts) == 2
    assert all(a["resolved"] for a in state.attempts), [a["message"] for a in state.attempts]
    base = next(a for a in state.attempts if a["condition"] == "baseline")
    assert base["baseline_context_files"][0] == "calc/ops.py"
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["evaluator"]["name"] == "benchy-swebench"
    assert meta["suite"]["kind"] == "swebench"
    assert meta["controls"]["baseline_context"] == "bm25-13k-tokens"


def test_broken_model_resolves_nothing_on_swebench_tasks(fake, tmp_path):
    suite, _, _ = fake
    state, _ = _experiment(suite, "scripted:broken", tmp_path)
    assert not any(a["resolved"] for a in state.attempts)


def test_unfetched_tasks_give_a_clear_error(fake, monkeypatch):
    _, task, _ = fake
    monkeypatch.setattr(cache, "env_ready", lambda *a: False)
    with pytest.raises(SuiteError, match="benchy suites fetch"):
        task.python()


def test_fingerprint_changes_with_the_data(fake, tmp_path):
    suite, _, _ = fake
    first = suite.fingerprint()
    rec = suite.tasks[0].swe.to_record()
    rec["problem_statement"] += " (edited)"
    (suite.path / "instances.jsonl").write_text(json.dumps(rec) + "\n")
    assert load_suite(suite.path).fingerprint() != first


def test_validity_is_saved_per_suite_fingerprint(fake):
    suite, _, _ = fake
    assert validity.load_validity(suite) is None
    validity.save_validity(suite, {"fakeorg__calc-1": True})
    assert validity.load_validity(suite) == {"fakeorg__calc-1": True}


def test_fetch_asks_first_and_refuses_without_a_terminal(fake, monkeypatch, capsys):
    suite, _, _ = fake
    monkeypatch.setattr(cache, "env_ready", lambda *a: False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert fetch.fetch(suite.tasks, assume_yes=False, say=print) == 2
    out = capsys.readouterr().out
    assert "--yes" in out and "Python environment" in out


def test_fetch_has_nothing_to_do_when_everything_is_cached(fake, capsys):
    suite, _, _ = fake
    assert fetch.fetch(suite.tasks, assume_yes=False, say=print) == 0
    assert "already" in capsys.readouterr().out


def test_cli_check_records_validity(fake, capsys):
    from benchy.cli import main

    suite, _, _ = fake
    assert main(["suites", "check", str(suite.path)]) == 0
    assert "1 of 1 tasks valid" in capsys.readouterr().out
    assert validity.load_validity(suite) == {"fakeorg__calc-1": True}


def test_the_shipped_suite_loads():
    suite = load_suite("swebench-verified-py")
    assert suite.kind == "swebench" and suite.time_limit_s == 1800
    assert len({t.id for t in suite.tasks}) == len(suite.tasks) > 0
    for task in suite.tasks:
        assert task.swe is not None and task.swe.repo in specs.SUPPORTED_REPOS
        task.swe.spec  # noqa: B018 - every shipped instance has a supported environment


def test_swebench_reports_state_their_own_limitations(fake, tmp_path):
    suite, _, _ = fake
    _, run_dir = _experiment(suite, "scripted:oracle", tmp_path)
    md = (run_dir / "report.md").read_text()
    assert "not comparable with the official SWE-bench leaderboard" in md
    assert "single-file" not in md and "FAIL_TO_PASS" in md


def test_run_skips_only_tasks_found_invalid(fake, tmp_path, capsys):
    from benchy.cli import main

    suite, _, _ = fake
    validity.save_validity(suite, {"some-other-task": True})  # this task: never checked
    out = tmp_path / "out"
    assert (
        main(
            [
                "run",
                "--model",
                "scripted:oracle",
                "--suite",
                str(suite.path),
                "--speed",
                "fast",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "have not been checked" in captured.out + captured.err
    validity.save_validity(suite, {"fakeorg__calc-1": False})
    assert (
        main(["run", "--model", "scripted:oracle", "--suite", str(suite.path), "--out", str(out)])
        == 2
    )
