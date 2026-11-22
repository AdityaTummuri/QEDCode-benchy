"""Agent mode: a coding agent's command line (Google Antigravity's `agy`) with and without QEDCode.

The model mode compares a bare model with the same model inside QEDCode. Agent mode answers the
question an IDE user asks instead: "does adding QEDCode make my agent's fixes more reliable?"

    agent           `agy -p "<issue>"` in a fresh snapshot of the repository
    agent+qedcode   the same command, prompt, model and snapshot, plus the QEDCode skill and the
                    `qed mcp` server set up for that workspace only

The prompt never names QEDCode, so the agent decides by itself whether to use it; whether it did
is recorded (receipts in `.qed/receipts/`). Both conditions get the same permission allow-list,
except that the `qed` command and QEDCode's MCP tools exist only on the QEDCode side. Workspace
setup files (`.venv`, `.agents/`) are hidden from git, so the evaluator never sees them.

The agent's model calls run on the user's Antigravity plan: Benchy cannot count tokens or set a
temperature here, and says so in the report.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

AGENT_CONDITIONS = ("agent", "agent+qedcode")

PROOF = "Fix it, and make sure the fix is actually proven before you tell me it is done."
# agy's headless mode denies every tool that needs a permission it cannot ask for. These rules are
# passed with --settings for one run only (never saved): the project's own Python and read-only
# git and file commands; on the QEDCode side also `qed` and QEDCode's MCP tools.
ALLOW_COMMON = [
    "command(.venv/bin/python)",
    "command(git status)",
    "command(git diff)",
    "command(git log)",
    "command(ls)",
    "command(cat)",
    "command(grep)",
]
ALLOW_QEDCODE = [
    *(f"mcp(qedcode/{tool})" for tool in ("check", "verify", "status", "solve")),
    "command(qed)",
    "command(command -v qed)",
]
# No internet for either side: SWE-bench issues and their upstream fixes are public, so a web
# search would measure lookup, not fixing. `search_web` is not covered by permission rules, so a
# PreToolUse hook (.agents/hooks.json) hard-blocks the web and browser tools; the deny rules below
# block URL reads and network commands, and override any allow rule in the user's own settings.
WEB_TOOLS = (
    "search_web|read_url_content|open_browser_url|read_browser_page|browser_.*|"
    "execute_browser_javascript|capture_browser_.*|click_browser_pixel|list_browser_pages"
)
DENY = [
    "read_url(*)",
    "execute_url(*)",
    *(
        f"command({c})"
        for c in ("gh", "curl", "wget", "git fetch", "git clone", "git pull", "pip", "uv", "npm")
    ),
]
OFFLINE_HOOK = {
    "benchy-offline": {
        "PreToolUse": [
            {
                "matcher": WEB_TOOLS,
                "hooks": [
                    {
                        "type": "command",
                        "command": 'cat >/dev/null; printf \'%s\' \'{"decision":"deny",'
                        '"reason":"No internet access in this benchmark: work from the '
                        "repository only.\"}'",
                        "timeout": 10,
                    }
                ],
            }
        ]
    }
}
# Signs in agy's error output that the plan's quota or rate limit stopped the agent.
QUOTA_RE = re.compile(
    r"quota|rate.?limit|resource.?exhausted|too many requests|\b429\b|usage limit", re.I
)
GAVE_UP_RE = re.compile(
    r"\b(could not|couldn't|unable to|was not able to|wasn't able to|did not manage|"
    r"cannot be fixed|not fixed)\b",
    re.I,
)


class QuotaExhausted(RuntimeError):
    """The agent's plan ran out of quota; the run stops and reports the finished pairs."""


@dataclass
class AgentSpec:
    """Which agent CLI and model to use, and what QEDCode pieces the QEDCode side gets."""

    cli: str = "agy"
    model: str = ""
    skill_dir: Path | None = None
    qed_command: list[str] = field(default_factory=list)

    context_tokens = 0  # not visible from an agent CLI

    @property
    def name(self) -> str:
        return f"{self.cli}:{self.model}" if self.model else self.cli

    def health(self) -> bool:
        return shutil.which(self.cli) is not None

    def unload(self) -> None:  # interface parity with model clients
        pass


@dataclass
class AgentOutcome:
    status: str  # done | no_change | timeout | error | quota
    message: str = ""
    seconds: float = 0.0
    used_qedcode: bool = False
    receipts: int = 0
    grade: str | None = None
    claimed_fixed: bool = False
    final_text: str = ""
    command: list[str] = field(default_factory=list)
    turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None  # includes thinking tokens
    qedcode_calls: int = 0  # MCP tool calls to qedcode, or `qed ...` commands
    web_blocked: int = 0  # web tool calls the offline hook refused
    tool_seconds: dict[str, float] = field(default_factory=dict)  # time per tool name


@dataclass
class StreamSummary:
    """What an `agy --output-format stream-json` run did, read from its NDJSON events."""

    final_text: str = ""
    status: str = ""  # the result event's status, e.g. SUCCESS ("" if it never came)
    turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    steps: list[dict] = field(default_factory=list)  # finished tool steps: name, detail, seconds
    qedcode_calls: int = 0
    web_blocked: int = 0


