"""`benchy suites fetch`: clone the repositories and build the environments a SWE-bench suite needs.

It says what it will download and asks first (unless `--yes`). Nothing else in Benchy downloads.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from benchy.suite import Task
from benchy.swebench import cache
from benchy.swebench.specs import Unsupported

# Rough sizes of a bare clone (November 2026), only for the question shown before downloading.
CLONE_MB = {
    "sympy/sympy": 230,
    "sphinx-doc/sphinx": 120,
    "pylint-dev/pylint": 50,
    "pydata/xarray": 60,
}
# Measured per environment on the reference machine (macOS arm64, November 2026).
ENV_MB = {"sympy/sympy": 20, "sphinx-doc/sphinx": 85, "pylint-dev/pylint": 80, "pydata/xarray": 490}


def plan(tasks: list[Task]) -> tuple[dict[str, list[str]], dict[tuple, Task], list[str]]:
    """(repo -> commits to have, env key -> one task needing it, unsupported task ids)."""
    commits: dict[str, list[str]] = {}
    envs: dict[tuple, Task] = {}
    unsupported: list[str] = []
    for task in tasks:
        inst = task.swe
        if inst is None:
            continue
        try:
            spec = inst.spec
        except Unsupported:
            unsupported.append(task.id)
            continue
        wanted = commits.setdefault(inst.repo, [])
        for c in (inst.base_commit, inst.env_commit):
            if c not in wanted:
                wanted.append(c)
        envs.setdefault((inst.repo, inst.env_commit, spec.key_parts()), task)
    return commits, envs, unsupported


def fetch(tasks: list[Task], *, assume_yes: bool, say: Callable[[str], None] = print) -> int:
    commits, envs, unsupported = plan(tasks)
    to_clone = [r for r in commits if not cache.repo_dir(r).is_dir()]
    to_build = [
        t
        for (repo, env_commit, _), t in envs.items()
        if t.swe is not None and not cache.env_ready(repo, env_commit, t.swe.spec)
    ]
    if not to_clone and not to_build:
        say(f"Everything for these {len(tasks)} task(s) is already in {cache.cache_root()}.")
        return 0
    mb = sum(CLONE_MB.get(r, 100) for r in to_clone)
    mb += sum(ENV_MB.get(t.swe.repo, 150) for t in to_build if t.swe is not None)
    say(f"To run {len(tasks)} SWE-bench task(s) Benchy needs, in {cache.cache_root()}:")
    for repo in to_clone:
        say(f"  - a git clone of https://github.com/{repo} (about {CLONE_MB.get(repo, 100)} MB)")
    if to_build:
        say(
            f"  - {len(to_build)} Python environment(s) built with uv from PyPI (Python versions "
            "uv does not have yet are downloaded too)"
        )
    say(f"About {mb / 1000:.1f} GB in total. Delete that folder at any time to free the space.")
    if not assume_yes:
        if not sys.stdin.isatty():
            say("Not asking in a non-interactive session: run again with --yes to download.")
            return 2
        if input("Download now? [y/N] ").strip().lower() not in ("y", "yes"):
            say("Nothing was downloaded.")
            return 1
    failures: list[str] = []
    for repo, wanted in commits.items():
        say(f"Getting {repo} ...")
        try:
            cache.ensure_repo(repo, wanted)
        except cache.CacheError as exc:
            failures.append(f"{repo}: {exc}")
    for n, task in enumerate(to_build, 1):
        inst = task.swe
        assert inst is not None
        say(f"[{n}/{len(to_build)}] environment for {inst.repo} {inst.version} ...")
        try:
            cache.build_env(inst.repo, inst.env_commit, inst.spec)
        except cache.CacheError as exc:
            failures.append(f"{inst.repo} {inst.version}: {str(exc).splitlines()[0]}")
    if unsupported:
        say(f"{len(unsupported)} task(s) cannot run without Docker: {', '.join(unsupported[:5])}")
    if failures:
        say("Some downloads or builds failed (the tasks that need them will not run):")
        for f in failures:
            say(f"  - {f}")
        say("Build logs are next to the environments, named *.failed.log.")
        return 1
    say("Done. Next: `benchy suites check <suite>` proves which tasks are valid on this computer.")
    return 0
