"""Plant fresh bugs in real projects and build a private SWE-bench-style suite (maintainers only).

Public benchmarks leak into training data: models recognise SWE-bench tasks by name. A planted bug
is new, so no model can have seen its fix, while the code around it is a real, well-tested project.

    # 1. find candidate bugs: small edits that make a few previously passing tests fail
    python tools/plant_bugs.py scan --project <checkout> --python <env python> \\
        --package networkx --seed <private> --sample 60 --out cand-networkx.jsonl

    # 2. pick candidates, write an issue text for each (a JSON file {candidate id: text}), then
    python tools/plant_bugs.py build --project <checkout> --name networkx \\
        --candidates cand-networkx.jsonl --statements statements.json --suite <private suite dir>

`scan` makes one edit at a time (flip a comparison, swap and/or, drop a `not`, off-by-one on a
small integer, + and -, flip a returned bool, drop a one-line guard), runs the tests, and keeps the
edit only when 1-10 tests that passed before now fail, in at most two test files, without
collection errors. `build` commits each chosen bug to a local bare repository
(`$BENCHY_CACHE/repos/benchy-fresh__<name>.git`) with the catching test functions removed (the
rest of each test file stays); the test patch adds them back (the hidden tests) and the reference
patch undoes the edit. The suite folder holds the answers, so keep it out of public
repositories. Selection never looks at any model's result.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "benchy" / "swebench" / "_plugin"
PASSING = ("passed", "xfailed", "skipped")
CMP_SWAP = {
    ast.Lt: ("<", "<="),
    ast.LtE: ("<=", "<"),
    ast.Gt: (">", ">="),
    ast.GtE: (">=", ">"),
    ast.Eq: ("==", "!="),
    ast.NotEq: ("!=", "=="),
}
FIXED_AUTHOR = {
    "GIT_AUTHOR_NAME": "benchy",
    "GIT_AUTHOR_EMAIL": "benchy@localhost",
    "GIT_COMMITTER_NAME": "benchy",
    "GIT_COMMITTER_EMAIL": "benchy@localhost",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}


@dataclass
class Mutation:
    id: str
    file: str  # repo-relative, forward slashes
    line: int  # 1-based first line
    end_line: int  # 1-based last line (inclusive) of the replaced span
    op: str
    before: str  # the exact lines replaced
    after: str  # their replacement ("" deletes them)
    failing: list[str] = field(default_factory=list)
    failing_files: list[str] = field(default_factory=list)
    status: str = ""  # kept | no_effect | too_many | crash | timeout | ...
    output: str = ""

    def apply(self, root: Path) -> None:
        path = root / self.file
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        old = "".join(lines[self.line - 1 : self.end_line])
        if old != self.before:
            raise RuntimeError(f"{self.id}: {self.file}:{self.line} changed since the scan")
        lines[self.line - 1 : self.end_line] = [self.after] if self.after else []
        path.write_text("".join(lines), encoding="utf-8")

    def diff(self) -> str:
        a = self.before.splitlines(keepends=True)
        b = self.after.splitlines(keepends=True)
        return "".join(difflib.unified_diff(a, b, f"a/{self.file}", f"b/{self.file}", n=0))


# --------------------------------------------------------------------------- finding edits


def _in_functions(tree: ast.AST):
    """Nodes inside function bodies (not decorators, defaults or docstrings)."""
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = fn.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        for stmt in body:
            for node in ast.walk(stmt):
                yield fn, node


def _line_edit(lines: list[str], node: ast.AST, start: int, end: int, new: str) -> tuple:
    """Replace columns [start, end) of the node's (single) line with `new`."""
    i = node.lineno - 1
    line = lines[i]
    return i + 1, i + 1, line, line[:start] + new + line[end:]


