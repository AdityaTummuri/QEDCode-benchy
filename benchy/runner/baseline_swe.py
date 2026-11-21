"""The baseline condition for SWE-bench tasks: SWE-bench's own retrieval baseline.

A whole repository does not fit in a prompt, so the bare model gets what SWE-bench's paper gave
its retrieval baselines: the issue text plus the source files that BM25 ranks highest against it,
up to a token budget, with line numbers. It answers with one unified diff, applied with git.
It reuses nothing from QEDCode (no QEDCode prompts, locator, edit protocol, retries or checks).

`context="oracle"` instead gives the files the reference fix changes (SWE-bench's "oracle
retrieval"). That leaks where the bug is, so it favours the baseline: use it for the strictest
comparison.
"""

from __future__ import annotations

import math
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from benchy.runner.baseline import TEMPERATURE, BaselineOutcome
from benchy.runner.scripted import BASELINE_TAG
from benchy.swebench.instances import patch_files

CONTEXTS = ("bm25", "oracle")
CONTEXT_TOKENS = 13_000  # SWE-bench's smallest BM25 setting
CHARS_PER_TOKEN = 3.5  # the same estimate the usage meter uses
MAX_TOKENS = 4096

PROMPT = """You will be given an issue from a software repository and some of its source files.

<issue>
{issue}
</issue>

<code>
{code}
</code>

Write a patch that resolves the issue. Reply with a single patch in unified diff format that can
be applied with `git apply` from the repository root, and nothing else:

<patch>
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -12,7 +12,7 @@
 unchanged line
-old line
+new line
 unchanged line
</patch>
"""

_SKIP_DIRS = {".git", ".qed", "__pycache__", "doc", "docs", "build", "dist", ".tox", "node_modules"}
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_SPLIT = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


def _is_test_path(rel: Path) -> bool:
    name = rel.name
    return (
        any(part in ("tests", "test", "testing") for part in rel.parts[:-1])
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
    )


def source_files(root: Path) -> list[Path]:
    """Non-test Python files of the repository, relative to `root`, sorted."""
    out = []
    for p in root.rglob("*.py"):
        rel = p.relative_to(root)
        if _SKIP_DIRS.intersection(rel.parts) or _is_test_path(rel):
            continue
        out.append(rel)
    return sorted(out)


def tokens(text: str) -> list[str]:
    """Identifier tokens plus their snake/camel parts, lower-cased (`getLocal_var` -> ...)."""
    out: list[str] = []
    for tok in _TOKEN.findall(text):
        low = tok.lower()
        out.append(low)
        parts = [p.lower() for piece in tok.split("_") for p in _SPLIT.findall(piece)]
        if len(parts) > 1:
            out.extend(parts)
    return out


def bm25_rank(query: str, docs: dict[str, str], k1: float = 1.2, b: float = 0.75) -> list[str]:
    """Document names by BM25 score against `query` (Okapi BM25), best first; ties by name."""
    q = Counter(tokens(query))
    tfs = {name: Counter(tokens(text)) for name, text in docs.items()}
    n = len(tfs) or 1
    avg = sum(sum(tf.values()) for tf in tfs.values()) / n or 1.0
    df: Counter[str] = Counter()
    for tf in tfs.values():
        df.update(set(tf) & set(q))
    scores: dict[str, float] = {}
    for name, tf in tfs.items():
        length = sum(tf.values())
        score = 0.0
        for term in q:
            f = tf.get(term, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * length / avg))
        scores[name] = score
    return sorted(scores, key=lambda name: (-scores[name], name))


def _numbered(text: str) -> str:
    return "\n".join(f"{i} {line}" for i, line in enumerate(text.splitlines(), 1))


@dataclass
class Context:
    files: list[str] = field(default_factory=list)
    text: str = ""


