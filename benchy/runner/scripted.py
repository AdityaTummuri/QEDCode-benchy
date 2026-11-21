"""A scripted stand-in model for self-tests. NOT a real model: it proves nothing about QEDCode.

`oracle` replays each task's reference fix (so both conditions should resolve every task) and
`broken` replies with a harmless non-fix (so both should resolve none). Together they check that the
runner, the evaluator and the report agree with known answers. Every report made with it is marked
"not a real measurement" and can never be shared.
"""

from __future__ import annotations

import difflib
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from benchy.suite import Task, copy_project

BASELINE_TAG = "benchy_baseline"


def fixed_files(task: Task) -> dict[str, tuple[str, str]]:
    """path -> (original text, fixed text) for every file the reference patch changes."""
    if task.swe is not None:
        patch = task.swe.patch
    else:
        patch = (task.path / "solution.patch").read_text(encoding="utf-8").replace("\r\n", "\n")
    with tempfile.TemporaryDirectory(prefix="benchy-oracle-") as tmp:
        if task.swe is not None:
            from benchy.swebench import cache

            work = cache.extract(task.swe.repo, task.swe.base_commit, Path(tmp) / "p")
        else:
            work = copy_project(task, Path(tmp) / "p")
        subprocess.run(["git", "init", "-q"], cwd=work, check=True, capture_output=True)
        names = subprocess.run(
            ["git", "apply", "--numstat", "-"],
            cwd=work,
            input=patch,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.split("\n")
        paths = [line.split("\t")[-1] for line in names if line.strip()]
        before = {p: (work / p).read_text(encoding="utf-8") for p in paths if (work / p).exists()}
        subprocess.run(
            ["git", "apply", "-"], cwd=work, input=patch, text=True, capture_output=True, check=True
        )
        return {p: (before.get(p, ""), (work / p).read_text(encoding="utf-8")) for p in paths}


class ScriptedModel:
    context_tokens = 16384

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.name = f"scripted:{mode}"
        self._task: Task | None = None
        self._files: dict[str, tuple[str, str]] = {}

    def set_task(self, task: Task) -> None:
        self._task = task
        self._files = fixed_files(task)

    def _target(self, before: str, after: str) -> str:
        return after if self.mode == "oracle" else before.rstrip("\n") + "\n# reviewed\n"

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
        on_token: Callable[[str], None] | None = None,
        tag: str = "",
    ) -> str:
        if self._task is None:
            raise RuntimeError("ScriptedModel.set_task() was not called")
        reply = self._reply(tag)
        if on_token is not None:
            on_token(reply)
        return reply

    def _reply(self, tag: str) -> str:
        assert self._task is not None
        if tag == BASELINE_TAG and self._task.swe is not None:
            return f"<patch>\n{self._swe_patch()}</patch>\n"
        if tag == BASELINE_TAG:
            blocks = [
                f"FILE: {path}\n```python\n{self._target(b, a)}```"
                for path, (b, a) in self._files.items()
            ]
            return "\n\n".join(blocks)
        if tag == "intake":
            return f"KIND: bugfix\nACCEPTANCE:\n- {self._task.request}\nQUESTION: NONE\n"
        if tag == "locator":
            return "\n".join(f"FILE: {p}" for p in self._files) + "\n"
        if tag == "test_writer":
            return "NONE\n"
        if tag in ("coder", "repairer"):
            parts = ["PLAN:\n- apply the change\n"]
            for path, (before, after) in self._files.items():
                parts.append(
                    f"EDIT search_replace path={path}\n<<<<<<< SEARCH\n{before.rstrip(chr(10))}\n"
                    f"=======\n{self._target(before, after).rstrip(chr(10))}\n>>>>>>> REPLACE\n"
                )
            return "\n".join(parts)
        if tag == "explainer":
            return "The change updates the code so it does what the task asks."
        return "NONE\n"

    def _swe_patch(self) -> str:
        """The reference fix (oracle), or a diff that only adds a comment (broken)."""
        assert self._task is not None and self._task.swe is not None
        if self.mode == "oracle":
            return self._task.swe.patch
        path, (before, _after) = next(iter(self._files.items()))
        after = self._target(before, before)
        diff = difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
        return "".join(diff)

    def health(self) -> bool:
        return True

    def unload(self) -> None:
        pass
