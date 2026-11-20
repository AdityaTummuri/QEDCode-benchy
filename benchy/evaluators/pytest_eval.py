"""The independent evaluator: one judge, identical for every condition.

It never trusts the coding agent's own claims (a QEDCode grade, a model saying "done"). It:

1. starts from a pristine copy of the task project,
2. copies in only the agent's changes to *non-test source files* (changes to tests, conftest.py
   or test configuration are discarded and recorded, so weakening a test can never help),
3. adds the hidden tests, which neither condition has ever seen,
4. runs the original visible tests and the hidden tests with pytest and reads per-test outcomes
   from JUnit XML.

A task counts as **resolved** only when every hidden test passes and no visible test that passed
on the original code now fails (no regression).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from benchy.suite import JUNK, Task, copy_project

SECRET_ENV = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)
TEST_CONFIG_FILES = frozenset(
    {"conftest.py", "pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini"}
)
PYTEST_TIMEOUT_S = 180


def is_protected(rel: Path) -> bool:
    """Files the evaluator owns: tests and anything that configures how tests run."""
    name = rel.name
    return (
        "tests" in rel.parts[:-1]
        or "test" in rel.parts[:-1]
        or rel.parts[0] == "hidden"
        or name in TEST_CONFIG_FILES
        or (name.startswith("test_") and name.endswith(".py"))
        or name.endswith("_test.py")
    )


@dataclass
class TestRun:
    outcomes: dict[str, str] = field(default_factory=dict)  # test id -> passed|failed|error|skipped
    exit_code: int | None = None
    timed_out: bool = False
    output: str = ""

    @property
    def passed(self) -> int:
        return sum(v == "passed" for v in self.outcomes.values())

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def all_passed(self) -> bool:
        return (
            not self.timed_out
            and self.total > 0
            and all(v == "passed" for v in self.outcomes.values())
        )


@dataclass
class Evaluation:
    resolved: bool
    regression: bool
    hidden_passed: int
    hidden_total: int
    visible_passed: int
    visible_total: int
    regressed_tests: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)  # source changes that were evaluated
    discarded_files: list[str] = field(default_factory=list)  # test/config changes ignored
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _scrubbed_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not SECRET_ENV.search(k)}
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    return env


def run_pytest(cwd: Path, target: str, *extra: str, timeout: int = PYTEST_TIMEOUT_S) -> TestRun:
    """Run pytest on `target` inside `cwd` and return per-test outcomes."""
    with tempfile.TemporaryDirectory(prefix="benchy-junit-") as tmp:
        xml_path = Path(tmp) / "junit.xml"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={xml_path}",
            "-o",
            "junit_family=xunit2",
            target,
            *extra,
        ]
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, env=_scrubbed_env(), capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            return TestRun(timed_out=True, output=out[-4000:])
        run = TestRun(exit_code=proc.returncode, output=(proc.stdout + proc.stderr)[-4000:])
        if xml_path.exists():
            run.outcomes = _parse_junit(xml_path)
        return run


def _parse_junit(path: Path) -> dict[str, str]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return {}
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        key = f"{case.get('classname', '')}::{case.get('name', '')}"
        tags = {child.tag for child in case}
        if "error" in tags:
            outcomes[key] = "error"
        elif "failure" in tags:
            outcomes[key] = "failed"
        elif "skipped" in tags:
            outcomes[key] = "skipped"
        else:
            outcomes[key] = "passed"
    return outcomes


def _project_tree(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if p.is_file() and not JUNK.intersection(rel.parts) and rel.name != ".gitignore":
            files[rel.as_posix()] = p.read_bytes()
    return files


def collect_changes(task: Task, workspace: Path) -> tuple[dict[str, bytes | None], list[str]]:
    """The agent's source changes (path -> new bytes, None = deleted) and discarded test edits."""
    with tempfile.TemporaryDirectory(prefix="benchy-orig-") as tmp:
        original = _project_tree(copy_project(task, Path(tmp) / "p"))
    final = _project_tree(workspace)
    changes: dict[str, bytes | None] = {}
    discarded: list[str] = []
    for rel in sorted(set(original) | set(final)):
        before, after = original.get(rel), final.get(rel)
        if before == after:
            continue
        if is_protected(Path(rel)):
            discarded.append(rel)
            continue
        changes[rel] = after
    return changes, discarded


class Evaluator:
    """Evaluates final workspaces for one task. Caches the original-code test outcomes."""

    name = "benchy-pytest-hidden"
    version = "1"

    def __init__(self, task: Task) -> None:
        self.task = task
        self._before: TestRun | None = None
        self._hidden_n: int | None = None

    def _build(self, target: Path, changes: dict[str, bytes | None]) -> Path:
        copy_project(self.task, target)
        for rel, data in changes.items():
            dest = target / rel
            if data is None:
                dest.unlink(missing_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
        shutil.copytree(self.task.hidden_dir, target / "hidden")
        return target

    def visible_before(self) -> TestRun:
        if self._before is None:
            with tempfile.TemporaryDirectory(prefix="benchy-eval-") as tmp:
                tree = self._build(Path(tmp) / "p", {})
                self._before = run_pytest(tree, ".", "--ignore=hidden")
        return self._before

    def evaluate(self, workspace: Path, log_dir: Path | None = None) -> Evaluation:
        changes, discarded = collect_changes(self.task, workspace)
        before = self.visible_before()
        with tempfile.TemporaryDirectory(prefix="benchy-eval-") as tmp:
            tree = self._build(Path(tmp) / "p", changes)
            visible = run_pytest(tree, ".", "--ignore=hidden")
            hidden = run_pytest(tree, "hidden")
        regressed = sorted(
            t
            for t, outcome in before.outcomes.items()
            if outcome == "passed" and visible.outcomes.get(t) != "passed"
        )
        if visible.timed_out:
            regressed = regressed or ["(visible test run timed out)"]
        error = ""
        if hidden.timed_out:
            error = "hidden tests timed out"
        elif hidden.total == 0:
            error = "hidden tests could not be collected (the changed code may not import)"
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "eval_visible.txt").write_text(visible.output, encoding="utf-8")
            (log_dir / "eval_hidden.txt").write_text(hidden.output, encoding="utf-8")
        return Evaluation(
            resolved=hidden.all_passed and not regressed,
            regression=bool(regressed),
            hidden_passed=hidden.passed,
            hidden_total=max(hidden.total, self._hidden_count()),
            visible_passed=visible.passed,
            visible_total=before.total,
            regressed_tests=regressed,
            changed_files=sorted(changes),
            discarded_files=discarded,
            error=error,
        )

    def _hidden_count(self) -> int:
        """Number of hidden tests on the original code (so a crash still shows x/N)."""
        if self._hidden_n is None:
            with tempfile.TemporaryDirectory(prefix="benchy-eval-") as tmp:
                tree = self._build(Path(tmp) / "p", {})
                self._hidden_n = run_pytest(tree, "hidden").total
        return self._hidden_n
