"""Local cache for SWE-bench tasks: bare git clones and one Python environment per repo version.

Everything lives under `~/.qedcode/benchy/cache/` (or `$BENCHY_CACHE`). Nothing here downloads on
its own: `benchy suites fetch` asks first and then calls `ensure_repo` and `build_env`.
Only fixed commands run (git and uv, as argument lists, never through a shell).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from benchy.swebench.specs import EnvSpec, SetupEdit


class CacheError(RuntimeError):
    """A clone, extract or environment build failed. The message says what to do next."""


def cache_root() -> Path:
    override = os.environ.get("BENCHY_CACHE")
    if override:
        return Path(override).expanduser()
    home = os.environ.get("QEDCODE_HOME")
    base = Path(home).expanduser() if home else Path.home() / ".qedcode"
    return base / "benchy" / "cache"


def repo_dir(repo: str) -> Path:
    return cache_root() / "repos" / (repo.replace("/", "__") + ".git")


def repo_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _git(*args: str, cwd: Path | None = None, input_bytes: bytes | None = None) -> bytes:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}
    proc = subprocess.run(
        ["git", "-c", f"core.hooksPath={os.devnull}", *args],
        cwd=cwd,
        env=env,
        input=input_bytes,
        capture_output=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", "replace").strip()[-800:]
        raise CacheError(f"git {' '.join(args[:3])} failed: {msg}")
    return proc.stdout


def has_commit(repo: str, commit: str) -> bool:
    path = repo_dir(repo)
    if not path.is_dir():
        return False
    try:
        _git("--git-dir", str(path), "cat-file", "-e", f"{commit}^{{commit}}")
    except CacheError:
        return False
    return True


def ensure_repo(repo: str, commits: list[str], url: str | None = None) -> Path:
    """A bare clone of `repo` containing every commit in `commits` (clone or fetch as needed)."""
    path = repo_dir(repo)
    if not path.is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".partial")
        shutil.rmtree(tmp, ignore_errors=True)
        _git("clone", "--quiet", "--bare", url or repo_url(repo), str(tmp))
        tmp.rename(path)
    missing = [c for c in commits if not has_commit(repo, c)]
    if missing:
        _git("--git-dir", str(path), "fetch", "--quiet", "origin", *missing)
    still = [c for c in commits if not has_commit(repo, c)]
    if still:
        raise CacheError(f"{repo}: commits not found upstream: {', '.join(c[:10] for c in still)}")
    return path


def extract(repo: str, commit: str, target: Path) -> Path:
    """Write the tree of `commit` into `target` (no .git), with the bytes exactly as committed."""
    data = _git("--git-dir", str(repo_dir(repo)), "archive", "--format=tar", commit)
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in tar.getmembers():
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise CacheError(
                    f"unsafe path in the archive of {repo}@{commit[:10]}: {member.name}"
                )
        if sys.version_info >= (3, 12):
            tar.extractall(target, filter="tar")
        else:  # pragma: no cover - Python 3.11
            tar.extractall(target)
    return target


# --------------------------------------------------------------------------- environments

ENV_LAYOUT = "uv-managed-python-1"  # bump when the way environments are built changes


def env_key(repo: str, env_commit: str, spec: EnvSpec) -> str:
    digest = hashlib.sha256(
        json.dumps([repo, env_commit, repr(spec.key_parts()), ENV_LAYOUT]).encode()
    )
    return f"{repo.replace('/', '__')}-{env_commit[:10]}-{digest.hexdigest()[:8]}"


def env_dir(repo: str, env_commit: str, spec: EnvSpec) -> Path:
    return cache_root() / "envs" / env_key(repo, env_commit, spec)


def env_python(path: Path) -> Path:
    return path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def env_ready(repo: str, env_commit: str, spec: EnvSpec) -> bool:
    path = env_dir(repo, env_commit, spec)
    return (path / "benchy-env.json").is_file() and env_python(path).exists()


def apply_edits(root: Path, edits: tuple[SetupEdit, ...]) -> None:
    for edit in edits:
        file = root / edit.path
        if not file.is_file():
            continue
        lines = file.read_text(encoding="utf-8").splitlines(keepends=True)
        file.write_text(
            "".join(line.replace(edit.old, edit.new, 1) for line in lines), encoding="utf-8"
        )


def _uv() -> str:
    uv = shutil.which("uv")
    if not uv:
        raise CacheError(
            "SWE-bench environments are built with uv, which is not installed. Install it from "
            "https://docs.astral.sh/uv/ and run `benchy suites fetch` again."
        )
    return uv


def _run(cmd: list[str], cwd: Path | None, log: list[str]) -> None:
    log.append("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    log.append((proc.stdout + proc.stderr)[-6000:])
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-12:]
        raise CacheError(
            "environment build step failed: " + " ".join(cmd[:4]) + "\n" + "\n".join(tail)
        )


def build_env(repo: str, env_commit: str, spec: EnvSpec) -> Path:
    """Build (or reuse) the environment and return its Python. A failed build leaves no env."""
    final = env_dir(repo, env_commit, spec)
    if env_ready(repo, env_commit, spec):
        return env_python(final)
    uv = _uv()
    work = final.with_name(final.name + ".partial")
    shutil.rmtree(work, ignore_errors=True)
    log: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="benchy-envsrc-") as tmp:
            src = extract(repo, env_commit, Path(tmp) / "src")
            apply_edits(src, spec.edits)
            # uv's own CPython builds, never a system or IDE Python: the same interpreter on
            # every machine (uv downloads it the first time).
            venv = [uv, "venv", "--quiet", "--seed", "--managed-python"]
            _run([*venv, "--python", spec.python, str(work)], None, log)
            py = str(env_python(work))
            if spec.pip:
                _run([uv, "pip", "install", "--quiet", "--python", py, *spec.pip], None, log)
            for req in spec.requirements:
                if (src / req).is_file():
                    _drop_editable_lines(src)
                    _run([uv, "pip", "install", "--quiet", "--python", py, "-r", req], src, log)
            if spec.install:
                target = str(src) + spec.install[1:]  # "." -> src, ".[test]" -> src[test]
                _run([uv, "pip", "install", "--quiet", "--python", py, target], None, log)
            if spec.optional:
                pins = [p for p in spec.pip if "==" in p]
                constraints = Path(tmp) / "constraints.txt"
                constraints.write_text("\n".join(pins) + "\n", encoding="utf-8")
                cmd = [uv, "pip", "install", "--quiet", "--python", py, *spec.optional]
                _run([*cmd, "--constraint", str(constraints)], None, log)
            if "pytest" not in _installed(uv, py, log):
                _run([uv, "pip", "install", "--quiet", "--python", py, "pytest"], None, log)
            freeze = subprocess.run(
                [uv, "pip", "freeze", "--python", py], capture_output=True, text=True
            ).stdout
        (work / "benchy-env.json").write_text(
            json.dumps(
                {"repo": repo, "env_commit": env_commit, "python": spec.python, "freeze": freeze},
                indent=1,
            ),
            encoding="utf-8",
        )
        (work / "build.log").write_text("\n".join(log), encoding="utf-8")
        shutil.rmtree(final, ignore_errors=True)
        work.rename(final)
    except Exception:
        failed = final.with_name(final.name + ".failed.log")
        failed.parent.mkdir(parents=True, exist_ok=True)
        failed.write_text("\n".join(log), encoding="utf-8")
        shutil.rmtree(work, ignore_errors=True)
        raise
    return env_python(final)


def _drop_editable_lines(src: Path) -> None:
    """Remove `-e .` style lines from the repository's requirement files.

    The project is installed separately, non-editable: old setuptools pins in some projects'
    build requirements cannot build editable installs (PEP 660), and an editable install would
    point at a temporary folder anyway.
    """
    for req in src.glob("requirements*.txt"):
        lines = req.read_text(encoding="utf-8").splitlines()
        kept = [ln for ln in lines if not ln.strip().startswith(("-e ", "--editable"))]
        if kept != lines:
            req.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _installed(uv: str, py: str, log: list[str]) -> set[str]:
    proc = subprocess.run(
        [uv, "pip", "list", "--python", py, "--format", "json"], capture_output=True, text=True
    )
    try:
        return {p["name"].lower() for p in json.loads(proc.stdout or "[]")}
    except json.JSONDecodeError:
        log.append("could not read `uv pip list`")
        return set()
