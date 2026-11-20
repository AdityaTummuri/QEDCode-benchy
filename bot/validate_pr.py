"""Validate a community-submission pull request. Runs from the TRUSTED base-branch checkout.

    python3 bot/validate_pr.py --pr <checkout of the PR head> --base-sha <base commit>

The PR checkout is only read through `git show` / `git ls-tree` (never imported, executed or even
read through the filesystem, so a symlink in the PR cannot point the validator at other files).
Accepted PRs add new, regular, non-executable files under results/submissions/ and nothing else.
Exit code 0 = valid, 1 = invalid. A Markdown summary goes to --summary (GitHub step summary).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TRUSTED_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TRUSTED_ROOT))

from benchy.submission import FILENAME  # noqa: E402
from benchy.submission.validate import known_suites, validate_bytes  # noqa: E402

MAX_FILES = 20


def _git(pr: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(pr), *args], check=True, capture_output=True, timeout=60
    ).stdout


def changed_files(pr: Path, base_sha: str) -> list[tuple[str, str]]:
    """(status, path) for every file the PR changes relative to its merge base."""
    out = _git(pr, "diff", "--name-status", "--no-renames", "-z", f"{base_sha}...HEAD")
    parts = out.decode("utf-8", errors="replace").split("\0")
    pairs = []
    for i in range(0, len(parts) - 1, 2):
        pairs.append((parts[i], parts[i + 1]))
    return pairs


def validate_pr(pr: Path, base_sha: str, trusted: Path = TRUSTED_ROOT) -> tuple[bool, list[str]]:
    lines: list[str] = []
    ok = True
    changes = changed_files(pr, base_sha)
    if not changes:
        return False, ["The pull request changes no files."]
    if len(changes) > MAX_FILES:
        return False, [f"Too many files ({len(changes)}); at most {MAX_FILES} per pull request."]
    suites = known_suites(trusted / "suites")
    existing = {p.name for p in (trusted / "results" / "submissions").glob("*.json")}
    for status, path in changes:
        shown = path.encode("unicode_escape").decode()[:120]
        match = FILENAME.match(path)
        if status != "A" or not match:
            ok = False
            lines.append(
                f"- ❌ `{shown}`: only new files named results/submissions/<id>.json are "
                "accepted in a submission pull request (changes to code, workflows or other "
                "results need a separate, reviewed pull request)."
            )
            continue
        mode = _git(pr, "ls-tree", "HEAD", "--", path).decode().split(" ", 1)[0]
        if mode != "100644":
            ok = False
            lines.append(f"- ❌ `{shown}`: must be a regular, non-executable file (mode {mode}).")
            continue
        if Path(path).name in existing:
            ok = False
            lines.append(f"- ❌ `{shown}`: this submission was already accepted (duplicate).")
            continue
        record, problems = validate_bytes(_git(pr, "show", f"HEAD:{path}"), suites)
        if record is not None and not problems and record["submission_id"] != match.group(1):
            problems = ["the file name must be the record's submission_id"]
        if problems:
            ok = False
            lines.append(f"- ❌ `{shown}`:")
            lines += [f"  - {p}" for p in problems[:15]]
        else:
            n = len(record["attempts"])
            lines.append(
                f"- ✅ `{shown}`: {record['suite']['name']} {record['suite']['version']}, "
                f"{record['model']['name']}, {n} attempts"
            )
    return ok, lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", required=True, type=Path)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)
    try:
        ok, lines = validate_pr(args.pr, args.base_sha)
    except subprocess.CalledProcessError as exc:
        ok, lines = False, [f"Could not read the pull request with git: {exc}"]
    head = "## Benchy submission check: " + ("passed ✅" if ok else "failed ❌")
    note = (
        "\n\nA passing check means the files are well-formed and consistent. It does not prove the "
        "benchmark really ran; accepted results are labelled *community-reported* until a "
        "maintainer reproduces them."
    )
    text = head + "\n\n" + "\n".join(lines) + note + "\n"
    print(text)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as fh:
            fh.write(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
