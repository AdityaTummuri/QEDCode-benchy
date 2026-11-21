"""Benchmark suites: loading tasks, building clean workspaces, fingerprinting, validity checks.

A suite is a folder with an optional `suite.toml` and one sub-folder per task (either directly or
under `tasks/`). A suite whose `suite.toml` says `kind = "swebench"` instead lists SWE-bench
instances in `instances.jsonl`; their repositories and environments come from the local cache
(`benchy suites fetch`, see `benchy/swebench/`). A task folder uses the same layout as QEDCode's
bug zoo, so `bugzoo/` can be run as a suite unchanged:

    <task>/task.txt             the request given to both conditions, word for word
    <task>/hidden/              the evaluator's tests; never shown to either condition
    <task>/solution.patch       a reference fix, used only to check that the task is valid
    <task>/edits.txt            (bug zoo only) a scripted reply; never shown to either condition
    <task>/...everything else   the project exactly as the coding agent receives it
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchy.swebench.instances import SweInstance

# Files and folders that belong to the benchmark, not to the project the agent sees.
RESERVED = frozenset({"hidden", "solution.patch", "edits.txt", "task.txt", "task.toml"})
JUNK = frozenset({"__pycache__", ".pytest_cache", ".DS_Store", ".git", ".qed", ".ruff_cache"})

# Fixed identity and dates so the same task always produces the same commit in every condition.
GIT_ENV = {
    "GIT_AUTHOR_NAME": "benchy",
    "GIT_AUTHOR_EMAIL": "benchy@localhost",
    "GIT_COMMITTER_NAME": "benchy",
    "GIT_COMMITTER_EMAIL": "benchy@localhost",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}


class SuiteError(RuntimeError):
    """A suite or task is missing or malformed. The message says what to fix."""


@dataclass(frozen=True)
class Task:
    id: str
    path: Path
    request: str
    swe: SweInstance | None = None  # set for SWE-bench tasks

    @property
    def is_swe(self) -> bool:
        return self.swe is not None

    def python(self) -> Path:
        """The interpreter that runs this task's tests (SWE-bench: the task's own environment)."""
        if self.swe is None:
            return Path(sys.executable)
        from benchy.swebench import cache
        from benchy.swebench.specs import Unsupported

        try:
            spec = self.swe.spec
        except Unsupported as exc:
            raise SuiteError(f"{self.id} cannot run here: {exc}.") from exc
        if not cache.env_ready(self.swe.repo, self.swe.env_commit, spec) or not cache.has_commit(
            self.swe.repo, self.swe.base_commit
        ):
            raise SuiteError(
                f"{self.id} is not fetched yet. Run `benchy suites fetch` for this suite first."
            )
        return cache.env_python(cache.env_dir(self.swe.repo, self.swe.env_commit, spec))

    @property
    def hidden_dir(self) -> Path:
        return self.path / "hidden"

    def project_files(self) -> list[Path]:
        """Paths (relative to the task folder) of the files the agent receives, sorted."""
        out: list[Path] = []
        for p in sorted(self.path.rglob("*")):
            rel = p.relative_to(self.path)
            if not p.is_file() or rel.parts[0] in RESERVED or JUNK.intersection(rel.parts):
                continue
            out.append(rel)
        return out


@dataclass
class Suite:
    name: str
    version: str
    description: str
    path: Path
    tasks: list[Task] = field(default_factory=list)

    kind: str = "folder"  # "folder" or "swebench"
    time_limit_s: float | None = None  # the suite's recommended limit per condition

    def fingerprint(self) -> str:
        """sha256 over every task file (including hidden tests), so results name the exact data."""
        h = hashlib.sha256()
        if self.kind == "swebench":
            for task in self.tasks:
                assert task.swe is not None
                h.update(json.dumps(task.swe.to_record(), sort_keys=True).encode())
                h.update(repr(task.swe.spec.key_parts()).encode())
                h.update(b"\0")
            return h.hexdigest()
        for task in self.tasks:
            for p in sorted(task.path.rglob("*")):
                rel = p.relative_to(task.path)
                if not p.is_file() or JUNK.intersection(rel.parts):
                    continue
                h.update(f"{task.id}/{rel.as_posix()}\0".encode())
                h.update(_normalized_bytes(p))
                h.update(b"\0")
        return h.hexdigest()

    def select(self, ids: list[str]) -> list[Task]:
        """The tasks named in `ids` (full ids or unique prefixes); all tasks when `ids` is empty."""
        if not ids:
            return list(self.tasks)
        chosen: list[Task] = []
        for wanted in ids:
            matches = [t for t in self.tasks if t.id == wanted] or [
                t for t in self.tasks if t.id.startswith(wanted)
            ]
            if len(matches) != 1:
                known = ", ".join(t.id for t in self.tasks)
                what = "matches no task" if not matches else "matches several tasks"
                raise SuiteError(f"'{wanted}' {what} in suite {self.name}. Tasks: {known}.")
            if matches[0] not in chosen:
                chosen.append(matches[0])
        return chosen


def _normalized_bytes(path: Path) -> bytes:
    """File bytes with CRLF turned into LF, so a Windows checkout gives the same fingerprint."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def builtin_suites_dir() -> Path:
    """Where the suites shipped with Benchy live (source checkout or installed wheel)."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "suites", here / "_suites"):
        if candidate.is_dir():
            return candidate
    raise SuiteError("Benchy's built-in suites are missing. Reinstall Benchy.")


def list_builtin_suites() -> list[str]:
    return sorted(p.name for p in builtin_suites_dir().iterdir() if p.is_dir())


def load_suite(name_or_path: str | Path) -> Suite:
    """Load a built-in suite by name, or any suite folder by path."""
    path = Path(name_or_path)
    if not path.is_dir():
        candidate = builtin_suites_dir() / str(name_or_path)
        if not candidate.is_dir():
            known = ", ".join(list_builtin_suites())
            raise SuiteError(
                f"There is no suite called '{name_or_path}'. Built-in suites: {known}. "
                "You can also pass the path of a suite folder (for example QEDCode's bugzoo/)."
            )
        path = candidate
    path = path.resolve()
    meta: dict = {}
    if (path / "suite.toml").exists():
        try:
            meta = tomllib.loads((path / "suite.toml").read_text(encoding="utf-8")).get("suite", {})
        except tomllib.TOMLDecodeError as exc:
            raise SuiteError(f"{path / 'suite.toml'} is not valid TOML: {exc}") from exc
    if meta.get("kind") == "swebench":
        return _load_swe_suite(path, meta)
    task_root = path / "tasks" if (path / "tasks").is_dir() else path
    tasks = [
        Task(id=p.name, path=p, request=(p / "task.txt").read_text(encoding="utf-8").strip())
        for p in sorted(task_root.iterdir())
        if p.is_dir() and (p / "task.txt").exists()
    ]
    if not tasks:
        raise SuiteError(
            f"No tasks found in {path}. Each task is a folder with a task.txt and a hidden/ folder."
        )
    for task in tasks:
        if not task.hidden_dir.is_dir() or not any(task.hidden_dir.glob("test_*.py")):
            raise SuiteError(f"Task {task.id} has no hidden/test_*.py: the evaluator needs one.")
    return Suite(
        name=str(meta.get("name", path.name)),
        version=str(meta.get("version", "unversioned")),
        description=str(meta.get("description", "")),
        path=path,
        tasks=tasks,
    )


def _load_swe_suite(path: Path, meta: dict) -> Suite:
    from benchy.swebench.instances import load_instances

    file = path / "instances.jsonl"
    if not file.is_file():
        raise SuiteError(f'{path} says kind = "swebench" but has no instances.jsonl.')
    try:
        instances = load_instances(file)
    except ValueError as exc:
        raise SuiteError(str(exc)) from exc
    tasks = [
        Task(id=i.instance_id, path=path, request=i.problem_statement.strip(), swe=i)
        for i in instances
    ]
    if not tasks:
        raise SuiteError(f"{file} lists no instances.")
    limit = meta.get("time_limit_s")
    return Suite(
        name=str(meta.get("name", path.name)),
        version=str(meta.get("version", "unversioned")),
        description=str(meta.get("description", "")),
        path=path,
        tasks=tasks,
        kind="swebench",
        time_limit_s=float(limit) if limit else None,
    )


# --------------------------------------------------------------------------- workspaces


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, **GIT_ENV, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def copy_project(task: Task, target: Path) -> Path:
    """Copy only the project files (no hidden tests, no answers, no task.txt) into `target`."""
    target.mkdir(parents=True, exist_ok=True)
    for rel in task.project_files():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_normalized_bytes(task.path / rel))
    return target


def prepare_workspace(task: Task, target: Path) -> str:
    """A fresh git repository of the task's project. Returns the commit sha.

    Fixed author, dates and contents mean every condition gets the identical commit, which the
    runner records and checks: that is the "same repository snapshot" guarantee.
    """
    if task.swe is not None:
        from benchy.swebench import cache

        cache.extract(task.swe.repo, task.swe.base_commit, target)
        ignore = target / ".gitignore"
        old = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
        sep = "" if not old or old.endswith("\n") else "\n"
        ignore.write_text(old + sep + "__pycache__/\n.pytest_cache/\n.qed/\n", encoding="utf-8")
    else:
        copy_project(task, target)
        (target / ".gitignore").write_text(
            "__pycache__/\n.pytest_cache/\n.qed/\n", encoding="utf-8"
        )
    git(target, "init", "-q")
    git(target, "add", "-A")
    git(target, "commit", "-q", "--no-gpg-sign", "-m", "task snapshot")
    return git(target, "rev-parse", "HEAD").stdout.strip()


# --------------------------------------------------------------------------- validity


@dataclass
class TaskCheck:
    task_id: str
    visible_pass_before: bool = False
    hidden_fail_before: bool = False
    patch_applies: bool = False
    visible_pass_after: bool = False
    hidden_pass_after: bool = False
    problems: list[str] = field(default_factory=list)
    p2p_lost: list[str] = field(default_factory=list)  # SWE-bench: PASS_TO_PASS failing here

    @property
    def valid(self) -> bool:
        return not self.problems


def _pytest_rc(cwd: Path, *args: str) -> int:
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return proc.returncode


def check_task(task: Task) -> TaskCheck:
    """A task is valid when: visible tests pass on the buggy code, hidden tests fail on it, and the
    reference patch makes both pass. Invalid tasks would make the comparison meaningless."""
    if task.swe is not None:
        from benchy.swebench.evaluate import check_instance

        swe = check_instance(task.swe, task.python())
        return TaskCheck(
            task.id,
            visible_pass_before=True,
            hidden_fail_before=not any("already pass" in p for p in swe.problems),
            patch_applies=not any("reference fix:" in p for p in swe.problems),
            visible_pass_after=not any("breaks" in p for p in swe.problems),
            hidden_pass_after=not any("still fail" in p for p in swe.problems),
            problems=list(swe.problems),
            p2p_lost=list(swe.p2p_lost),
        )
    result = TaskCheck(task.id)
    if not (task.path / "solution.patch").exists():
        result.problems.append("missing solution.patch (needed to prove the task is solvable)")
        return result
    with tempfile.TemporaryDirectory(prefix="benchy-check-") as tmp:
        work = Path(tmp) / "w"
        prepare_workspace(task, work)
        shutil.copytree(task.hidden_dir, work / "hidden")
        result.visible_pass_before = _pytest_rc(work, "--ignore=hidden") == 0
        result.hidden_fail_before = _pytest_rc(work, "hidden") not in (0, 5)
        patch = _normalized_bytes(task.path / "solution.patch").decode("utf-8")
        proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            cwd=work,
            input=patch,
            capture_output=True,
            text=True,
        )
        result.patch_applies = proc.returncode == 0
        if result.patch_applies:
            result.visible_pass_after = _pytest_rc(work, "--ignore=hidden") == 0
            result.hidden_pass_after = _pytest_rc(work, "hidden") == 0
    checks = [
        (result.visible_pass_before, "visible tests do not pass on the original code"),
        (result.hidden_fail_before, "hidden tests do not fail on the original code"),
        (result.patch_applies, "solution.patch does not apply"),
    ]
    if result.patch_applies:
        checks += [
            (result.visible_pass_after, "visible tests fail after the reference fix"),
            (result.hidden_pass_after, "hidden tests fail after the reference fix"),
        ]
    result.problems.extend(problem for ok, problem in checks if not ok)
    return result