def _is_qedcode_step(name: str, params: dict) -> bool:
    if name == "call_mcp_tool":
        return "qedcode" in json.dumps(params).lower()
    if name == "run_command":
        cmd = str(params.get("CommandLine", "")).strip()
        return cmd == "qed" or cmd.startswith(("qed ", "command -v qed"))
    return False


def parse_stream(stdout: str) -> StreamSummary:
    out = StreamSummary()
    text: list[str] = []
    usage_in = usage_out = 0
    responses = 0  # model responses (one per step the model takes)
    seen_usage = False
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("event") == "result":
            res = ev.get("result") or {}
            out.status = str(res.get("status", ""))
            out.final_text = str(res.get("response", ""))
            # (num_turns counts the user's prompts, not model steps: see `responses` below)
            usage = res.get("usage") or {}
            if usage:
                out.input_tokens = int(usage.get("input_tokens", 0))
                out.output_tokens = int(usage.get("output_tokens", 0)) + int(
                    usage.get("thinking_tokens", 0)
                )
            continue
        step = ev.get("step_update") or {}
        if step.get("step_type") == "agent_response":
            if step.get("text_delta"):
                text.append(step["text_delta"])
            usage = step.get("usage") or {}
            if step.get("state") == "DONE":
                responses += 1
            if usage and step.get("state") == "DONE":
                seen_usage = True
                usage_in += int(usage.get("input_tokens", 0))
                usage_out += int(usage.get("output_tokens", 0)) + int(
                    usage.get("thinking_tokens", 0)
                )
        elif step.get("step_type") == "tool" and step.get("state") == "ERROR":
            if re.fullmatch(WEB_TOOLS, str(step.get("tool_name") or "")):
                out.web_blocked += 1
        elif step.get("step_type") == "tool" and step.get("state") == "DONE":
            info = step.get("tool_info") or {}
            name = str(step.get("tool_name") or info.get("name") or "?")
            params = info.get("parameters") or {}
            detail = params.get("CommandLine") or params.get("AbsolutePath") or ""
            if name == "call_mcp_tool":
                detail = json.dumps(params)[:200]
            out.steps.append(
                {
                    "tool": name,
                    "detail": str(detail)[:200],
                    "seconds": round(float(step.get("duration_seconds") or 0.0), 2),
                }
            )
            out.qedcode_calls += _is_qedcode_step(name, params)
    out.turns = responses or None
    if not out.final_text:
        out.final_text = "".join(text)
    if out.input_tokens is None and seen_usage:  # stopped before the result event
        out.input_tokens, out.output_tokens = usage_in, usage_out
    return out


def find_skill_dir() -> Path | None:
    """The QEDCode agent skill: $BENCHY_QEDCODE_SKILL, a sibling checkout, or ~/.agents/skills."""
    candidates = []
    env = os.environ.get("BENCHY_QEDCODE_SKILL")
    if env:
        candidates.append(Path(env).expanduser())
    here = Path(__file__).resolve()
    for parent in here.parents[:4]:
        candidates.append(parent.parent / "QEDCode-AgentSkill" / "skills" / "qedcode")
    candidates += [
        Path.home() / ".agents" / "skills" / "qedcode",
        Path.home() / ".claude" / "skills" / "qedcode",
    ]
    for c in candidates:
        if (c / "SKILL.md").is_file():
            return c
    return None


def find_qed() -> list[str]:
    """The `qed` command of the QEDCode that Benchy itself imports (same version on both sides)."""
    local = Path(sys.executable).parent / "qed"
    if local.exists():
        return [str(local)]
    found = shutil.which("qed")
    return [found] if found else []


def build_prompt(request: str) -> str:
    return (
        f"{request.strip()}\n\n"
        "The repository is checked out in the current folder. Its Python environment is "
        "`.venv/bin/python` (for example `.venv/bin/python -m pytest <test file>`). "
        f"Fix the issue in the source code. {PROOF}"
    )


def _exclude(workspace: Path, *patterns: str) -> None:
    exclude = workspace / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as fh:
        fh.write("\n" + "\n".join(patterns) + "\n")


def prepare_agent_workspace(workspace: Path, python: Path, condition: str, spec: AgentSpec) -> None:
    """Point `.venv` at the task's environment; on the QEDCode side add the skill and MCP server."""
    from qedcode.config import ProjectConfig, save_project

    env_root = python.parent.parent
    venv = workspace / ".venv"
    if not venv.exists():
        venv.symlink_to(env_root, target_is_directory=True)
    _exclude(workspace, ".venv", ".agents/")
    # QEDCode's own project settings (in the git-ignored .qed/): the task's interpreter.
    save_project(workspace, ProjectConfig(python=str(python), confirmed=True))
    agents = workspace / ".agents"
    agents.mkdir(exist_ok=True)
    (agents / "hooks.json").write_text(json.dumps(OFFLINE_HOOK, indent=2) + "\n", encoding="utf-8")
    if condition != "agent+qedcode":
        return
    if spec.skill_dir is None or not spec.qed_command:
        raise RuntimeError("agent+qedcode needs the QEDCode skill folder and the qed command")
    shutil.copytree(spec.skill_dir, agents / "skills" / "qedcode")
    server = {"command": spec.qed_command[0], "args": [*spec.qed_command[1:], "mcp"]}
    (agents / "mcp_config.json").write_text(
        json.dumps({"mcpServers": {"qedcode": server}}, indent=2) + "\n", encoding="utf-8"
    )


