"""SWE-bench task instances as Benchy ships them (`instances.jsonl` in a `kind = "swebench"` suite).

Each line holds the fields of one SWE-bench Verified instance that Benchy needs. The repository
itself is not shipped: `benchy suites fetch` clones it into the local cache.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from benchy.swebench.specs import EnvSpec, spec_for

FIELDS = (
    "instance_id",
    "repo",
    "version",
    "base_commit",
    "environment_setup_commit",
    "problem_statement",
    "patch",
    "test_patch",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "difficulty",
)


@dataclass(frozen=True)
class SweInstance:
    instance_id: str
    repo: str
    version: str
    base_commit: str
    env_commit: str
    problem_statement: str
    patch: str  # the reference fix (never shown to either condition)
    test_patch: str  # SWE-bench's tests for the fix (the hidden tests)
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    difficulty: str = ""

    @property
    def spec(self) -> EnvSpec:
        return spec_for(self.repo, self.version)

    @classmethod
    def from_record(cls, rec: dict) -> SweInstance:
        def ids(value) -> tuple[str, ...]:
            return tuple(json.loads(value) if isinstance(value, str) else value)

        return cls(
            instance_id=rec["instance_id"],
            repo=rec["repo"],
            version=str(rec["version"]),
            base_commit=rec["base_commit"],
            env_commit=rec["environment_setup_commit"],
            problem_statement=rec["problem_statement"],
            patch=rec["patch"],
            test_patch=rec["test_patch"],
            fail_to_pass=ids(rec["FAIL_TO_PASS"]),
            pass_to_pass=ids(rec["PASS_TO_PASS"]),
            difficulty=rec.get("difficulty", ""),
        )

    def to_record(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "repo": self.repo,
            "version": self.version,
            "base_commit": self.base_commit,
            "environment_setup_commit": self.env_commit,
            "problem_statement": self.problem_statement,
            "patch": self.patch,
            "test_patch": self.test_patch,
            "FAIL_TO_PASS": list(self.fail_to_pass),
            "PASS_TO_PASS": list(self.pass_to_pass),
            "difficulty": self.difficulty,
        }


def load_instances(path: Path) -> list[SweInstance]:
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(SweInstance.from_record(json.loads(line)))
            except (KeyError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}:{n}: not a valid SWE-bench instance ({exc})") from exc
    return out


def patch_files(patch: str) -> list[str]:
    """Paths a unified diff changes (the `b/` side), in order, without duplicates."""
    out: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path not in out:
                out.append(path)
        elif line.startswith("diff --git ") and " b/" in line:
            path = line.rsplit(" b/", 1)[1].strip()
            if path not in out:
                out.append(path)
    return out