def find_mutations(root: Path, rel: str) -> list[Mutation]:
    src = (root / rel).read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    lines = src.splitlines(keepends=True)
    out: list[Mutation] = []
    seen: set[tuple] = set()

    def add(op: str, edit: tuple) -> None:
        line, end_line, before, after = edit
        key = (line, before, after)
        if before == after or key in seen:
            return
        seen.add(key)
        out.append(
            Mutation(f"{rel}:{line}:{op}:{len(out)}", rel, line, end_line, op, before, after)
        )

    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    for _fn, node in _in_functions(tree):
        single = getattr(node, "lineno", None) == getattr(node, "end_lineno", None)
        if isinstance(node, ast.Compare) and single and len(node.ops) == 1:
            swap = CMP_SWAP.get(type(node.ops[0]))
            left, right = node.left, node.comparators[0]
            if swap and left.end_lineno == right.lineno == node.lineno:
                seg = lines[node.lineno - 1][left.end_col_offset : right.col_offset]
                if seg.strip() == swap[0]:
                    new = seg.replace(swap[0], swap[1], 1)
                    add("cmp", _line_edit(lines, node, left.end_col_offset, right.col_offset, new))
        elif isinstance(node, ast.BoolOp) and single and len(node.values) == 2:
            a, b = node.values
            seg = lines[node.lineno - 1][a.end_col_offset : b.col_offset]
            word, other = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
            if seg.strip() == word:
                new = seg.replace(word, other, 1)
                add("boolop", _line_edit(lines, node, a.end_col_offset, b.col_offset, new))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) and single:
            line = lines[node.lineno - 1]
            if line[node.col_offset : node.col_offset + 4] == "not ":
                inner = line[node.operand.col_offset : node.operand.end_col_offset]
                add("not", _line_edit(lines, node, node.col_offset, node.end_col_offset, inner))
        elif (
            isinstance(node, ast.Constant)
            and type(node.value) is int
            and node.value in (0, 1, 2)
            and single
            and isinstance(
                parents.get(id(node)), ast.Compare | ast.Slice | ast.BinOp | ast.Subscript
            )
        ):
            line = lines[node.lineno - 1]
            if line[node.col_offset : node.end_col_offset] == str(node.value):
                for delta in (1, -1):
                    v = node.value + delta
                    if v >= 0:
                        add(
                            "const",
                            _line_edit(lines, node, node.col_offset, node.end_col_offset, str(v)),
                        )
        elif isinstance(node, ast.BinOp) and single and isinstance(node.op, ast.Add | ast.Sub):
            seg = lines[node.lineno - 1][node.left.end_col_offset : node.right.col_offset]
            sym, other = ("+", "-") if isinstance(node.op, ast.Add) else ("-", "+")
            if seg.strip() == sym and node.left.end_lineno == node.right.lineno:
                new = seg.replace(sym, other, 1)
                add(
                    "arith",
                    _line_edit(lines, node, node.left.end_col_offset, node.right.col_offset, new),
                )
        elif (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and type(node.value.value) is bool
            and single
        ):
            v = node.value
            line = lines[node.lineno - 1]
            new = "False" if v.value else "True"
            add("return", _line_edit(lines, node, v.col_offset, v.end_col_offset, new))
        elif (
            isinstance(node, ast.If)
            and not node.orelse
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Return | ast.Raise | ast.Continue | ast.Break)
        ):
            parent = parents.get(id(node))
            siblings = getattr(parent, "body", None)
            if isinstance(siblings, list) and node in siblings and len(siblings) > 1:
                start, end = node.lineno, node.end_lineno
                before = "".join(lines[start - 1 : end])
                add("guard", (start, end, before, ""))
    return out