def _receipts(workspace: Path) -> list[Path]:
    folder = workspace / ".qed" / "receipts"
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime)


def _source_changed(workspace: Path) -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    for line in out.splitlines():
        rel = line[3:]
        if rel.startswith((".qed/", ".agents/")) or "__pycache__" in rel or rel == ".venv":
            continue
        return True
    return False


def agent_command(spec: AgentSpec, prompt: str, condition: str, limit_s: float) -> list[str]:
    allow = ALLOW_COMMON + (ALLOW_QEDCODE if condition == "agent+qedcode" else [])
    cmd = [spec.cli, "-p", prompt, "--print-timeout", f"{int(limit_s)}s"]
    cmd += ["--output-format", "stream-json"]
    cmd += ["--settings", json.dumps({"permissions": {"allow": allow, "deny": DENY}})]
    if spec.model:
        cmd += ["--model", spec.model]
    return cmd


def run_agent(
    spec: AgentSpec,
    request: str,
    workspace: Path,
    *,
    condition: str,
    python: Path,
    limit_s: float,
    log_dir: Path | None = None,
) -> AgentOutcome:
    prepare_agent_workspace(workspace, python, condition, spec)
    prompt = build_prompt(request)
    cmd = agent_command(spec, prompt, condition, limit_s)
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH")}
    # The task environments are shared: nothing may be installed into them from the network.
    env.update({"PIP_NO_INDEX": "1", "UV_OFFLINE": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"})
    started = time.monotonic()
    out = AgentOutcome(status="error", command=cmd)
    try:
        done = subprocess.run(  # no stdin: the agent must never wait for a typed answer
            cmd,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=limit_s + 120,
            env=env,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        stdout, stderr, rc = done.stdout, done.stderr, done.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else ""
        stderr, rc = "", None
        out.status, out.message = "timeout", f"the agent ran over {int(limit_s)}s"
    except OSError as exc:
        out.message = f"could not start {spec.cli}: {exc}"
        return out
    out.seconds = round(time.monotonic() - started, 2)
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        shown = [c if i != 2 else "<prompt>" for i, c in enumerate(cmd)]
        (log_dir / "agent_stream.jsonl").write_text(stdout, encoding="utf-8")
    summary = parse_stream(stdout)
    if log_dir is not None:
        steps = "\n".join(
            f"{i:3d}. {s['seconds']:8.1f}s  {s['tool']}  {s['detail']}"
            for i, s in enumerate(summary.steps, 1)
        )
        (log_dir / "agent_transcript.txt").write_text(
            f"$ {' '.join(shown)}\n\n--- prompt ---\n{prompt}\n\n--- tool steps ---\n{steps}\n"
            f"\n--- final answer ({summary.status or 'no result event'}) ---\n"
            f"{summary.final_text}\n\n--- stderr ---\n{stderr}\n",
            encoding="utf-8",
        )
    out.turns, out.qedcode_calls = summary.turns, summary.qedcode_calls
    out.input_tokens, out.output_tokens = summary.input_tokens, summary.output_tokens
    for s in summary.steps:
        out.tool_seconds[s["tool"]] = round(out.tool_seconds.get(s["tool"], 0.0) + s["seconds"], 1)
    receipts = _receipts(workspace)
    out.receipts = len(receipts)
    out.used_qedcode = bool(receipts) or summary.qedcode_calls > 0
    out.web_blocked = summary.web_blocked
    if receipts:
        try:
            out.grade = json.loads(receipts[-1].read_text(encoding="utf-8")).get("grade")
        except (OSError, json.JSONDecodeError):
            out.grade = None
    out.final_text = summary.final_text.strip()[-2000:]
    changed = _source_changed(workspace)
    if rc is not None:
        if rc != 0 and QUOTA_RE.search(stderr or ""):
            out.status, out.message = "quota", (stderr.strip().splitlines() or ["quota"])[-1][:300]
            return out
        if rc != 0 and "authentication" in (stderr or "").lower():
            out.message = f"{spec.cli} is not signed in: run `{spec.cli}` once by itself"
            return out
        if out.seconds > limit_s or "print_timeout" in (stderr or ""):
            out.status, out.message = "timeout", f"the agent ran over {int(limit_s)}s"
        elif rc != 0:
            out.status = "error"
            last = (stderr.strip().splitlines() or [""])[-1][:300]
            out.message = f"{spec.cli} exit {rc}: {last}"
        else:
            out.status = "done" if changed else "no_change"
    # Claimed fixed: the agent finished normally, changed source code and did not say it failed.
    tail = out.final_text[-800:]
    out.claimed_fixed = out.status == "done" and not GAVE_UP_RE.search(tail)
    return out
