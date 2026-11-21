"""The SWE-bench evaluator: the same judge for both conditions, graded the way SWE-bench grades.

1. Extract the task's base commit into a fresh folder.
2. Copy in only the agent's changes to non-test source files (test and test-config edits are
   discarded and listed, exactly like `benchy-pytest-hidden`).
3. Apply SWE-bench's `test_patch` (the hidden tests).
4. Run pytest on the test files the instance names, inside the task's own environment, and read
   one outcome per test node from Benchy's pytest plugin.

**Resolved** = every FAIL_TO_PASS test and every PASS_TO_PASS test passes (SWE-bench's
"RESOLVED_FULL"; xfail counts as a pass, as in SWE-bench). **Regression** = a PASS_TO_PASS test
no longer passes.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from benchy.evaluators.pytest_eval import Evaluation, _scrubbed_env, is_protected
from benchy.swebench import cache
from benchy.swebench.instances import SweInstance, patch_files

PLUGIN_DIR = Path(__file__).resolve().parent / "_plugin"
PASSING = frozenset({"passed", "xfailed"})
TEST_TIMEOUT_S = 900


@dataclass
class SweTestRun:
    outcomes: dict[str, str] = field(default_factory=dict)
    exit_code: int | None = None
    timed_out: bool = False
    output: str = ""


def test_files(inst: SweInstance) -> list[str]:
    """Test files to run: those the test patch touches, plus files named in node ids."""
    files: list[str] = []
    for path in patch_files(inst.test_patch):
        name = path.rsplit("/", 1)[-1]
        if path.endswith(".py") and (name.startswith("test") or name.endswith("_test.py")):
            files.append(path)
    for test_id in (*inst.fail_to_pass, *inst.pass_to_pass):
        if "::" in test_id:
            path = test_id.split("::", 1)[0]
            if path.endswith(".py") and path not in files:
                files.append(path)
    return files


def run_tests(
    python: Path, cwd: Path, files: list[str], timeout: int = TEST_TIMEOUT_S
) -> SweTestRun:
    existing = [f for f in files if (cwd / f).is_file()]
    if not existing:
        return SweTestRun(output="none of the instance's test files exist")
    with tempfile.TemporaryDirectory(prefix="benchy-swe-") as tmp:
        report = Path(tmp) / "report.json"
        env = _scrubbed_env()
        env["BENCHY_SWE_REPORT"] = str(report)
        env["PYTHONPATH"] = str(PLUGIN_DIR)
        cmd = [str(python), "-m", "pytest", "-p", "no:cacheprovider", "-p", "benchy_swe_report"]
        cmd += ["-q", "-rN", "--tb=short", *existing]
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return SweTestRun(timed_out=True, output=f"tests timed out after {timeout}s")
        run = SweTestRun(exit_code=proc.returncode, output=(proc.stdout + proc.stderr)[-6000:])
        if report.is_file():
            run.outcomes = json.loads(report.read_text(encoding="utf-8"))
        return run


def outcome_of(test_id: str, outcomes: dict[str, str]) -> str:
    """The outcome of one SWE-bench test id. Bare names (sympy) match by function name."""
    if test_id in outcomes:
        return outcomes[test_id]
    if "::" in test_id:
        if "[" in test_id and not test_id.endswith("]"):
            # SWE-bench cut this id at a space inside the parameters: match by prefix.
            hits = [v for k, v in outcomes.items() if k.startswith(test_id)]
            if hits:
                return _combine(hits)
        return "missing"
    hits = [
        v
        for k, v in outcomes.items()
        if k.rsplit("::", 1)[-1] == test_id or k.rsplit("::", 1)[-1].split("[", 1)[0] == test_id
    ]
    return _combine(hits) if hits else "missing"


def _combine(hits: list[str]) -> str:
    """One outcome for several matching nodes: passing only when all of them pass."""
    # (the first non-passing outcome otherwise)
    return (
        "passed" if all(h in PASSING for h in hits) else next(h for h in hits if h not in PASSING)
    )


def _passes(test_id: str, outcomes: dict[str, str]) -> bool:
    return outcome_of(test_id, outcomes) in PASSING


# --------------------------------------------------------------------------- building trees


def workspace_changes(workspace: Path) -> tuple[dict[str, bytes | None], list[str]]:
    """The agent's changes against the snapshot commit: source edits, and discarded test edits."""
    out = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames"],
        cwd=workspace,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", "replace")
    changes: dict[str, bytes | None] = {}
    discarded: list[str] = []
    for entry in filter(None, out.split("\0")):
        status, rel = entry[:2], entry[3:]
        parts = Path(rel).parts
        if not parts or parts[0] in (".qed", ".git") or "__pycache__" in parts:
            continue
        if rel.endswith((".pyc", ".pyo")) or Path(rel).name == ".gitignore":
            continue
        if is_protected(Path(rel)):
            discarded.append(rel)
            continue
        path = workspace / rel
        changes[rel] = None if "D" in status or not path.exists() else path.read_bytes()
    return changes, sorted(discarded)


def build_tree(inst: SweInstance, target: Path, changes: dict[str, bytes | None]) -> Path:
    cache.extract(inst.repo, inst.base_commit, target)
    for rel, data in changes.items():
        dest = target / rel
        if data is None:
            dest.unlink(missing_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    return target


def apply_patch(tree: Path, patch: str) -> str:
    """Apply a unified diff with git. Returns "" on success, else git's message."""
    proc = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=tree,
        input=patch,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"},
    )
    return "" if proc.returncode == 0 else (proc.stderr.strip() or "git apply failed")[-800:]


# --------------------------------------------------------------------------- the judge