def build_context(
    workspace: Path,
    issue: str,
    context: str = "bm25",
    oracle_patch: str = "",
    budget_tokens: int = CONTEXT_TOKENS,
) -> Context:
    """The code given to the bare model: whole files, best first, until the budget is used."""
    if context == "oracle":
        ranked = [p for p in patch_files(oracle_patch) if (workspace / p).is_file()]
    else:
        docs = {
            rel.as_posix(): (workspace / rel).read_text(encoding="utf-8", errors="replace")
            for rel in source_files(workspace)
        }
        ranked = [name for name in bm25_rank(issue, docs) if docs[name].strip()]
    budget = budget_tokens * CHARS_PER_TOKEN
    used = 0.0
    out = Context()
    blocks = []
    for name in ranked:
        text = (workspace / name).read_text(encoding="utf-8", errors="replace")
        block = f"[start of {name}]\n{_numbered(text)}\n[end of {name}]"
        if used + len(block) > budget:
            if context == "oracle" and not out.files:
                blocks.append(block)  # the oracle always gets the first changed file
                out.files.append(name)
            continue
        blocks.append(block)
        out.files.append(name)
        used += len(block)
    out.text = "\n".join(blocks)
    return out


_PATCH_TAG = re.compile(r"<patch>\s*\n(.*?)</patch>", re.DOTALL)
_FENCE = re.compile(r"```(?:diff|patch)?[^\n]*\n(.*?)```", re.DOTALL)


def extract_patch(reply: str) -> str:
    """The diff in a reply: inside <patch>...</patch>, else in a ``` block, else the bare reply."""
    for pattern in (_PATCH_TAG, _FENCE):
        for m in pattern.finditer(reply):
            body = m.group(1)
            if "--- " in body and "+++ " in body:
                return body if body.endswith("\n") else body + "\n"
    if "--- " in reply and "+++ " in reply and "@@" in reply:
        start = reply.find("--- ")
        if reply.rfind("diff --git", 0, start) != -1:
            start = reply.rfind("diff --git", 0, start)
        body = reply[start:]
        return body if body.endswith("\n") else body + "\n"
    return ""


def apply_model_patch(workspace: Path, patch: str) -> str:
    """Apply a model's diff with git, trying the usual tolerances. Returns "" on success."""
    last = ""
    for extra in ([], ["--recount"], ["--recount", "--ignore-whitespace"]):
        proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", *extra, "-"],
            cwd=workspace,
            input=patch,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return ""
        last = proc.stderr.strip()[-500:]
    return last or "git apply failed"


def _paths_are_safe(patch: str) -> list[str]:
    bad = []
    for path in patch_files(patch):
        parts = Path(path).parts
        if Path(path).is_absolute() or ".." in parts or (parts and parts[0] in (".git", ".qed")):
            bad.append(path)
    return bad


def run_baseline_swe(
    client,
    issue: str,
    workspace: Path,
    *,
    context: str = "bm25",
    oracle_patch: str = "",
) -> tuple[BaselineOutcome, list[str]]:
    """Returns the outcome and the files that were put in the prompt."""
    from benchy.runner.clients import DeadlineExceeded

    ctx = build_context(workspace, issue, context, oracle_patch)
    prompt = PROMPT.format(issue=issue, code=ctx.text)
    try:
        reply = client.chat(
            [{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            tag=BASELINE_TAG,
        )
    except DeadlineExceeded:
        return BaselineOutcome(
            "timeout", message="time limit reached before the model answered"
        ), ctx.files
    except Exception as exc:
        return BaselineOutcome("error", message=f"{type(exc).__name__}: {exc}"[:500]), ctx.files
    patch = extract_patch(reply)
    if not patch:
        return BaselineOutcome(
            "unparsable", message="the reply contained no unified diff"
        ), ctx.files
    bad = _paths_are_safe(patch)
    if bad:
        return BaselineOutcome(
            "no_change", rejected_paths=bad, message="the patch writes outside the repository"
        ), ctx.files
    error = apply_model_patch(workspace, patch)
    if error:
        return BaselineOutcome(
            "unparsable", message=f"the patch does not apply: {error}"[:500]
        ), ctx.files
    return BaselineOutcome("done", files_written=patch_files(patch)), ctx.files