def source_files(root: Path, packages: list[str]) -> list[str]:
    files = []
    for pkg in packages:
        for path in sorted((root / pkg).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            parts = rel.split("/")
            if any(p in ("tests", "test", "testing", "conftest.py") for p in parts):
                continue
            if parts[-1].startswith("test_") or parts[-1] == "conftest.py":
                continue
            files.append(rel)
    return files


# --------------------------------------------------------------------------- running tests


def run_tests(
    python: str, cwd: Path, args: list[str], timeout: int
) -> tuple[dict[str, str] | None, str]:
    with tempfile.TemporaryDirectory(prefix="plant-") as tmp:
        report = Path(tmp) / "report.json"
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
        env.update({"BENCHY_SWE_REPORT": str(report), "PYTHONPATH": str(PLUGIN_DIR)})
        cmd = [python, "-m", "pytest", "-p", "no:cacheprovider", "-p", "benchy_swe_report"]
        cmd += ["-q", "-rN", "--tb=short", *args]
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return None, "timeout"
        out = proc.stdout + proc.stderr
        if not report.is_file():
            return None, out[-3000:]
        return json.loads(report.read_text(encoding="utf-8")), out


def classify(m: Mutation, base: dict[str, str], outcomes: dict[str, str] | None, out: str) -> None:
    if outcomes is None:
        m.status, m.output = ("timeout" if out == "timeout" else "crash"), out[-1500:]
        return
    if any(k == "<collection>" or ("::" not in k and v == "error") for k, v in outcomes.items()):
        m.status, m.output = "crash", out[-1500:]
        return
    failing = sorted(
        t for t, o in base.items() if o in PASSING and outcomes.get(t, "missing") not in PASSING
    )
    files = sorted({t.split("::", 1)[0] for t in failing})
    m.failing, m.failing_files = failing, files
    if not failing:
        m.status = "no_effect"
    elif len(failing) > 10:
        m.status = "too_many"
    elif len(files) > 2:
        m.status = "too_spread"
    else:
        m.status = "kept"
        m.output = out[-4000:]


def cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.project).resolve()
    files = source_files(root, args.package)
    muts = [m for f in files for m in find_mutations(root, f)]
    rng = random.Random(args.seed)
    rng.shuffle(muts)
    # spread over files: at most --per-file edits from one file
    picked, per_file = [], {}
    for m in muts:
        if per_file.get(m.file, 0) < args.per_file:
            picked.append(m)
            per_file[m.file] = per_file.get(m.file, 0) + 1
        if len(picked) >= args.sample:
            break
    test_args = [*args.tests, *[f"--ignore={p}" for p in args.ignore]]
    print(f"{len(files)} files, {len(muts)} possible edits; testing {len(picked)}", flush=True)
    work = Path(tempfile.mkdtemp(prefix="plant-work-"))
    copies = []
    for i in range(args.jobs):
        dst = work / f"w{i}"
        shutil.copytree(
            root, dst, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__")
        )
        copies.append(dst)
    base, out = run_tests(args.python, copies[0], test_args, args.timeout * 3)
    if base is None:
        print("The tests do not run on the unchanged project:\n" + out, file=sys.stderr)
        return 2
    print(f"baseline: {sum(o in PASSING for o in base.values())} passing", flush=True)
    free = list(copies)

    def one(m: Mutation) -> Mutation:
        dst = free.pop()
        try:
            original = (dst / m.file).read_text(encoding="utf-8")
            try:
                m.apply(dst)
                outcomes, text = run_tests(args.python, dst, test_args, args.timeout)
                classify(m, base, outcomes, text)
            finally:
                (dst / m.file).write_text(original, encoding="utf-8")
        finally:
            free.append(dst)
        print(
            f"  {m.status:10s} {m.op:7s} {m.file}:{m.line} ({len(m.failing)} failing)", flush=True
        )
        return m

    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(one, picked))
    shutil.rmtree(work, ignore_errors=True)
    with Path(args.out).open("w", encoding="utf-8") as fh:
        for m in results:
            fh.write(json.dumps(asdict(m)) + "\n")
    kept = sum(m.status == "kept" for m in results)
    print(f"kept {kept} of {len(results)}; written to {args.out}")
    return 0


# --------------------------------------------------------------------------- building the suite


def _git(cwd: Path, *a: str, env: dict | None = None, input: bytes | None = None) -> str:
    full = {**os.environ, **FIXED_AUTHOR, **(env or {}), "GIT_CONFIG_NOSYSTEM": "1"}
    proc = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *a],
        cwd=cwd,
        env=full,
        capture_output=True,
        input=input,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(a[:3])}: {proc.stderr.decode()[-500:]}")
    return proc.stdout.decode("utf-8", "replace")


