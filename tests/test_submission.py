"""Sharing: sanitizer, validator (incl. malicious input), PR checks and aggregation."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from benchy.cli import main
from benchy.runner.clients import make_model
from benchy.runner.experiment import ExperimentConfig, run_experiment
from benchy.submission import SubmissionError, submission_id
from benchy.submission.sanitize import build_submission
from benchy.submission.validate import known_suites, validate_bytes, validate_record
from benchy.suite import builtin_suites_dir

ROOT = Path(__file__).resolve().parent.parent


def _load_bot(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "bot" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def results(tmp_path_factory) -> dict:
    """A complete run (scripted, then relabelled as if a real model produced it)."""
    from benchy.suite import load_suite

    os.environ.setdefault("QEDCODE_HOME", str(tmp_path_factory.mktemp("qh")))
    core = load_suite("benchy-core")
    client, spec = make_model("scripted:oracle")
    cfg = ExperimentConfig(suite=core, tasks=core.select(["b01", "b02"]), model=spec, reps=2)
    _state, run_dir = run_experiment(cfg, client, tmp_path_factory.mktemp("runs"))
    data = json.loads((run_dir / "results.json").read_text())
    data["metadata"]["is_real_measurement"] = True
    data["metadata"]["model"] = {"backend": "ollama", "name": "qwen3:4b"}
    return data


@pytest.fixture(scope="module")
def suites() -> dict:
    return known_suites(builtin_suites_dir())


@pytest.fixture()
def record(results) -> dict:
    return build_submission(copy.deepcopy(results))


def _rehash(rec: dict) -> dict:
    rec["submission_id"] = submission_id(rec)
    return rec


# --------------------------------------------------------------------------- sanitizer


def test_record_is_valid_and_minimal(record, suites):
    assert validate_record(record, suites) == []
    assert set(record) == {
        "schema_version", "submission_id", "benchy_version", "qedcode_version", "run_date",
        "suite", "model", "controls", "environment", "attempts",
    }  # fmt: skip
    assert len(record["attempts"]) == 8
    text = json.dumps(record)
    for leaked in ("transcript", "message", "changed_files", "run_id", "snapshot_commit", "r-20"):
        assert leaked not in text
    assert len(record["run_date"]) == 10  # a day, not a timestamp


def test_record_is_deterministic(results):
    assert build_submission(copy.deepcopy(results)) == build_submission(copy.deepcopy(results))


def test_self_tests_incomplete_and_single_condition_runs_are_refused(results):
    for change, words in (
        (lambda m: m.update(is_real_measurement=False), "self-test"),
        (lambda m: m.update(complete=False), "did not finish"),
        (lambda m: m["controls"].update(conditions=["qedcode"]), "both conditions"),
    ):
        data = copy.deepcopy(results)
        change(data["metadata"])
        with pytest.raises(SubmissionError, match=words):
            build_submission(data)


def test_local_model_paths_are_reduced_to_a_name(results):
    data = copy.deepcopy(results)
    data["metadata"]["model"] = {"backend": "llamacpp", "name": "/Users/me/models/Qwen-4B.Q4.gguf"}
    assert build_submission(data)["model"]["name"] == "Qwen-4B.Q4"
    data["metadata"]["model"] = {"backend": "llamacpp", "name": "llamacpp:qwen3.5-4b-q4km"}
    assert build_submission(data)["model"]["name"] == "qwen3.5-4b-q4km"


def test_a_secret_anywhere_refuses_the_whole_submission(results):
    data = copy.deepcopy(results)
    data["metadata"]["model"]["name"] = "sk-abcdefghijklmnopqrstuvwx"
    with pytest.raises(SubmissionError, match="Refusing to share"):
        build_submission(data)


# --------------------------------------------------------------------------- validator


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda r: r.update(extra="x"), "unexpected field"),
        (lambda r: r["attempts"][0].update(transcript="code"), "unexpected field"),
        (lambda r: r["attempts"][0].update(hidden_passed=99), "more hidden tests"),
        (lambda r: r["attempts"][0].update(resolved=True, hidden_passed=0), "resolved needs"),
        (lambda r: r["attempts"][0].update(seconds=99999), "far above"),
        (lambda r: r["attempts"].append(dict(r["attempts"][0])), "duplicate attempt"),
        (lambda r: r["attempts"].pop(), "incomplete run"),
        (lambda r: r["suite"].update(fingerprint_sha256="0" * 64), "fingerprint"),
        (lambda r: r["suite"].update(version="9.9.9"), "unknown suite"),
        (lambda r: r["attempts"][0].update(task_id="zz_unknown"), "not in the suite"),
        (lambda r: r["model"].update(name="../../etc"), "unexpected format"),
        (lambda r: r["model"].update(name="a//b"), "looks like a path"),
        (lambda r: r["environment"].update(os="my-laptop"), "is not one of"),
        (lambda r: r["model"].update(name="user@example.com"), "secret"),
        (lambda r: r["attempts"][0].update(rep=True), "expected integer"),
    ],
)
def test_bad_records_are_rejected(record, suites, mutate, expected):
    bad = copy.deepcopy(record)
    mutate(bad)
    _rehash(bad)
    problems = validate_record(bad, suites)
    assert any(expected in p for p in problems), problems


def test_baseline_cannot_carry_a_grade(record, suites):
    bad = copy.deepcopy(record)
    next(a for a in bad["attempts"] if a["condition"] == "baseline")["qed_grade"] = "A"
    assert any("baseline attempt" in p for p in validate_record(_rehash(bad), suites))


def test_tampering_breaks_the_id(record, suites):
    bad = copy.deepcopy(record)
    bad["attempts"][0]["seconds"] += 1
    assert any("submission_id" in p for p in validate_record(bad, suites))


@pytest.mark.parametrize(
    "data, expected",
    [
        (b"\xff\xfe", "UTF-8"),
        (b"{not json", "not valid JSON"),
        (b"[]", "expected object"),
        (b" " * (600 * 1024), "larger than"),
    ],
)
def test_malformed_files(data, expected):
    _record, problems = validate_bytes(data)
    assert any(expected in p for p in problems), problems


# --------------------------------------------------------------------------- PR validation


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}  # fmt: skip
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture()
def pr_repo(tmp_path):
    trusted = tmp_path / "trusted"
    shutil.copytree(builtin_suites_dir(), trusted / "suites")
    (trusted / "results" / "submissions").mkdir(parents=True)
    pr = tmp_path / "pr"
    (pr / "results" / "submissions").mkdir(parents=True)
    (pr / "README.md").write_text("hi\n")
    _git(pr, "init", "-q", "-b", "main")
    _git(pr, "add", "-A")
    _git(pr, "commit", "-qm", "base")
    return trusted, pr, _git(pr, "rev-parse", "HEAD")


def _add(pr: Path, rel: str, text: str, mode: str | None = None) -> None:
    path = pr / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode:
        path.chmod(0o755)
    _git(pr, "add", "-A")
    _git(pr, "commit", "-qm", "change")


def test_pr_with_a_valid_submission_passes(pr_repo, record):
    bot = _load_bot("validate_pr")
    trusted, pr, base = pr_repo
    _add(pr, f"results/submissions/{record['submission_id']}.json", json.dumps(record))
    ok, lines = bot.validate_pr(pr, base, trusted)
    assert ok, lines


def test_pr_touching_anything_else_fails(pr_repo, record):
    bot = _load_bot("validate_pr")
    trusted, pr, base = pr_repo
    _add(pr, f"results/submissions/{record['submission_id']}.json", json.dumps(record))
    _add(pr, ".github/workflows/x.yml", "on: push\n")
    ok, lines = bot.validate_pr(pr, base, trusted)
    assert not ok and any("x.yml" in line for line in lines)


def test_pr_modifying_readme_fails(pr_repo):
    bot = _load_bot("validate_pr")
    trusted, pr, base = pr_repo
    _add(pr, "README.md", "changed\n")
    ok, _lines = bot.validate_pr(pr, base, trusted)
    assert not ok


def test_pr_executable_symlink_wrong_name_and_duplicate_fail(pr_repo, record):
    bot = _load_bot("validate_pr")
    trusted, pr, base = pr_repo
    sid = record["submission_id"]
    _add(pr, f"results/submissions/{sid}.json", json.dumps(record), mode="x")
    ok, lines = bot.validate_pr(pr, base, trusted)
    assert not ok and any("non-executable" in line for line in lines)

    _git(pr, "reset", "-q", "--hard", base)
    link = pr / "results" / "submissions" / f"{sid}.json"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to("/etc/passwd")
    _git(pr, "add", "-A")
    _git(pr, "commit", "-qm", "link")
    ok, lines = bot.validate_pr(pr, base, trusted)
    assert not ok and any("regular" in line for line in lines)

    _git(pr, "reset", "-q", "--hard", base)
    _add(pr, f"results/submissions/{'a' * 64}.json", json.dumps(record))
    ok, lines = bot.validate_pr(pr, base, trusted)
    assert not ok and any("file name" in line for line in lines)

    _git(pr, "reset", "-q", "--hard", base)
    (trusted / "results" / "submissions" / f"{sid}.json").write_text("{}")
    _add(pr, f"results/submissions/{sid}.json", json.dumps(record))
    ok, lines = bot.validate_pr(pr, base, trusted)
    assert not ok and any("duplicate" in line for line in lines)


# --------------------------------------------------------------------------- aggregation


def test_aggregate_builds_leaderboard_and_readme(tmp_path, record, results):
    bot = _load_bot("aggregate")
    root = tmp_path / "repo"
    shutil.copytree(builtin_suites_dir(), root / "suites")
    subs = root / "results" / "submissions"
    subs.mkdir(parents=True)
    (root / "README.md").write_text(f"# x\n\n{bot.START}\nold\n{bot.END}\n")
    second = copy.deepcopy(results)
    second["metadata"]["controls"]["order_seed"] = 5
    other = build_submission(second)
    for rec in (record, other):
        (subs / f"{rec['submission_id']}.json").write_text(json.dumps(rec))
    (subs / f"{'b' * 64}.json").write_text('{"bad": true}')  # invalid: skipped, never counted
    (root / "results" / "reproduced.json").write_text(
        json.dumps({"submission_ids": [record["submission_id"]]})
    )
    assert bot.main(["--root", str(root), "--check"]) == 1
    assert bot.main(["--root", str(root)]) == 0
    assert bot.main(["--root", str(root), "--check"]) == 0
    board = json.loads((root / "leaderboard" / "leaderboard.json").read_text())
    assert board["accepted_submissions"] == 2 and board["reproduced_submissions"] == 1
    assert board["skipped_invalid"] == [f"{'b' * 64}.json"]
    (group,) = board["groups"]
    assert group["model"] == "qwen3:4b" and group["submissions"] == 2
    assert group["label"].startswith("community-reported")  # only 1 of 2 reproduced
    assert group["paired"]["pairs"] == 8 and group["qedcode"]["attempts"] == 8
    readme = (root / "README.md").read_text()
    assert "old" not in readme and "qwen3:4b" in readme


def test_repository_aggregates_are_current():
    assert _load_bot("aggregate").main(["--check"]) == 0


# --------------------------------------------------------------------------- CLI


def test_share_refuses_self_tests_and_exports_real_runs(tmp_path, results, capsys):
    out = tmp_path / "reports"
    assert main(["run", "--model", "scripted:oracle", "--tasks", "b03", "--out", str(out)]) == 0
    assert main(["share", "--out", str(out)]) == 1
    assert "never shared" in capsys.readouterr().err
    run = next(out.iterdir())
    data = json.loads((run / "results.json").read_text())
    data["metadata"].update(is_real_measurement=True, model={"backend": "ollama", "name": "m"})
    (run / "results.json").write_text(json.dumps(data))
    assert main(["share", "--out", str(out)]) == 0
    assert '"submission_id"' in capsys.readouterr().out
    target = tmp_path / "sub.json"
    assert main(["share", "--out", str(out), "--export", str(target)]) == 0
    assert validate_record(json.loads(target.read_text())) == []
