"""The baseline condition: the same model, used directly, without QEDCode.

One request, one answer, applied as-is. It deliberately reuses nothing from QEDCode (no QEDCode
prompts, edit protocol, file locator, test writer, retries or checks), because the question Benchy
asks is "what does QEDCode add on top of the bare model?".

The model gets the task and every project file (the projects are small), and replies with the full
new contents of each file it changes. The first-try temperature matches QEDCode's first try.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from benchy.runner.scripted import BASELINE_TAG

TEMPERATURE = 0.2
MAX_TOKENS = 4096

PROMPT = """You are a careful software engineer working on a small Python project.

TASK: {request}

PROJECT FILES:
{files}

Make the change the task asks for. Reply with the COMPLETE new contents of every file you change,
each in this exact format, and nothing else:

FILE: <path relative to the project root>
```python
<entire file contents>
```
"""

_BLOCK = re.compile(
    r"^[ \t]*(?:#+\s*|\*\*)?FILE:\s*`?(?P<path>[^\s`*]+)`?\**\s*\n"
    r"[ \t]*```[^\n]*\n(?P<body>.*?)^[ \t]*```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


@dataclass
class BaselineOutcome:
    status: str  # "done" | "no_change" | "unparsable" | "timeout" | "error"
    files_written: list[str] = field(default_factory=list)
    rejected_paths: list[str] = field(default_factory=list)
    message: str = ""


def build_prompt(request: str, workspace: Path, files: list[Path]) -> str:
    rendered = []
    for rel in files:
        text = (workspace / rel).read_text(encoding="utf-8", errors="replace")
        rendered.append(f"--- {rel.as_posix()} ---\n{text}")
    return PROMPT.format(request=request, files="\n".join(rendered))


def parse_reply(reply: str) -> list[tuple[str, str]]:
    return [(m.group("path"), m.group("body")) for m in _BLOCK.finditer(reply)]


def _safe_target(workspace: Path, raw: str) -> Path | None:
    """Only relative paths that stay inside the workspace (and out of .git) may be written."""
    raw = raw.strip()
    rel = Path(raw[2:] if raw.startswith("./") else raw)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or rel.parts[0] in (".git", ".qed"):
        return None
    target = (workspace / rel).resolve()
    try:
        target.relative_to(workspace.resolve())
    except ValueError:
        return None
    return target


def run_baseline(client, request: str, workspace: Path, files: list[Path]) -> BaselineOutcome:
    from benchy.runner.clients import DeadlineExceeded

    prompt = build_prompt(request, workspace, files)
    try:
        reply = client.chat(
            [{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            tag=BASELINE_TAG,
        )
    except DeadlineExceeded:
        return BaselineOutcome("timeout", message="time limit reached before the model answered")
    except Exception as exc:  # a model/server failure is recorded, never hidden
        return BaselineOutcome("error", message=f"{type(exc).__name__}: {exc}"[:500])
    blocks = parse_reply(reply)
    if not blocks:
        return BaselineOutcome("unparsable", message="the reply contained no FILE blocks")
    outcome = BaselineOutcome("done")
    for raw_path, body in blocks:
        target = _safe_target(workspace, raw_path)
        if target is None:
            outcome.rejected_paths.append(raw_path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        outcome.files_written.append(target.relative_to(workspace.resolve()).as_posix())
    if not outcome.files_written:
        outcome.status = "no_change"
        outcome.message = "every FILE path in the reply was outside the project"
    return outcome