def cmd_build(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchy.swebench import cache

    root = Path(args.project).resolve()
    upstream = _git(root, "rev-parse", "HEAD").strip()
    repo = f"benchy-fresh/{args.name}"
    bare = cache.repo_dir(repo)
    if not bare.is_dir():
        bare.parent.mkdir(parents=True, exist_ok=True)
        _git(root.parent, "clone", "-q", "--bare", str(root), str(bare))
    statements = json.loads(Path(args.statements).read_text(encoding="utf-8"))
    cands = {
        m["id"]: Mutation(**m)
        for m in map(json.loads, Path(args.candidates).read_text(encoding="utf-8").splitlines())
    }
    suite = Path(args.suite)
    suite.mkdir(parents=True, exist_ok=True)
    out_file = suite / "instances.jsonl"
    existing = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
    records = []
    with tempfile.TemporaryDirectory(prefix="plant-build-") as tmp:
        wt = Path(tmp) / "wt"
        _git(bare, "worktree", "add", "-q", "--detach", str(wt), upstream)
        try:
            # "clean" commit: upstream minus files that cannot run here (e.g. git submodules)
            if args.drop:
                _git(wt, "rm", "-q", "-r", "--", *args.drop)
                _git(wt, "commit", "-q", "-m", "benchy: drop files that need submodules")
            clean = _git(wt, "rev-parse", "HEAD").strip()
            for n, (cid, text) in enumerate(statements.items(), 1):
                m = cands[cid]
                _git(wt, "checkout", "-q", "--detach", clean)
                m.apply(wt)
                remove_tests(wt, m.failing)
                _git(wt, "add", "-A")
                _git(wt, "commit", "-q", "-m", f"benchy-fresh {args.name} {n}")
                base = _git(wt, "rev-parse", "HEAD").strip()
                patch = _git(wt, "diff", base, clean, "--", m.file)
                test_patch = _git(wt, "diff", base, clean, "--", *m.failing_files)
                p2p = sorted(t for t in m_passing_in(args, m.failing_files) if t not in m.failing)
                records.append(
                    {
                        "instance_id": f"fresh__{args.name}-{n:03d}",
                        "repo": repo,
                        "version": "fresh-1",
                        "base_commit": base,
                        "environment_setup_commit": upstream,
                        "problem_statement": text.strip() + "\n",
                        "patch": patch,
                        "test_patch": test_patch,
                        "FAIL_TO_PASS": json.dumps(m.failing),
                        "PASS_TO_PASS": json.dumps(p2p),
                        "difficulty": m.op,
                    }
                )
        finally:
            _git(bare, "worktree", "remove", "--force", str(wt))
    with out_file.open("w", encoding="utf-8") as fh:
        fh.write(existing)
        for r in records:
            fh.write(json.dumps(r) + "\n")
    print(f"wrote {len(records)} instances for {repo} to {out_file}")
    return 0


def remove_tests(root: Path, failing: list[str]) -> None:
    """Delete the test functions that catch the bug (and nothing else) from their files.

    The rest of each test file stays visible, as in a real project; the test patch adds the
    deleted functions back. A class left with no other statements is deleted with them.
    """
    by_file: dict[str, set[str]] = {}
    for test_id in failing:
        path, _, rest = test_id.partition("::")
        by_file.setdefault(path, set()).add(rest.rsplit("::", 1)[-1].split("[", 1)[0])
    for rel, names in by_file.items():
        path = root / rel
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        spans: list[tuple[int, int]] = []

        def span(node: ast.AST) -> tuple[int, int]:
            first = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
            return first, node.end_lineno

        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in names:
                spans.append(span(node))
            elif isinstance(node, ast.ClassDef):
                body = [
                    b
                    for b in node.body
                    if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))
                ]
                hit = [
                    b
                    for b in body
                    if isinstance(b, ast.FunctionDef | ast.AsyncFunctionDef) and b.name in names
                ]
                if hit and len(hit) == len(body):
                    spans.append(span(node))
                else:
                    spans.extend(span(b) for b in hit)
        if not spans:
            raise RuntimeError(f"none of {sorted(names)} found in {rel}")
        lines = src.splitlines(keepends=True)
        for start, end in sorted(spans, reverse=True):
            del lines[start - 1 : end]
        new = "".join(lines)
        ast.parse(new)  # still valid Python
        path.write_text(new, encoding="utf-8")


_BASE_CACHE: dict[tuple, dict[str, str]] = {}


def m_passing_in(args: argparse.Namespace, files: list[str]) -> list[str]:
    """Tests in `files` that pass on the unchanged project (the PASS_TO_PASS candidates)."""
    key = tuple(files)
    if key not in _BASE_CACHE:
        outcomes, out = run_tests(args.python, Path(args.project), list(files), 900)
        if outcomes is None:
            raise RuntimeError(f"tests in {files} do not run on the unchanged project:\n{out}")
        _BASE_CACHE[key] = outcomes
    return [t for t, o in _BASE_CACHE[key].items() if o in PASSING]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--project", required=True)
    s.add_argument("--python", required=True)
    s.add_argument("--package", action="append", required=True, help="package folder(s) to edit")
    s.add_argument("--tests", nargs="*", default=[], help="pytest targets (default: all)")
    s.add_argument("--ignore", action="append", default=[], help="test paths to leave out")
    s.add_argument("--seed", required=True, help="keep it private: it picks the edits")
    s.add_argument("--sample", type=int, default=60)
    s.add_argument("--per-file", type=int, default=3)
    s.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    s.add_argument("--timeout", type=int, default=300)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_scan)
    b = sub.add_parser("build")
    b.add_argument("--project", required=True)
    b.add_argument("--python", required=True)
    b.add_argument("--name", required=True)
    b.add_argument("--candidates", required=True)
    b.add_argument("--statements", required=True, help="JSON {candidate id: issue text}")
    b.add_argument("--suite", required=True)
    b.add_argument("--drop", nargs="*", default=[], help="files to remove from the clean commit")
    b.set_defaults(func=cmd_build)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