# A task whose environment here loses more than this share of PASS_TO_PASS tests is not run.
MAX_P2P_ENV_LOSS = 0.10


class SweEvaluator:
    """Judges final workspaces for one instance. Caches the base-commit outcomes."""

    name = "benchy-swebench"
    version = "1"

    def __init__(self, inst: SweInstance, python: Path) -> None:
        self.inst = inst
        self.python = python
        self._base: SweTestRun | None = None

    def run(
        self, changes: dict[str, bytes | None], extra_patch: str = ""
    ) -> tuple[SweTestRun, str]:
        with tempfile.TemporaryDirectory(prefix="benchy-swe-eval-") as tmp:
            tree = build_tree(self.inst, Path(tmp) / "t", changes)
            if extra_patch:
                err = apply_patch(tree, extra_patch)
                if err:
                    return SweTestRun(output=err), f"patch does not apply: {err}"
            err = apply_patch(tree, self.inst.test_patch)
            if err:
                return SweTestRun(output=err), f"the test patch does not apply: {err}"
            return run_tests(self.python, tree, test_files(self.inst)), ""

    def base(self) -> SweTestRun:
        if self._base is None:
            self._base, _ = self.run({})
        return self._base

    def p2p_here(self) -> tuple[list[str], list[str]]:
        """(PASS_TO_PASS tests that pass on the base commit here, the ones that do not).

        Without Docker an environment never matches SWE-bench's images exactly, so a few
        PASS_TO_PASS tests can fail before any change. Like Benchy's visible tests, only tests that
        pass on the original code can count as a regression; the others are listed, not hidden.
        """
        base = self.base().outcomes
        ok = [t for t in self.inst.pass_to_pass if _passes(t, base)]
        lost = [t for t in self.inst.pass_to_pass if t not in ok]
        return ok, lost

    def evaluate(self, workspace: Path, log_dir: Path | None = None) -> Evaluation:
        changes, discarded = workspace_changes(workspace)
        p2p, _lost = self.p2p_here()
        run, error = self.run(changes)
        f2p = self.inst.fail_to_pass
        hidden_ok = [t for t in f2p if _passes(t, run.outcomes)]
        visible_ok = [t for t in p2p if _passes(t, run.outcomes)]
        regressed = sorted(t for t in p2p if t not in visible_ok)
        if run.timed_out:
            error = error or "tests timed out"
        elif not run.outcomes and not error:
            error = "no test outcomes (the changed code may not import)"
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "eval_tests.txt").write_text(run.output, encoding="utf-8")
            (log_dir / "eval_outcomes.json").write_text(
                json.dumps(run.outcomes, indent=1, sort_keys=True), encoding="utf-8"
            )
        return Evaluation(
            resolved=bool(run.outcomes) and len(hidden_ok) == len(f2p) and not regressed,
            regression=bool(regressed),
            hidden_passed=len(hidden_ok),
            hidden_total=len(f2p),
            visible_passed=len(visible_ok),
            visible_total=len(p2p),
            regressed_tests=regressed[:50],
            changed_files=sorted(changes),
            discarded_files=discarded,
            error=error,
        )


@dataclass
class SweCheck:
    task_id: str
    problems: list[str] = field(default_factory=list)
    p2p_lost: list[str] = field(default_factory=list)  # PASS_TO_PASS failing here before any change
    detail: dict = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.problems


def check_instance(inst: SweInstance, python: Path) -> SweCheck:
    """Valid on this machine when, with SWE-bench's test patch applied:

    - every FAIL_TO_PASS test fails on the base commit and passes with the reference fix,
    - the reference fix breaks no PASS_TO_PASS test that passes on the base commit here, and
    - at most 10% of PASS_TO_PASS tests fail here before any change (environment drift).
    """
    result = SweCheck(inst.instance_id)
    judge = SweEvaluator(inst, python)
    before = judge.base()
    if not before.outcomes:
        result.problems.append("no tests ran on the base commit: " + before.output[-300:])
        return result
    after, err = judge.run({}, extra_patch=inst.patch)
    if err:
        result.problems.append(f"reference fix: {err}")
        return result
    p2p, lost = judge.p2p_here()
    result.p2p_lost = lost
    f2p_passing_before = [t for t in inst.fail_to_pass if _passes(t, before.outcomes)]
    f2p_failing_after = [t for t in inst.fail_to_pass if not _passes(t, after.outcomes)]
    broken_by_fix = [t for t in p2p if not _passes(t, after.outcomes)]
    result.detail = {
        "f2p_passing_before": f2p_passing_before,
        "f2p_failing_after_fix": {t: outcome_of(t, after.outcomes) for t in f2p_failing_after},
        "p2p_broken_by_fix": broken_by_fix[:20],
        "p2p_lost_here": len(lost),
        "p2p_total": len(inst.pass_to_pass),
    }
    if before.timed_out or after.timed_out:
        result.problems.append("tests timed out")
    if f2p_passing_before:
        result.problems.append(f"{len(f2p_passing_before)} FAIL_TO_PASS test(s) already pass")
    if f2p_failing_after:
        result.problems.append(
            f"{len(f2p_failing_after)} FAIL_TO_PASS test(s) still fail with the reference fix"
        )
    if broken_by_fix:
        result.problems.append(
            f"the reference fix breaks {len(broken_by_fix)} PASS_TO_PASS test(s)"
        )
    if inst.pass_to_pass and len(lost) > MAX_P2P_ENV_LOSS * len(inst.pass_to_pass):
        result.problems.append(
            f"{len(lost)}/{len(inst.pass_to_pass)} PASS_TO_PASS tests fail here before any change "
            "(this environment differs too much from SWE-bench's)"
        )
    return result
